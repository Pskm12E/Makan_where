"""Acceptance checks for live normalization, invariants and retry contracts."""
from copy import deepcopy
from decimal import Decimal
from datetime import datetime
import json
from pathlib import Path
import uuid
import pytest
from sqlalchemy import MetaData, select, func, text
from sqlalchemy.exc import IntegrityError, DBAPIError
from pymongo.errors import WriteError, AutoReconnect
from test_api import app, Browser
from test_admin import administrator
from test_menu_imports import menu_for, preview_and_apply
from test_database_evaluation import concurrent_requests, engine_evidence, evidence
from backend.models import db, Dish, FoodPlace, MenuEntry, MenuPublication, Tag, PlaceTag
from backend.mongo import community_db
from backend.catalogue_design import upgrade_catalogue_design


def test_shared_menu_facts_and_local_overrides(app, record_property):
    admin = administrator(app)
    menu = menu_for(app, (1, 2))
    assert preview_and_apply(admin, menu).status_code == 200
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(MenuPublication)) == 1
        assert db.session.scalar(select(func.count()).select_from(MenuEntry)) == 1
        dishes = list(db.session.scalars(select(Dish).where(Dish.publication_id.is_not(None)).order_by(Dish.place_id)))
        ids = [d.dish_id for d in dishes]
        assert [d.price for d in dishes] == [Decimal('6.25')] * 2
        assert all(d.legacy_dish_name == '' and d.legacy_price == 0 and d.legacy_source_url is None for d in dishes)
    response = admin.send('PATCH', f'/api/admin/establishments/1/dishes/{ids[0]}',
        {'name': 'Outlet correction', 'price': '0.00', 'dietary': '', 'description': ''})
    assert response.status_code == 200
    with app.app_context():
        db.session.remove()
        first, second = (db.session.get(Dish, i) for i in ids)
        assert first.price == 0 and first.dish_name == 'Outlet correction'
        assert second.price == Decimal('6.25') and second.dish_name == 'Imported test dish'
        assert first.menu_entry.reference_price == Decimal('6.25')
        rows = db.session.execute(text('SELECT dish_id,price FROM catalogue_effective_menu WHERE dish_id IN (:a,:b) ORDER BY dish_id'), {'a': ids[0], 'b': ids[1]}).all()
        assert [r.price for r in rows] == [0, Decimal('6.25')]
    assert preview_and_apply(admin, menu).json['added'] == 0
    evidence(record_property, 'Normalization', 'One source entry supports two outlets; zero-price overrides are local and repeat imports add nothing.',
             {'publications': 1, 'sharedEntries': 1, 'outletOfferings': 2, 'localOverride': '0.00', 'otherOutlet': '6.25', 'repeatAdded': 0})


def test_old_schema_upgrade_preserves_ids_overrides_and_tags(app, record_property):
    # Reconstruct the pre-upgrade physical schema, not merely a fresh v3 table.
    extra = {'publication_id', 'dish_name_override', 'description_override', 'price_override', 'dietary_label_override', 'menu_edited_at'}
    new_tables = {'menu_publication', 'menu_entry', 'tag', 'place_tag'}
    with app.app_context():
        db.session.remove()
        with db.engine.begin() as connection:
            connection.execute(text('DROP VIEW catalogue_menu_summary'))
            connection.execute(text('DROP VIEW catalogue_effective_menu'))
        db.drop_all()
        old = MetaData()
        for table in db.metadata.sorted_tables:
            if table.name not in new_tables:
                copied = table.to_metadata(old)
                if table.name == 'dish':
                    for constraint in list(copied.constraints):
                        if constraint.name in {'fk_dish_menu_entry', 'uq_dish_offering', 'ck_dish_override_price', 'ck_dish_entry_identity', 'ck_dish_shared_payload'}:
                            for element in getattr(constraint, 'elements', []):
                                copied.foreign_keys.discard(element)
                                element.parent.foreign_keys.discard(element)
                            copied.constraints.remove(constraint)
                    for name in extra:
                        copied._columns.remove(copied.c[name])
                if table.name == 'food_place':
                    for constraint in list(copied.constraints):
                        if constraint.name in {'ck_place_latitude', 'ck_place_longitude', 'ck_place_hygiene'}:
                            copied.constraints.remove(constraint)
        old.create_all(db.engine)
        source = json.loads(Path('data/menus/kfc_sg_reference_20261004.json').read_text())
        item = source['items'][0]
        with db.engine.begin() as c:
            c.execute(old.tables['area'].insert().values(area_id=1, area_name='Area'))
            c.execute(old.tables['category'].insert().values(category_id=1, category_name='Food'))
            c.execute(old.tables['food_place'].insert().values(place_id=1, area_id=1, category_id=1,
                place_name='KFC', address='', description='', image_url='', tags=['budget', 'family']))
            c.execute(old.tables['dish'].insert().values(dish_id=701, place_id=1, dish_name='Retained manual correction',
                price=Decimal('8.50'), description='Retained description', dietary_label='', is_available=False,
                source_name=source['sourceName'], source_item_id=item['sourceId'], source_url=source['sourceUrl'], is_reference=True))
            c.execute(old.tables['dish'].insert().values(dish_id=702, place_id=1, dish_name='Different source observation',
                price=Decimal('9.00'), description='', dietary_label='', is_available=True,
                source_name=source['sourceName'], source_item_id=source['items'][1]['sourceId'], source_url=source['sourceUrl'],
                source_observed_at=datetime(2026, 10, 5), is_reference=True))
        result = upgrade_catalogue_design()
        assert result['offeringsConverted'] == 1 and result['taggedPlacesConverted'] == 1
        dish = db.session.get(Dish, 701)
        assert dish.price == Decimal('8.50') and dish.dish_name == 'Retained manual correction' and not dish.is_available
        assert dish.menu_entry.item_name == item['name']
        later = db.session.get(Dish, 702)
        assert later.publication_id is None and later.source_observed_at == datetime(2026, 10, 5)
        assert later.dish_name == 'Different source observation' and later.price == Decimal('9.00')
        assert db.session.get(FoodPlace, 1).tags == ['budget', 'family']
        assert db.session.get(FoodPlace, 1).legacy_tags == []
        again = upgrade_catalogue_design()
        assert again['offeringsConverted'] == again['taggedPlacesConverted'] == 0
        with pytest.raises(DBAPIError):
            with db.engine.begin() as c:
                c.execute(text('UPDATE food_place SET latitude=91 WHERE place_id=1'))
        with pytest.raises(DBAPIError):
            with db.engine.begin() as c:
                c.execute(text('UPDATE dish SET source_item_id=\'missing\' WHERE dish_id=701'))
        evidence(record_property, 'Normalization', 'An actual pre-upgrade schema migrates without changing dish identity, edits, removal or tag membership.',
                 {'retainedDishId': 701, 'retainedPrice': '8.50', 'retainedUnavailable': True, 'tags': ['budget', 'family'],
                  'repeatConverted': 0, 'differentSourceObservationPreserved': True, 'invalidCoordinateAndCompositeReferenceRejected': True})


@pytest.mark.parametrize('column,value', [('latitude', 91), ('longitude', -181), ('hygiene_grade', 'Z')])
def test_sql_domain_rejection(app, column, value):
    with app.app_context():
        before = getattr(db.session.get(FoodPlace, 1), column)
        with pytest.raises(DBAPIError):
            with db.engine.begin() as c:
                c.execute(FoodPlace.__table__.update().where(FoodPlace.place_id == 1).values({column: value}))
        db.session.expire_all()
        assert getattr(db.session.get(FoodPlace, 1), column) == before


def test_moderation_validator_rejects_incomplete_resolution_atomically(app):
    owner = Browser(app, 'owner')
    cid = owner.review()
    rid = owner.send('POST', f'/api/content/{cid}/reports', {'reason': 'Test'}).json['id']
    with app.app_context():
        reports = community_db().reports
        before = reports.find_one({'_id': rid})
        with pytest.raises(WriteError):
            reports.update_one({'_id': rid}, {'$set': {'status': 'resolved', 'reason': 'Must not persist'}})
        assert reports.find_one({'_id': rid}) == before


def test_stale_edit_and_delete_cannot_overwrite_a_newer_revision(app):
    owner = Browser(app, 'owner')
    cid = owner.review()
    original = owner.client.get(f'/api/content/{cid}').json['content']
    body = {'title': 'New', 'text': 'New body', 'rating': 3}
    assert owner.send('PATCH', f'/api/content/{cid}', body, headers={'If-Match': str(original['revision'])}).status_code == 200
    for method in ('PATCH', 'DELETE'):
        assert owner.send(method, f'/api/content/{cid}', body if method == 'PATCH' else None,
            headers={'If-Match': str(original['revision'])}).status_code == 409
    current = owner.client.get(f'/api/content/{cid}').json['content']
    assert current['text'] == 'New body' and current['revision'] == original['revision'] + 1


def test_same_request_key_survives_commit_ack_failure_and_rejects_different_payload(app, monkeypatch):
    owner = Browser(app, 'owner')
    import backend.community as community
    body = {'kind': 'thread', 'placeId': 1, 'title': 'A question', 'text': 'One stored post'}
    headers = {'Idempotency-Key': uuid.uuid4().hex}
    with monkeypatch.context() as fault:
        fault.setattr(community, 'serialize', lambda _: (_ for _ in ()).throw(AutoReconnect('after commit')))
        assert owner.send('POST', '/api/content', body, headers=headers).status_code == 503
    replay = owner.send('POST', '/api/content', body, headers=headers)
    assert replay.status_code == 200 and replay.json['replayed']
    assert owner.send('POST', '/api/content', {**body, 'text': 'Changed'}, headers=headers).status_code == 409
    with app.app_context():
        assert community_db().content.count_documents({}) == 1


def test_simultaneous_edits_have_exactly_one_winner(app):
    owner = Browser(app, 'owner')
    cid = owner.review()
    from concurrent.futures import ThreadPoolExecutor
    import threading
    gate = threading.Barrier(6)
    def edit(i):
        browser = Browser(app)
        with browser.client.session_transaction() as session:
            session['user_id'] = owner.user['id']
        gate.wait(timeout=15)
        return browser.send('PATCH', f'/api/content/{cid}', {'title': 'Edit', 'text': f'Writer {i}', 'rating': 2},
                            headers={'If-Match': '1'}).status_code
    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(edit, range(6)))
    assert codes.count(200) == 1 and codes.count(409) == 5


def test_required_preconditions_and_legacy_revision_upgrade(app):
    owner = Browser(app, 'owner')
    payload = {'kind': 'thread', 'placeId': 1, 'title': 'Preconditions', 'text': 'Check'}
    assert owner.client.post('/api/content', json=payload, headers={'X-CSRF-Token': owner.csrf}).status_code == 400
    cid = owner.send('POST', '/api/content', payload).json['content']['id']
    path = f'/api/content/{cid}'
    assert owner.client.patch(path, json={'title': 'Edit', 'text': 'Edit'}, headers={'X-CSRF-Token': owner.csrf}).status_code == 428
    with app.app_context():
        community_db().content.update_one({'_id': cid}, {'$unset': {'revision': ''}})
    response = owner.send('PATCH', path, {'title': 'Edit', 'text': 'Edit'}, headers={'If-Match': '1'})
    assert response.status_code == 200 and response.json['revision'] == 2
    assert owner.send('PATCH', path, {'title': 'Old', 'text': 'Old'}, headers={'If-Match': '1'}).status_code == 409


def test_concurrent_same_key_submissions_create_one_document(app):
    owner = Browser(app, 'owner')
    from concurrent.futures import ThreadPoolExecutor
    import threading
    gate = threading.Barrier(6)
    payload = {'kind': 'thread', 'placeId': 1, 'title': 'One identity', 'text': 'Repeated transmission'}
    key = uuid.uuid4().hex
    def create(_):
        browser = Browser(app)
        with browser.client.session_transaction() as session:
            session['user_id'] = owner.user['id']
        gate.wait(timeout=15)
        result = browser.send('POST', '/api/content', payload, headers={'Idempotency-Key': key})
        return result.status_code, result.json['content']['id']
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(create, range(6)))
    assert sum(code == 201 for code, _ in responses) == 1
    assert sum(code == 200 for code, _ in responses) == 5
    assert len({cid for _, cid in responses}) == 1
    with app.app_context():
        assert community_db().content.count_documents({}) == 1
