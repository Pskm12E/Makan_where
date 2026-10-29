import os
import pytest
from sqlalchemy import inspect, text
from test_api import app, Browser
from test_admin import administrator
from backend.models import db, User

pytestmark = pytest.mark.skipif(not os.environ.get('MARIADB_TEST_ADMIN_URL'), reason='Schema editing requires an isolated MariaDB test database')


def propose(browser, change):
    result = browser.send('POST', '/api/admin/schema/preview', {'change': change})
    assert result.status_code == 200, result.json
    return {'change': change, 'previewToken': result.json['previewToken']}


def execute(browser, change):
    result = browser.send('POST', '/api/admin/schema/apply', propose(browser, change))
    assert result.status_code == 200, result.json


def test_editor_changes_real_metadata_and_enforces_foreign_keys(app):
    admin = administrator(app)
    creation = {'operation': 'create_table', 'table': 'custom_booking', 'column': 'booking_id'}
    proposal = propose(admin, creation)
    with app.app_context():
        assert 'custom_booking' not in inspect(db.engine).get_table_names()
    assert admin.send('POST', '/api/admin/schema/apply', proposal).status_code == 200
    assert admin.send('POST', '/api/admin/schema/apply', proposal).status_code == 409
    execute(admin, {'operation':'add_column', 'table':'custom_booking', 'column':'place_id', 'type':'integer'})
    execute(admin, {'operation':'add_foreign_key', 'table':'custom_booking', 'column':'place_id', 'parentTable':'food_place', 'parentColumn':'place_id'})
    execute(admin, {'operation':'add_column', 'table':'food_place', 'column':'custom_notes', 'type':'text'})
    execute(admin, {'operation':'add_column', 'table':'user', 'column':'custom_editor_note', 'type':'text'})
    tables = {t['name']: t for t in admin.client.get('/api/admin/schema').json['tables']}
    assert tables['custom_booking']['primaryKey'] == ['booking_id']
    assert tables['custom_booking']['foreignKeys'][0]['table'] == 'food_place'
    assert next(c for c in tables['food_place']['columns'] if c['name'] == 'custom_notes')['nullable']
    with app.app_context():
        with db.engine.begin() as connection:
            connection.execute(text('INSERT INTO custom_booking(place_id) VALUES (1)'))
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            with db.engine.begin() as connection:
                connection.execute(text('INSERT INTO custom_booking(place_id) VALUES (2147483647)'))
        assert db.session.execute(text('SELECT COUNT(*) FROM food_place')).scalar() == 6


def test_editor_requires_admin_csrf_bound_preview_and_rejects_injection(app):
    guest, user, admin = Browser(app), Browser(app, 'reader'), administrator(app)
    change = {'operation':'create_table', 'table':'custom_safe', 'column':'id'}
    for endpoint in ('preview','apply'):
        path = '/api/admin/schema/' + endpoint
        assert guest.send('POST', path, {'change':change}).status_code == 401
        assert user.send('POST', path, {'change':change}).status_code == 403
        assert admin.client.post(path, json={'change':change}).status_code == 403
    assert admin.send('POST','/api/admin/schema/apply',{'change':change}).status_code == 400
    for bad in ({**change, 'table':'user'}, {**change,'table':'custom_x; DROP TABLE user'},
                {**change,'column':'id` INT); DROP TABLE user; --'},
                {'operation':'drop_table','table':'food_place'},
                {'operation':'add_column','table':'user','column':'role2','type':'text'},
                {'operation':'add_column','table':'food_place','column':'custom_x','type':'INT; DROP TABLE user'}):
        assert admin.send('POST','/api/admin/schema/preview',{'change':bad}).status_code == 400
    proposal = propose(admin, change)
    assert admin.send('POST','/api/admin/schema/apply',{**proposal,'change':{**change,'column':'changed'}}).status_code == 409
    with app.app_context():
        db.session.get(User,user.user['id']).role='admin'; db.session.commit()
    assert user.send('POST','/api/admin/schema/apply',proposal).status_code == 403
    assert admin.send('POST','/api/admin/schema/apply',{**proposal,'previewToken':'forged'}).status_code == 409


def test_editor_rejects_stale_structure_and_orphaned_values(app):
    admin = administrator(app)
    execute(admin, {'operation':'create_table','table':'custom_child','column':'id'})
    execute(admin, {'operation':'add_column','table':'custom_child','column':'place_id','type':'integer'})
    proposal = propose(admin, {'operation':'add_column','table':'custom_child','column':'notes','type':'text'})
    execute(admin, {'operation':'add_column','table':'custom_child','column':'other','type':'text'})
    assert admin.send('POST','/api/admin/schema/apply',proposal).status_code == 409
    with app.app_context():
        with db.engine.begin() as connection:
            connection.execute(text('INSERT INTO custom_child(place_id) VALUES (2147483647)'))
    foreign = propose(admin, {'operation':'add_foreign_key','table':'custom_child','column':'place_id','parentTable':'food_place','parentColumn':'place_id'})
    assert admin.send('POST','/api/admin/schema/apply',foreign).status_code == 409
    with app.app_context():
        assert inspect(db.engine).get_foreign_keys('custom_child') == []
        assert db.session.execute(text('SELECT COUNT(*) FROM custom_child')).scalar() == 1


def test_editor_works_without_schema_wide_record_access(app):
    import secrets, uuid
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from backend.app import create_app
    admin = administrator(app)
    name = 'schema_test_' + uuid.uuid4().hex[:16]
    password = secrets.token_urlsafe(24)
    admin_engine = create_engine(os.environ['MARIADB_TEST_ADMIN_URL'])
    url = make_url(app.config['SQLALCHEMY_DATABASE_URI'])
    database = url.database
    limited = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(text("CREATE USER :name@'localhost' IDENTIFIED BY :password"), {'name': name, 'password': password})
            connection.execute(text(f"GRANT CREATE,ALTER,REFERENCES ON `{database}`.* TO '{name}'@'localhost'"))
            for table in db.metadata.tables:
                connection.execute(text(f"GRANT SELECT,INSERT,UPDATE,DELETE ON `{database}`.`{table}` TO '{name}'@'localhost'"))
        limited = create_app({**dict(app.config), 'SQLALCHEMY_DATABASE_URI': url.set(username=name, password=password).render_as_string(hide_password=False)})
        browser = Browser(limited)
        assert browser.send('POST','/api/login',{'identity':'administrator','password':'UniqueTestPassword!52'}).status_code == 200
        execute(browser, {'operation':'create_table','table':'custom_limited','column':'id'})
        execute(browser, {'operation':'add_column','table':'custom_limited','column':'place_id','type':'integer'})
        execute(browser, {'operation':'add_foreign_key','table':'custom_limited','column':'place_id','parentTable':'food_place','parentColumn':'place_id'})
        tables = {t['name']:t for t in browser.client.get('/api/admin/schema').json['tables']}
        assert tables['custom_limited']['foreignKeys'][0]['table'] == 'food_place'
        from sqlalchemy.exc import OperationalError
        with limited.app_context():
            with pytest.raises(OperationalError):
                db.session.execute(text('SELECT * FROM custom_limited'))
            db.session.rollback()
    finally:
        if limited:
            with limited.app_context():
                db.session.remove(); db.engine.dispose()
            limited.extensions['community_client'].close()
        with admin_engine.begin() as connection:
            connection.execute(text("DROP USER IF EXISTS :name@'localhost'"), {'name': name})
        admin_engine.dispose()
