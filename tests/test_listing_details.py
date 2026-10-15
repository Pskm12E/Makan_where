import json
from sqlalchemy import create_engine, text
from backend.app import create_app
from test_api import app, Browser
from test_admin import administrator
from backend.models import db, FoodPlace
from backend.listing_details import enrich_listings, safe_url
from backend.migrations import add_listing_details


def basic(place):
    return {'name': place['name'], 'address': '', 'cuisine': '', 'area': place['area'], 'category': place['category']}


def test_every_listing_has_attributed_photo_without_fake_venue_claim(app):
    browser = Browser(app)
    with app.app_context():
        place = db.session.get(FoodPlace, 1)
        place.image_url = ''
        place.is_sample = False
        db.session.commit()
    result = browser.client.get('/api/establishments/1').json['establishment']
    assert result['image'].startswith('https://images.unsplash.com/')
    assert result['photo']['kind'] == 'illustrative'
    assert result['photo']['sourceUrl'] and result['photo']['credit']
    assert result['customImage'] == ''
    assert result['website'] == result['phone'] == ''


def test_details_admin_auth_validation_and_public_roundtrip(app):
    admin, user = administrator(app), Browser(app, 'detail_reader')
    path = '/api/admin/establishments/1'
    original = user.client.get('/api/establishments/1').json['establishment']
    data = {**basic(original), 'website': 'https://example.com/restaurant', 'menuUrl': 'https://example.com/menu',
            'phone': '+65 6123 4567', 'openingHours': 'Mo-Fr 10:00-20:00', 'description': 'A supplied description.',
            'image': 'https://upload.wikimedia.org/wikipedia/commons/a/ab/Example.jpg',
            'photoKind': 'venue', 'photoSourceUrl': 'https://commons.wikimedia.org/wiki/File:Example.jpg',
            'photoCredit': 'Test photographer / CC BY-SA'}
    assert user.send('PATCH', path, data).status_code == 403
    assert admin.client.patch(path, json=data).status_code == 403
    assert admin.send('PATCH', path, data).status_code == 200
    result = user.client.get('/api/establishments/1').json['establishment']
    assert result['website'] == data['website'] and result['phone'] == data['phone']
    assert result['openingHours'] == data['openingHours']
    assert result['photo']['kind'] == 'venue' and result['photo']['credit'] == data['photoCredit']
    for bad in [{'website': 'javascript:alert(1)'}, {'menuUrl': 'https://me:secret@example.com'},
                {'image': 'https://unreviewed.example/image.jpg'}, {'image': '/assets/../secret.png'},
                {'phone': '<script>'}, {'photoKind': 'verified'}, {'photoSourceUrl': ''}]:
        assert admin.send('PATCH', path, {**data, **bad}).status_code == 400
    assert user.client.get('/api/establishments/1').json['establishment']['website'] == data['website']


def test_enrichment_preview_repeat_and_admin_clear_preserved(app):
    admin = administrator(app)
    with app.app_context():
        place = db.session.get(FoodPlace, 1)
        place.place_name = "McDonald's"
        place.is_sample = False
        place.enrichment = None
        db.session.commit()
        assert enrich_listings()['placesChanged'] == 1
        assert db.session.get(FoodPlace, 1).enrichment is None
        assert enrich_listings(apply=True)['placesChanged'] == 1
        assert enrich_listings(apply=True)['placesChanged'] == 0
    place = admin.client.get('/api/establishments/1').json['establishment']
    assert 'Big Mac' in place['menuHighlights'] and place['menuLinkKind'] == 'chain'
    assert admin.send('PATCH', '/api/admin/establishments/1', {**basic(place), 'menuUrl': ''}).status_code == 200
    with app.app_context():
        assert enrich_listings(apply=True)['placesChanged'] == 0
    place = admin.client.get('/api/establishments/1').json['establishment']
    assert place['menuUrl'] == '' and place['menuHighlights'] == []


def test_exact_source_identity_and_invalid_business_links(app, tmp_path, monkeypatch):
    import backend.listing_details as module
    folder = tmp_path / 'data/enrichment'
    folder.mkdir(parents=True)
    (folder / 'chain_links.json').write_text('[]')
    (folder / 'osm_business_details.json').write_text(json.dumps({'sourceTimestamp': '2026-09-21', 'places': [
        {'sourceId': 'node/111', 'name': 'Exact café', 'sourceUrl': 'https://www.openstreetmap.org/node/111',
         'website': 'javascript:alert(1)', 'menuUrl': 'https://example.com/menu', 'phone': '+65 6123 4567'}]}))
    monkeypatch.setattr(module, 'BASE_DIR', tmp_path)
    with app.app_context():
        place = db.session.get(FoodPlace, 1)
        place.place_name = 'Different café'
        place.source_name, place.source_id, place.is_sample = 'OpenStreetMap', 'node/111', False
        db.session.commit()
        assert enrich_listings(apply=True)['placesChanged'] == 0
        place.place_name = 'Exact café'
        db.session.commit()
        result = enrich_listings(apply=True)
        assert result['placesChanged'] == 1 and result['invalidSkipped'] == 1
        assert place.enrichment['phone'] == '+65 6123 4567'
        assert not place.enrichment.get('website')


def test_details_migration_is_additive_and_repeatable(app, tmp_path):
    uri = 'sqlite:///' + str(tmp_path / 'old-listing.sqlite')
    engine = create_engine(uri)
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE food_place (place_id INTEGER PRIMARY KEY, place_name TEXT)'))
        conn.execute(text("INSERT INTO food_place VALUES (77, 'Existing place')"))
    old_app = create_app({**app.config, 'SQLALCHEMY_DATABASE_URI': uri})
    try:
        with old_app.app_context():
            assert add_listing_details()['added'] == ['enrichment']
            assert add_listing_details()['added'] == []
            row = db.session.execute(text('SELECT * FROM food_place')).mappings().one()
            assert row['place_id'] == 77 and row['place_name'] == 'Existing place' and row['enrichment'] is None
            db.session.remove()
            db.engine.dispose()
    finally:
        old_app.extensions['community_client'].close()
        engine.dispose()


def test_photo_urls_disallow_scripts_credentials_and_traversal():
    for value in ['javascript:alert(1)', '//example.com/a.png', '/assets/../secret.png',
                  'https://x:y@images.unsplash.com/a', 'https://images.unsplash.com\\@evil.com/a']:
        assert safe_url(value, image=True) == ''
    assert safe_url('/assets/venues/one.webp', image=True)
