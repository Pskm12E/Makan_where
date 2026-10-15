import json
from sqlalchemy import text
from test_api import app, Browser
from backend.models import db, User, Dish, ContentDish
from backend.mongo import community_db


def administrator(app):
    browser = Browser(app, 'administrator')
    with app.app_context():
        db.session.get(User, browser.user['id']).role = 'admin'
        db.session.commit()
    return browser


def test_schema_requires_admin_and_reflects_only_live_application_tables(app):
    guest, user = Browser(app), Browser(app, 'reader')
    assert guest.client.get('/api/admin/schema').status_code == 401
    assert user.client.get('/api/admin/schema').status_code == 403
    admin = administrator(app)
    with app.app_context():
        db.session.execute(text('CREATE TABLE unrelated_private_table (secret VARCHAR(20))'))
        db.session.execute(text('ALTER TABLE area ADD COLUMN inspection_note VARCHAR(20)'))
        db.session.commit()
    response = admin.client.get('/api/admin/schema')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    result = response.json
    tables = {table['name']: table for table in result['tables']}
    assert len(tables) == 17 and 'unrelated_private_table' not in tables
    assert any(c['name'] == 'inspection_note' for c in tables['area']['columns'])
    assert tables['favourite']['primaryKey'] == ['user_id', 'place_id']
    assert any(f['table'] == 'food_place' for f in tables['dish']['foreignKeys'])
    assert tables['review']['checks']
    assert result['source'] == 'live database metadata' and result['readOnly']
    assert result['missingTables'] == []
    assert result['mongoDB']['connected'] is True
    assert 'UniqueTestPassword!52' not in json.dumps(result)
    assert 'SQLALCHEMY_DATABASE_URI' not in json.dumps(result)
    assert admin.send('POST', '/api/admin/schema', {}).status_code == 405


def test_admin_signin_enforces_role_without_creating_admin_accounts(app):
    user = Browser(app, 'reader')
    user.send('POST', '/api/logout')
    user.csrf = user.client.get('/api/session').json['csrfToken']
    credentials = {'identity': 'reader', 'password': 'UniqueTestPassword!52', 'adminOnly': True}
    assert user.send('POST', '/api/login', credentials).status_code == 403
    assert user.client.get('/api/session').json['user'] is None
    assert user.send('POST', '/api/login', {**credentials, 'adminOnly': False}).status_code == 200
    admin = administrator(app)
    admin.send('POST', '/api/logout')
    admin.csrf = admin.client.get('/api/session').json['csrfToken']
    response = admin.send('POST', '/api/login', {**credentials, 'identity': 'administrator'})
    assert response.status_code == 200 and response.json['user']['role'] == 'admin'


def test_dish_changes_require_admin_csrf_and_matching_place(app):
    guest, user, admin = Browser(app), Browser(app, 'reader'), administrator(app)
    path = '/api/admin/establishments/1/dishes/1'
    data = {'name': 'Updated', 'price': '4.25'}
    for method in ['PATCH', 'DELETE']:
        assert guest.send(method, path, data).status_code == 401
        assert user.send(method, path, data).status_code == 403
    assert admin.client.delete(path).status_code == 403
    assert admin.send('PATCH', '/api/admin/establishments/2/dishes/1', data).status_code == 404
    assert admin.send('DELETE', '/api/admin/establishments/2/dishes/1').status_code == 404
    with app.app_context():
        assert db.session.get(Dish, 1).is_available


def test_dish_edit_remove_restore_preserves_history_and_updates_public_menu(app):
    user, admin = Browser(app, 'reviewer'), administrator(app)
    content_id = user.review()
    path = '/api/admin/establishments/1/dishes/1'
    data = {'name': 'Updated chicken rice', 'price': '1.25', 'dietary': 'No peanuts'}
    assert admin.send('PATCH', path, data).status_code == 200
    assert user.client.get('/api/establishments/1').json['establishment']['price'] == 1.25
    assert admin.send('DELETE', path).status_code == 200
    assert admin.send('DELETE', path).status_code == 200
    place = user.client.get('/api/establishments/1').json['establishment']
    assert not any(d['id'] == 1 for d in place['menu'])
    assert place['price'] != 1.25
    admin_menu = admin.client.get('/api/establishments/1').json['establishment']['menu']
    assert any(d['id'] == 1 and not d['availability'] for d in admin_menu)
    review = user.client.get('/api/reviews?place_id=1').json['content'][0]
    assert review['dishes'][0]['name'] == data['name']
    with app.app_context():
        assert community_db().content.find_one({'_id': content_id})['dishes'][0]['dish_id'] == 1
    assert user.send('POST', '/api/reviews', {'placeId': 1, 'title': 'New', 'text': 'Text',
                                            'rating': 4, 'dishes': [{'id': 1}]}).status_code == 400
    assert admin.send('PATCH', path, {**data, 'availability': True}).status_code == 200
    assert user.client.get('/api/establishments/1').json['establishment']['price'] == 1.25


def test_invalid_dish_edits_preserve_saved_values(app):
    admin = administrator(app)
    path = '/api/admin/establishments/1/dishes/1'
    with app.app_context():
        before = db.session.get(Dish, 1)
        name, price = before.dish_name, before.price
    for change in [{'price': '-1'}, {'price': 'NaN'}, {'price': '1.234'}, {'availability': 'false'}, {'dietary': 'x' * 81}]:
        data = {'name': 'Should not persist', 'price': '2.00', **change}
        assert admin.send('PATCH', path, data).status_code == 400
        with app.app_context():
            dish = db.session.get(Dish, 1)
            assert dish.dish_name == name and dish.price == price and dish.is_available
