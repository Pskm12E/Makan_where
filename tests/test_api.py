import pytest
import os
import uuid
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from backend.passwords import verify_password as check_password_hash
from backend.mongo import community_db
from backend.app import create_app
from backend.models import (db, User, FoodPlace, Favourite, Content, Review,
                            Thread, Comment, ContentDish, Upvote, DiscoveryEvent)


@pytest.fixture
def app(tmp_path):
    mongo_uri = os.environ.get("MONGODB_TEST_URI")
    if not mongo_uri:
        pytest.skip("Set MONGODB_TEST_URI to a dedicated local MongoDB test administrator URI.")
    admin_engine = None
    uri = "sqlite:///" + str(tmp_path / "test.sqlite")
    if os.environ.get("MARIADB_TEST_ADMIN_URL"):
        admin_engine = create_engine(os.environ["MARIADB_TEST_ADMIN_URL"])
        test_schema = "makanwhere_test_" + uuid.uuid4().hex
        with admin_engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE `{test_schema}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        uri = make_url(os.environ["MARIADB_TEST_ADMIN_URL"]).set(database=test_schema).render_as_string(hide_password=False)
    mongo_schema = "makanwhere_test_" + uuid.uuid4().hex
    app = create_app({"TESTING": True, "PASSWORD_PEPPER": "test-only-pepper-" * 4,
        "MENU_IMPORT_API_KEY": "",
        "MONGODB_URI": mongo_uri, "MONGODB_DATABASE": mongo_schema, "SECRET_KEY": "test-only-secret-" * 4,
        "SQLALCHEMY_DATABASE_URI": uri,
        "SESSION_COOKIE_SECURE": False, "RATELIMIT_ENABLED": False})
    runner = app.test_cli_runner()
    assert runner.invoke(args=["init-db"]).exit_code == 0
    assert runner.invoke(args=["init-mongo"]).exit_code == 0
    result = runner.invoke(args=["seed-demo"])
    assert result.exit_code == 0, result.output
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
        assert mongo_schema.startswith("makanwhere_test_") and len(mongo_schema) == 48
        app.extensions["community_client"].drop_database(mongo_schema)
        app.extensions["community_client"].close()
    if admin_engine:
        assert test_schema.startswith('makanwhere_test_') and len(test_schema) == 48
        with admin_engine.connect() as conn:
            conn.execute(text(f"DROP DATABASE `{test_schema}`"))
        admin_engine.dispose()


class Browser:
    def __init__(self, app, name=None):
        self.client = app.test_client()
        self.csrf = self.client.get('/api/session').json['csrfToken']
        if name:
            response = self.send('POST', '/api/register', {"username": name, "email": f"{name}@example.com", "fullName": name,
                "password": "UniqueTestPassword!52", "role": "admin"})
            assert response.status_code == 201, response.json
            self.user = response.json['user']

    def send(self, method, path, data=None, headers=None):
        import re
        supplied = dict(headers or {})
        if method == 'POST' and path in ('/api/content', '/api/reviews'):
            supplied.setdefault('Idempotency-Key', uuid.uuid4().hex)
        if method in ('PATCH', 'DELETE') and re.fullmatch(r'/api/content/[0-9]+', path) and 'If-Match' not in supplied:
            current = self.client.get(path)
            supplied['If-Match'] = str(current.json.get('content', {}).get('revision', 1))
        response = self.client.open(path, method=method, json=data, headers={"X-CSRF-Token": self.csrf, **supplied})
        if response.is_json and response.json.get('csrfToken'):
            self.csrf = response.json['csrfToken']
        return response

    def review(self, place=1):
        response = self.send('POST', '/api/content', {"kind":"review", "placeId":place,
            "title":"A good lunch", "text":"Really enjoyed it.", "rating":5,
            "dishes":[{"id":1,"feedback":"Nice rice"}] if place == 1 else []})
        assert response.status_code == 201, response.json
        return response.json['content']['id']


def test_catalogue_and_safe_static_serving(app):
    client = app.test_client()
    assert client.get('/api/health').json['database'] == 'connected'
    places = client.get('/api/establishments').json['establishments']
    assert len(places) == 6
    assert places[0]['rating'] == 0
    assert places[0]['price'] == 5
    assert len(places[0]['menu']) == 3
    for path in ['/', '/auth.html', '/js/api.js', '/css/style.css']:
        assert client.get(path).status_code == 200
    for path in ['/backend/config.py', '/.env', '/.git/config', '/database/demo_places.json', '/js/../backend/config.py']:
        assert client.get(path).status_code == 404
    assert client.get('/api/session').headers['Cache-Control'] == 'no-store'


def test_passwords_and_sessions(app):
    browser = Browser(app, 'alice')
    assert browser.user['role'] == 'user'
    assert 'password' not in str(browser.user)
    with app.app_context():
        user = db.session.get(User, browser.user['id'])
        assert user.password_hash != 'UniqueTestPassword!52'
        assert check_password_hash(user.password_hash, 'UniqueTestPassword!52')
    assert browser.send('POST', '/api/logout').status_code == 200
    assert browser.client.get('/api/session').json['user'] is None
    browser.csrf = browser.client.get('/api/session').json['csrfToken']
    assert browser.send('POST','/api/login',{'identity':'ALICE@example.com','password':'wrong'}).status_code == 401
    assert browser.send('POST','/api/login',{'identity':'ALICE@example.com','password':'UniqueTestPassword!52'}).status_code == 200


def test_csrf_and_admin_permissions(app):
    guest, user = Browser(app), Browser(app, 'bob')
    assert user.client.post('/api/logout').status_code == 403
    assert guest.send('PUT','/api/favourites/1').status_code == 401
    for method, path in [('POST','/api/admin/establishments'),('PATCH','/api/admin/establishments/1'),('DELETE','/api/admin/establishments/1'),('GET','/api/admin/reports')]:
        assert user.send(method,path,{} if method != 'GET' else None).status_code == 403


def test_favourites_are_persistent_isolated_and_idempotent(app):
    alice, bob = Browser(app,'alice'), Browser(app,'bob')
    for _ in range(2):
        assert alice.send('PUT','/api/favourites/1').json['favourites'] == [1]
    assert alice.client.get('/api/session').json['favourites'] == [1]
    assert bob.client.get('/api/session').json['favourites'] == []
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(Favourite)) == 1
    assert alice.send('DELETE','/api/favourites/1').json['favourites'] == []


def test_reviews_ratings_ownership_and_soft_removal(app):
    alice, bob = Browser(app,'alice'), Browser(app,'bob')
    content_id = alice.review()
    path = f'/api/content/{content_id}'
    assert bob.send('PATCH',path,{'text':'stolen','title':'x','rating':1}).status_code == 403
    assert bob.send('DELETE',path).status_code == 403
    assert alice.client.get('/api/establishments/1').json['establishment']['rating'] == 5
    assert alice.send('PATCH',path,{'text':'Updated','title':'Updated title','rating':3}).status_code == 200
    assert alice.client.get('/api/establishments/1').json['establishment']['rating'] == 3
    assert alice.send('DELETE',path).status_code == 200
    assert alice.client.get('/api/reviews').json['content'] == []
    assert alice.client.get('/api/establishments/1').json['establishment']['rating'] == 0
    with app.app_context():
        assert community_db().content.find_one({'_id': content_id})['removed_by_id'] == alice.user['id']
        assert db.session.scalar(select(func.count()).select_from(Content)) == 0


def test_invalid_content_is_rolled_back_and_dishes_must_match(app):
    alice = Browser(app,'alice')
    for changes in [{'rating':6},{'rating':1.5},{'dishes':[{'id':4}]},{'dishes':[{'id':1},{'id':1}]}]:
        data = {'kind':'review','placeId':1,'text':'Text','title':'Title','rating':5,**changes}
        assert alice.send('POST','/api/content',data).status_code == 400
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(Content)) == 0
        assert db.session.scalar(select(func.count()).select_from(Review)) == 0


def test_threads_comments_and_subtype_constraints(app):
    alice = Browser(app,'alice')
    thread_id = alice.send('POST','/api/content',{'kind':'thread','placeId':1,'title':'Lunch?','text':'What to order?'}).json['content']['id']
    body = {'kind':'comment','placeId':1,'threadId':thread_id,'text':'Chicken rice.'}
    assert alice.send('POST','/api/content',{**body,'placeId':2}).status_code == 400
    assert alice.send('POST','/api/content',body).status_code == 201
    with app.app_context():
        db.session.add(Review(content_id=thread_id,rating=5))
        with pytest.raises(IntegrityError): db.session.commit()
        db.session.rollback()
    assert len(alice.client.get('/api/content?place_id=1').json['content']) == 2
    alice.send('DELETE', f'/api/content/{thread_id}')
    assert alice.client.get('/api/content?place_id=1').json['content'] == []


def test_upvotes_reports_and_admin_resolution(app):
    alice, bob = Browser(app,'alice'), Browser(app,'bob')
    content_id = alice.review()
    path = f'/api/content/{content_id}'
    for _ in range(2):
        assert bob.send('PUT',path+'/upvote').json['content']['upvoteCount'] == 1
    report = bob.send('POST',path+'/reports',{'reason':'Needs review'}).json['id']
    assert bob.send('PATCH',f'/api/admin/reports/{report}',{'status':'resolved','note':'Checked'}).status_code == 403
    with app.app_context():
        db.session.get(User,bob.user['id']).role = 'admin'; db.session.commit()
    assert bob.send('PATCH',path,{'text':'Admin edit','title':'x','rating':1}).status_code == 403
    assert bob.send('DELETE',path).status_code == 200
    assert bob.send('PATCH',f'/api/admin/reports/{report}',{'status':'resolved','note':'Removed'}).status_code == 200
    assert bob.client.get('/api/admin/reports').json['reports'] == []


def test_admin_crud_menu_and_derived_price(app):
    admin = Browser(app,'admin')
    with app.app_context():
        db.session.get(User,admin.user['id']).role = 'admin'; db.session.commit()
    data = {'name':'Test place','area':'New area','category':'Cafe','cuisine':'Chinese, Japanese','address':'123 Test Road'}
    result = admin.send('POST','/api/admin/establishments',data)
    assert result.status_code == 201, result.json
    place = result.json['establishment']
    assert place['price'] is None and place['rating'] == 0
    path = f"/api/admin/establishments/{place['id']}"
    assert admin.send('POST',path+'/dishes',{'name':'Noodles','price':'7.25','dietary':''}).status_code == 201
    assert admin.client.get(f"/api/establishments/{place['id']}").json['establishment']['price'] == 7.25
    assert admin.send('PATCH',path,{**data,'name':'Updated place'}).status_code == 200
    assert admin.send('DELETE',path).status_code == 200
    assert admin.client.get(f"/api/establishments/{place['id']}").status_code == 404


def test_discovery_guests_and_constraints(app):
    guest = Browser(app)
    assert guest.send('POST','/api/events',{'type':'place_view'}).status_code == 400
    assert guest.send('POST','/api/events',{'type':'search'}).status_code == 201
    assert guest.send('POST','/api/events',{'type':'place_view','placeId':1}).status_code == 201
    assert guest.client.get('/api/analytics').json['discovery'] == {'search':1,'place_view':1}
    with app.app_context():
        assert all(event.user_id is None for event in db.session.scalars(select(DiscoveryEvent)))
        assert len(db.metadata.tables) == 21


def test_pagination_and_initialization_preserves_data(app):
    client = app.test_client()
    first = client.get('/api/establishments?limit=2').json
    second = client.get(f"/api/establishments?limit=2&cursor={first['nextCursor']}").json
    assert {p['id'] for p in first['establishments']}.isdisjoint(p['id'] for p in second['establishments'])
    runner = app.test_cli_runner()
    assert runner.invoke(args=['init-db']).exit_code == 0
    assert runner.invoke(args=['seed-demo']).exit_code != 0
    assert len(client.get('/api/establishments').json['establishments']) == 6
