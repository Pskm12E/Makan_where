import pytest
from sqlalchemy import func, select
from test_api import app, Browser
from backend.example_community import seed_listing_examples
from backend.models import db, FoodPlace, User, now
from backend.mongo import community_db


def source_target():
    place = db.session.get(FoodPlace, 1)
    place.is_sample = False
    place.source_name, place.source_id = 'OpenStreetMap', 'node/example-fixture'
    place.source_url = 'https://www.openstreetmap.org/node/example-fixture'
    db.session.commit()
    return {'id': place.place_id, 'name': place.place_name, 'sourceUrl': place.source_url}


def test_examples_are_labelled_excluded_from_ratings_and_preserved_on_repeat(app):
    with app.app_context():
        target = source_target()
        preview = seed_listing_examples([target])
        assert (preview['reviews'], preview['threads'], preview['replies']) == (3, 2, 4)
        assert community_db().content.count_documents({}) == 0
        assert db.session.scalar(select(func.count()).select_from(User)) == 0
        assert seed_listing_examples([target], apply=True)['added'] == 9
        records = list(community_db().content.find({}))
        assert all(r['is_demo'] and r['is_example'] and 'fictional' in r['body'].lower() for r in records)
        threads = {r['_id']: r for r in records if r['kind'] == 'thread'}
        assert all(threads[r['thread_id']]['place_id'] == r['place_id'] for r in records if r['kind'] == 'comment')
    client = app.test_client()
    examples = client.get('/api/reviews?place_id=1').json['content']
    assert len(examples) == 3 and all(r['isDemo'] and r['isExample'] for r in examples)
    assert client.get('/api/establishments/1').json['establishment']['rating'] == 0
    assert client.get('/api/analytics').json['topRated'] == []
    actual = Browser(app, 'actual_visitor')
    created = actual.send('POST', '/api/reviews', {'placeId': 1, 'title': 'Real test review',
        'text': 'A normal user contribution', 'rating': 2})
    assert created.status_code == 201 and not created.json['content']['isExample']
    assert client.get('/api/establishments/1').json['establishment']['rating'] == 2
    assert client.get('/api/analytics').json['topRated'][0]['reviewCount'] == 1
    with app.app_context():
        record = community_db().content.find_one({'kind': 'review', 'is_example': True})
        community_db().content.update_one({'_id': record['_id']}, {'$set': {
            'body': 'An edited example', 'removed_at': now(), 'removed_by_id': record['author_id']}})
        repeat = seed_listing_examples([target], apply=True)
        assert repeat['added'] == 0 and repeat['skipped'] == 9
        kept = community_db().content.find_one({'_id': record['_id']})
        assert kept['body'] == 'An edited example' and kept['removed_at'] is not None
        assert community_db().content.count_documents({}) == 10


def test_example_identity_validation_happens_before_writes(app):
    with app.app_context():
        target = source_target()
        with pytest.raises(ValueError, match='source identity'):
            seed_listing_examples([target, {**target, 'id': 2}], apply=True)
        assert db.session.scalar(select(func.count()).select_from(User)) == 0
        assert community_db().content.count_documents({}) == 0
    Browser(app, 'example_guest_01')  # Existing real identity must never be repurposed.
    with app.app_context():
        with pytest.raises(ValueError, match='reserved example account'):
            seed_listing_examples([target], apply=True)
        assert db.session.scalar(select(func.count()).select_from(User)) == 1
        assert community_db().content.count_documents({}) == 0
