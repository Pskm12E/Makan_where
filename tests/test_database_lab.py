import csv
import json
import pytest
from pymongo.errors import WriteError, DuplicateKeyError
from sqlalchemy import select, func
from werkzeug.security import generate_password_hash
from test_api import app, Browser
from test_admin import administrator
from test_imports import row
from backend.models import db, User, Content, Review, now
from backend.mongo import community_db
from backend.database_lab import integrity_audit
from backend.population import counts, seed_coursework
from backend.passwords import hash_password, verify_password, PREFIX


def test_lab_auth_live_metadata_probes_and_no_private_material(app):
    guest, reader = Browser(app), Browser(app, 'reader')
    assert guest.client.get('/api/admin/database-lab').status_code == 401
    assert reader.client.get('/api/admin/database-lab').status_code == 403
    admin = administrator(app)
    assert admin.client.post('/api/admin/database-lab/probes').status_code == 403
    with app.app_context():
        before = counts()
    result = admin.client.get('/api/admin/database-lab')
    assert result.status_code == 200, result.json
    assert result.json['mongo']['version']
    assert list(result.json['mongo']['pipeline'][2]['$sort']) == ['rating', 'reviewCount', '_id']
    assert len(result.json['schema']['tables']) == 21
    assert len(result.json['queries']['queries']) == 6
    assert 'NOT (EXISTS' in result.json['queries']['queries'][0]['sql']
    assert all(r['orphans'] == 0 for r in result.json['audit']['sqlForeignKeys'])
    response = admin.send('POST', '/api/admin/database-lab/probes', {})
    assert response.status_code == 200, response.json
    assert len(response.json['checks']) == 9
    assert all(c['passed'] for c in response.json['checks']), response.json
    with app.app_context():
        assert counts() == before
        assert not any(n.startswith('lab_probe_') for n in community_db().list_collection_names())
    encoded = json.dumps(result.json)
    assert 'test-only-pepper' not in encoded and 'test-only-secret' not in encoded
    assert 'UniqueTestPassword' not in encoded and 'password_hash": "' not in encoded


def test_mongo_rejects_invalid_subtypes_and_duplicate_votes_at_database(app):
    user = Browser(app, 'reviewer')
    identifier = user.review()
    with app.app_context():
        mongo = community_db()
        original = mongo.content.find_one({'_id': identifier})
        for changes in [{'rating': 6}, {'rating': '4'}, {'kind': 'comment'}, {'removed_at': now()}]:
            with pytest.raises(WriteError) as error:
                mongo.content.insert_one({**original, '_id': identifier + 100, **changes})
            assert error.value.code == 121
        assert mongo.content.count_documents({}) == 1
        vote = {'user_id': user.user['id'], 'content_id': identifier, 'voted_at': now()}
        mongo.upvotes.insert_one(dict(vote))
        with pytest.raises(DuplicateKeyError):
            mongo.upvotes.insert_one(dict(vote))
        assert mongo.upvotes.count_documents({}) == 1


def test_cross_engine_reconciliation_detects_out_of_band_orphans(app):
    user = Browser(app, 'reviewer')
    identifier = user.review()
    with app.app_context():
        assert not any(integrity_audit()['mongoReferences'].values())
        # Mongo cannot enforce a SQL FK. A direct privileged write can bypass
        # application checks; reconciliation must report that honestly.
        community_db().content.update_one({'_id': identifier}, {'$set': {'author_id': 999999}})
        assert integrity_audit()['mongoReferences']['authors'] == 1


def test_password_salts_pepper_legacy_upgrade_and_wrong_login(app):
    browser = Browser(app, 'legacy')
    with app.app_context():
        first, second = hash_password('ExamplePassword!'), hash_password('ExamplePassword!')
        assert first != second
        assert verify_password(first, 'ExamplePassword!')
        assert not verify_password(first, 'wrong')
        old_pepper = app.config['PASSWORD_PEPPER']
        app.config['PASSWORD_PEPPER'] = 'different-pepper-' * 4
        assert not verify_password(first, 'ExamplePassword!')
        app.config['PASSWORD_PEPPER'] = old_pepper
        legacy = generate_password_hash('LegacyPassword!')
        db.session.get(User, browser.user['id']).password_hash = legacy
        db.session.commit()
    browser.send('POST', '/api/logout')
    browser.csrf = browser.client.get('/api/session').json['csrfToken']
    assert browser.send('POST', '/api/login', {'identity': 'legacy', 'password': 'wrong'}).status_code == 401
    with app.app_context():
        assert db.session.get(User, browser.user['id']).password_hash == legacy
    assert browser.send('POST', '/api/login', {'identity': 'legacy', 'password': 'LegacyPassword!'}).status_code == 200
    with app.app_context():
        assert db.session.get(User, browser.user['id']).password_hash.startswith(PREFIX)


def test_sql_migration_is_idempotent_preserves_source_and_refuses_conflicts(app):
    user = Browser(app, 'legacy')
    with app.app_context():
        c = Content(author_id=user.user['id'], place_id=1, kind='review', body='Legacy review')
        db.session.add(c)
        db.session.flush()
        db.session.add(Review(content_id=c.content_id, rating=4, title='Original'))
        db.session.commit()
        cid = c.content_id
    runner = app.test_cli_runner()
    assert runner.invoke(args=['migrate-community']).exit_code == 0
    again = runner.invoke(args=['migrate-community'])
    assert again.exit_code == 0 and json.loads(again.output)['inserted'] == 0
    with app.app_context():
        assert db.session.get(Content, cid).body == 'Legacy review'
        assert community_db().content.find_one({'_id': cid})['body'] == 'Legacy review'
        db.session.get(Content, cid).body = 'Conflicting legacy edit'
        db.session.commit()
    assert runner.invoke(args=['migrate-community']).exit_code != 0
    with app.app_context():
        assert community_db().content.find_one({'_id': cid})['body'] == 'Legacy review'
    assert user.review() > cid


def test_population_rerun_has_no_duplicates_and_keeps_edits(app, tmp_path):
    path = tmp_path / 'source.csv'
    record = row()
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=record)
        writer.writeheader()
        writer.writerow(record)
    with app.app_context():
        first = seed_coursework(path)
        mongo = community_db()
        cid = mongo.content.find_one({'kind': 'review'})['_id']
        mongo.content.update_one({'_id': cid}, {'$set': {'body': 'DEMO edited by student'}})
        second = seed_coursework(path)
        assert all(n == 0 for rows in second['added'].values() for n in rows.values()), second
        assert second['after']['sql']['food_place'] == 7
        assert second['after']['mongo'] == {'content': 720, 'upvotes': 600, 'reports': 20}
        assert mongo.content.find_one({'_id': cid})['body'] == 'DEMO edited by student'
        assert not any(integrity_audit()['mongoReferences'].values())
        assert mongo.content.count_documents({'is_demo': {'$ne': True}}) == 0
        assert db.session.scalar(select(func.count()).select_from(Content)) == 0
        mongo.content.update_one({'_id': cid}, {'$set': {'author_id': 999999}})
        with pytest.raises(ValueError, match='matching pair'):
            seed_coursework(path)
        assert mongo.content.find_one({'_id': cid})['author_id'] == 999999


def test_lab_detects_missing_vote_index_instead_of_claiming_success(app):
    admin = administrator(app)
    with app.app_context():
        community_db().upvotes.drop_index('one_vote_per_user')
    result = admin.send('POST', '/api/admin/database-lab/probes', {})
    assert result.status_code == 200, result.json
    assert result.json['checks'][-1]['passed'] is False


def test_security_demo_uses_dummy_hashes_and_has_csrf_protection(app):
    admin = administrator(app)
    assert admin.client.post('/api/admin/database-lab/security').status_code == 403
    result = admin.send('POST', '/api/admin/database-lab/security', {}).json
    assert result['differentSalts'] and result['correctPasswordWorks'] and result['wrongPepperRejected']
    with app.app_context():
        real_hash = db.session.get(User, admin.user['id']).password_hash
    assert real_hash not in json.dumps(result)


def test_mongo_outage_returns_503_without_sql_fallback(app):
    from pymongo import MongoClient
    import socket
    # Reserve a bound, non-listening local socket so no live server can occupy
    # this test port. This exercises a real refused MongoDB connection.
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1', 0))
        port = reserved.getsockname()[1]
        failed_client = MongoClient(f'mongodb://127.0.0.1:{port}', serverSelectionTimeoutMS=50, connectTimeoutMS=50)
        original = app.extensions['community_db']
        app.extensions['community_db'] = failed_client['unavailable_test']
        try:
            client = app.test_client()
            assert client.get('/api/health').status_code == 503
            response = client.get('/api/establishments/1')
            assert response.status_code == 503
            assert 'temporarily unavailable' in response.json['error']
            assert 'rating' not in response.json
        finally:
            app.extensions['community_db'] = original
            failed_client.close()


def test_mongo_feed_seek_pagination_has_no_lost_or_repeated_documents(app):
    user = Browser(app, 'reviewer')
    cid = user.review()
    with app.app_context():
        original = community_db().content.find_one({'_id': cid})
        community_db().content.insert_many([{**original, '_id': cid + offset,
            'request_key': f'pagination-fixture-request-{offset}'} for offset in range(1, 205)])
    seen, cursor = [], 0
    for _ in range(3):
        result = user.client.get(f'/api/content?place_id=1&cursor={cursor}').json
        seen.extend(c['id'] for c in result['content'])
        cursor = result['nextCursor']
        if cursor is None:
            break
    assert cursor is None and len(seen) == len(set(seen)) == 205
    assert seen == sorted(seen)
