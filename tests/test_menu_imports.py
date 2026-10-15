from copy import deepcopy
import json

from sqlalchemy import create_engine, func, inspect, select, text

from test_api import app, Browser
from test_admin import administrator
from backend.app import create_app
from backend.models import db, Dish, FoodPlace, PopulationRun
from backend.menu_imports import digest, normalise_menu
from backend.migrations import add_menu_provenance


def menu_for(app, places=(1,)):
    with app.app_context():
        targets = [{"id": i, "name": db.session.get(FoodPlace, i).place_name, "sourceId": ""} for i in places]
    return {"sourceName": "Test restaurant menu", "sourceUrl": "https://example.com/menu",
            "observedAt": "2026-09-30T10:00:00+08:00", "currency": "SGD",
            "isReference": len(places) > 1, "places": targets,
            "items": [{"sourceId": "new-dish-1", "name": "Imported test dish", "price": "6.25",
                       "description": "Fixture description"}]}


def preview_and_apply(admin, menu):
    preview = admin.send('POST', '/api/admin/menu-imports', {'menu': menu})
    assert preview.status_code == 200, preview.json
    return admin.send('POST', '/api/admin/menu-imports', {'menu': preview.json['menu'],
                     'apply': True, 'previewToken': preview.json['previewToken']})


def test_menu_import_access_key_scope_and_no_secrets(app):
    guest, user, admin = Browser(app), Browser(app, 'reader'), administrator(app)
    menu = menu_for(app)
    for browser, status in [(guest, 401), (user, 403)]:
        assert browser.client.get('/api/admin/menu-imports').status_code == status
        assert browser.send('POST', '/api/admin/menu-imports', {'menu': menu}).status_code == status
        assert browser.client.get('/api/admin/establishments/1/menu-template').status_code == status
    assert admin.client.post('/api/admin/menu-imports', json={'menu': menu}).status_code == 403
    client = app.test_client()
    assert client.post('/api/integrations/menu-imports', json={'menu': menu}).status_code == 503
    key = 'menu-import-test-secret-' * 3
    app.config['MENU_IMPORT_API_KEY'] = key
    assert client.post('/api/integrations/menu-imports', json={'menu': menu}).status_code == 401
    assert client.get('/api/integrations/menu-targets?name=KFC', headers={'Authorization': 'Bearer wrong'}).status_code == 401
    headers = {'Authorization': 'Bearer ' + key}
    preview = client.post('/api/integrations/menu-imports', json={'menu': menu}, headers=headers)
    assert preview.status_code == 200
    result = client.post('/api/integrations/menu-imports', json={'menu': preview.json['menu'], 'apply': True,
                         'previewToken': preview.json['previewToken']}, headers=headers)
    assert result.status_code == 200 and result.json['added'] == 1
    assert client.patch('/api/profile', json={}, headers=headers).status_code == 403
    assert client.get('/api/admin/schema', headers=headers).status_code == 401
    status = admin.client.get('/api/admin/menu-imports').json
    assert status['apiConfigured'] and len(status['history']) == 1
    assert key not in json.dumps(status) and key not in json.dumps(preview.json)


def test_menu_import_preview_repeat_edits_and_removal_are_preserved(app):
    admin = administrator(app)
    menu = menu_for(app)
    before = admin.client.get('/api/establishments/1').json['establishment']['menu']
    preview = admin.send('POST', '/api/admin/menu-imports', {'menu': menu})
    assert preview.json['added'] == 1
    assert admin.client.get('/api/establishments/1').json['establishment']['menu'] == before
    result = preview_and_apply(admin, menu)
    assert result.status_code == 200 and result.json['added'] == 1
    saved = admin.client.get('/api/establishments/1').json['establishment']['menu'][-1]
    assert saved['sourceName'] == menu['sourceName'] and saved['sourceObservedAt'] == '2026-09-30T02:00:00Z'
    assert saved['description'] == 'Fixture description'
    path = f"/api/admin/establishments/1/dishes/{saved['id']}"
    assert admin.send('PATCH', path, {'name': saved['name'], 'price': '8.50', 'description': 'Student edit'}).status_code == 200
    assert admin.send('DELETE', path).status_code == 200
    repeated = preview_and_apply(admin, menu)
    assert repeated.json['added'] == 0 and repeated.json['skipped'] == 1
    with app.app_context():
        dish = db.session.get(Dish, saved['id'])
        assert str(dish.price) == '8.50' and dish.description == 'Student edit'
        assert not dish.is_available and dish.source_observed_at is None
        assert db.session.scalar(select(func.count()).select_from(PopulationRun)) == 1
    public = app.test_client().get('/api/establishments/1').json['establishment']
    assert all(d['id'] != saved['id'] for d in public['menu'])


def test_menu_import_invalid_rows_and_venue_identity_do_not_write(app):
    admin = administrator(app)
    original = menu_for(app)
    variants = []
    for price in ['-1', 'NaN', '1.001', None, True]:
        menu = deepcopy(original)
        menu['items'].append({'sourceId': 'bad', 'name': 'Bad item', 'price': price})
        variants.append(menu)
    variants += [{**original, 'currency': 'USD'}, {**original, 'sourceUrl': 'javascript:alert(1)'},
                 {**original, 'sourceUrl': 'https://user:pass@example.com/menu'},
                 {**original, 'observedAt': '2026-09-30'}, {**original, 'isReference': 'false'},
                 {**original, 'items': original['items'] * 2}]
    for menu in variants:
        assert admin.send('POST', '/api/admin/menu-imports', {'menu': menu}).status_code == 400
    mismatch = deepcopy(original)
    mismatch['places'][0]['sourceId'] = 'node/wrong-outlet'
    assert admin.send('POST', '/api/admin/menu-imports', {'menu': mismatch}).status_code == 409
    admin.send('DELETE', '/api/admin/establishments/1')
    assert admin.send('POST', '/api/admin/menu-imports', {'menu': original}).status_code == 400
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(Dish)) == 18


def test_menu_import_requires_unchanged_preview_and_actor(app):
    admin = administrator(app)
    menu = menu_for(app)
    assert admin.send('POST', '/api/admin/menu-imports', {'menu': menu, 'apply': True}).status_code == 400
    preview = admin.send('POST', '/api/admin/menu-imports', {'menu': menu}).json
    altered = deepcopy(preview['menu'])
    altered['items'][0]['price'] = '90.00'
    assert admin.send('POST', '/api/admin/menu-imports', {'menu': altered, 'apply': True,
                      'previewToken': preview['previewToken']}).status_code == 409
    app.config['MENU_IMPORT_API_KEY'] = 'test-api-key-' * 4
    result = app.test_client().post('/api/integrations/menu-imports', json={'menu': preview['menu'],
              'apply': True, 'previewToken': preview['previewToken']},
              headers={'Authorization': 'Bearer ' + app.config['MENU_IMPORT_API_KEY']})
    assert result.status_code == 409
    admin.send('POST', '/api/admin/establishments/1/dishes', {'name': 'Concurrent dish', 'price': '3.00'})
    assert admin.send('POST', '/api/admin/menu-imports', {'menu': preview['menu'], 'apply': True,
                      'previewToken': preview['previewToken']}).status_code == 409


def test_chain_reference_labelling_and_existing_name_conflicts(app):
    admin = administrator(app)
    menu = menu_for(app, (1, 2))
    assert admin.send('POST', '/api/admin/menu-imports', {'menu': {**menu, 'isReference': False}}).status_code == 400
    result = preview_and_apply(admin, menu)
    assert result.status_code == 200 and result.json['added'] == 2
    for pid in [1, 2]:
        place = app.test_client().get(f'/api/establishments/{pid}').json['establishment']
        assert place['hasReferenceMenu']
        assert next(d for d in place['menu'] if d['name'] == 'Imported test dish')['isReference']
    conflict = deepcopy(menu)
    conflict['sourceName'] = 'Different supplier'
    preview = admin.send('POST', '/api/admin/menu-imports', {'menu': conflict}).json
    assert len(preview['conflicts']) == 2
    assert preview_and_apply(admin, conflict).status_code == 409


def test_menu_import_rolls_back_dishes_if_receipt_commit_fails(app):
    admin = administrator(app)
    menu = menu_for(app)
    with app.test_request_context():
        normalised = normalise_menu(menu)
        db.session.add(PopulationRun(run_key='menu:' + digest(normalised), details={'test': 'existing receipt'}))
        db.session.commit()
    result = preview_and_apply(admin, menu)
    assert result.status_code == 409
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(Dish)) == 18


def test_menu_provenance_migration_preserves_old_table_and_is_repeatable(app, tmp_path):
    uri = 'sqlite:///' + str(tmp_path / 'old-menu.sqlite')
    engine = create_engine(uri)
    with engine.begin() as c:
        c.execute(text('CREATE TABLE dish (dish_id INTEGER PRIMARY KEY, dish_name VARCHAR(150), price NUMERIC(10,2))'))
        c.execute(text("INSERT INTO dish VALUES (77, 'Original dish', 1.25)"))
        c.execute(text('ALTER TABLE dish ADD COLUMN place_id INTEGER'))
    old_app = create_app({**app.config, 'SQLALCHEMY_DATABASE_URI': uri})
    try:
        with old_app.app_context():
            assert len(add_menu_provenance()['added']) == 5
            assert add_menu_provenance()['added'] == []
            row = db.session.execute(text('SELECT * FROM dish')).mappings().one()
            assert row['dish_id'] == 77 and row['dish_name'] == 'Original dish' and row['price'] == 1.25
            assert row['source_name'] is None and row['is_reference'] == 0
            assert any(i['name'] == 'uq_dish_source' for i in inspect(db.engine).get_indexes('dish'))
            db.session.remove()
            db.engine.dispose()
    finally:
        old_app.extensions['community_client'].close()
        engine.dispose()
