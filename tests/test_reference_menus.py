"""Unpriced published items remain real, venue-scoped review references."""
from datetime import datetime
from decimal import Decimal
import pytest
from sqlalchemy import MetaData, create_engine, event, inspect, select
from sqlalchemy.exc import DBAPIError
from test_api import app, Browser
from test_admin import administrator
from test_menu_imports import menu_for, preview_and_apply
from backend.models import db, Dish, FoodPlace, MenuEntry, MenuPublication
from backend.listing_details import enrich_listings
from backend.reference_menus import import_menu_highlights, allow_unpriced_references


def test_published_names_become_reviewable_without_inventing_prices(app):
    admin, author = administrator(app), Browser(app, 'dish_reviewer')
    with app.app_context():
        place = db.session.get(FoodPlace, 1)
        place.place_name, place.is_sample, place.enrichment = "McDonald's", False, None
        db.session.commit()
        enrich_listings(apply=True)
        before = db.session.query(Dish).count()
        preview = import_menu_highlights()
        assert preview['added'] == 45 and db.session.query(Dish).count() == before
        assert import_menu_highlights(apply=True)['added'] == 45
        assert import_menu_highlights(apply=True)['added'] == 0
    menu = author.client.get('/api/establishments/1').json['establishment']['menu']
    big_mac = next(d for d in menu if d['name'] == 'Big Mac')
    assert big_mac['price'] is None and big_mac['isReference'] and big_mac['sourceUrl']
    result = author.send('POST', '/api/content', {'kind':'review', 'placeId':1, 'title':'Lunch',
        'text':'I ordered a burger.', 'rating':4, 'dishes':[{'id':big_mac['id'],'feedback':'Enjoyed it.'}]})
    assert result.status_code == 201, result.json
    assert result.json['content']['dishes'] == [{'id':big_mac['id'],'name':'Big Mac','feedback':'Enjoyed it.'}]
    wrong_place = author.send('POST', '/api/content', {'kind':'review', 'placeId':2, 'title':'Wrong venue',
        'text':'Must reject this link.', 'rating':4, 'dishes':[{'id':big_mac['id'],'feedback':'Wrong venue'}]})
    assert wrong_place.status_code == 400
    insights = author.client.get('/api/analytics').json
    assert big_mac['id'] not in {d['id'] for d in insights['affordableItems']}
    # Local edits and removal do not cause a subsequent source import to restore it.
    path = f"/api/admin/establishments/1/dishes/{big_mac['id']}"
    assert admin.send('PATCH', path, {'name':'Outlet burger label','price':'','dietary':'','description':''}).status_code == 200
    assert admin.send('DELETE', path).status_code == 200
    with app.app_context():
        assert import_menu_highlights(apply=True)['added'] == 0
        dish = db.session.get(Dish, big_mac['id'])
        assert dish.dish_name == 'Outlet burger label' and dish.price is None and not dish.is_available
    assert author.send('POST', '/api/content', {'kind':'review','placeId':1,'title':'Unavailable',
        'text':'Cannot select a removed item.', 'rating':3,'dishes':[{'id':big_mac['id']}]}).status_code == 400


def test_unpriced_shared_entries_and_known_zero_price_override(app):
    admin = administrator(app)
    menu = menu_for(app, (1,2))
    menu['items'][0]['price'] = None
    response = preview_and_apply(admin, menu)
    assert response.status_code == 200, response.json
    dishes = []
    for pid in (1,2):
        place = admin.client.get(f'/api/establishments/{pid}').json['establishment']
        dishes.append(next(d for d in place['menu'] if d['name'] == 'Imported test dish'))
        assert dishes[-1]['price'] is None
    assert admin.send('PATCH',f"/api/admin/establishments/1/dishes/{dishes[0]['id']}",
        {'name':'Imported test dish','price':'0.00','dietary':''}).status_code == 200
    with app.app_context():
        first,second=(db.session.get(Dish,d['id']) for d in dishes)
        assert first.price == Decimal('0.00') and second.price is None
        assert first.menu_entry.reference_price is None
    assert preview_and_apply(admin, menu).json['added'] == 0


def test_highlights_respect_changed_source_and_existing_dish_names(app):
    with app.app_context():
        place = db.session.get(FoodPlace, 1)
        place.place_name, place.is_sample, place.enrichment = "McDonald's", False, None
        db.session.commit()
        enrich_listings(apply=True)
        original = dict(place.enrichment)
        place.enrichment = {**original, 'menuUrl':'https://example.com/custom-menu'}
        db.session.commit()
        assert import_menu_highlights(apply=True)['added'] == 0
        place.enrichment = original
        db.session.add(Dish(place_id=1,dish_name='Big Mac',price=Decimal('7.50'),is_available=False))
        db.session.commit()
        assert import_menu_highlights(apply=True)['added'] == 44
        existing = list(db.session.scalars(select(Dish).where(Dish.place_id==1,Dish.legacy_dish_name=='Big Mac')))
        assert len(existing)==1 and existing[0].price==Decimal('7.50') and not existing[0].is_available


def test_existing_reference_price_upgrade_preserves_custom_data(app):
    admin = administrator(app)
    assert preview_and_apply(admin, menu_for(app)).status_code == 200
    with app.app_context():
        entry = db.session.scalar(select(MenuEntry))
        identity = (entry.publication_id, entry.source_item_id)
        db.session.remove()
        if db.engine.dialect.name in {'mysql','mariadb'}:
            with db.engine.begin() as conn:
                conn.exec_driver_sql('ALTER TABLE menu_entry MODIFY COLUMN reference_price NUMERIC(10, 2) NOT NULL')
                conn.exec_driver_sql("ALTER TABLE menu_entry ADD COLUMN custom_note VARCHAR(30) DEFAULT 'Keep me'")
            assert allow_unpriced_references(db.engine)
            with db.engine.connect() as conn:
                assert conn.exec_driver_sql('SELECT custom_note FROM menu_entry').scalar_one() == 'Keep me'
        assert not allow_unpriced_references(db.engine)
        assert next(c for c in inspect(db.engine).get_columns('menu_entry') if c['name']=='reference_price')['nullable']
        entry = db.session.get(MenuEntry, identity)
        assert entry.reference_price == Decimal('6.25')
        entry.reference_price = None
        db.session.commit()
        menu = admin.client.get('/api/establishments/1').json['establishment']['menu']
        assert next(d for d in menu if d['name']=='Imported test dish')['price'] is None


def test_sqlite_price_upgrade_preserves_references_views_triggers_and_columns(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path/'old-reference.sqlite'))
    metadata = MetaData()
    MenuPublication.__table__.to_metadata(metadata)
    old = MenuEntry.__table__.to_metadata(metadata)
    old.c.reference_price.nullable = False
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')
        conn.exec_driver_sql('ALTER TABLE menu_entry ADD COLUMN custom_note VARCHAR(30)')
        conn.execute(metadata.tables['menu_publication'].insert().values(publication_id=11, source_name='Test',
            source_url='https://example.com/menu',observed_at=datetime(2026,10,4),payload_sha256='a'*64,is_reference=True))
        conn.execute(old.insert().values(publication_id=11,source_item_id='a',item_name='Keep item',
            reference_price=Decimal('5.50'),description='',dietary_label=''))
        conn.exec_driver_sql("UPDATE menu_entry SET custom_note='Keep value'")
        conn.exec_driver_sql('CREATE TABLE dish (dish_id INTEGER PRIMARY KEY, publication_id INTEGER, source_item_id VARCHAR(100), FOREIGN KEY (publication_id,source_item_id) REFERENCES menu_entry(publication_id,source_item_id))')
        conn.exec_driver_sql("INSERT INTO dish VALUES (77,11,'a')")
        conn.exec_driver_sql('CREATE INDEX idx_custom_reference_name ON menu_entry(item_name)')
        conn.exec_driver_sql('CREATE VIEW custom_reference_view AS SELECT e.reference_price FROM menu_entry e JOIN dish d ON d.publication_id=e.publication_id AND d.source_item_id=e.source_item_id')
        conn.exec_driver_sql("CREATE TRIGGER custom_reference_guard BEFORE UPDATE ON menu_entry WHEN NEW.item_name='Blocked' BEGIN SELECT RAISE(ABORT,'guard retained'); END")
    def fail_during_rebuild(conn, cursor, statement, parameters, context, executemany):
        if statement == 'DROP TABLE menu_entry':
            raise RuntimeError('injected migration failure')
    event.listen(engine, 'before_cursor_execute', fail_during_rebuild)
    try:
        with pytest.raises(RuntimeError, match='injected migration failure'):
            allow_unpriced_references(engine)
    finally:
        event.remove(engine, 'before_cursor_execute', fail_during_rebuild)
    with engine.connect() as conn:
        assert conn.exec_driver_sql('SELECT reference_price FROM custom_reference_view').scalar_one()==5.5
        assert conn.exec_driver_sql('PRAGMA foreign_keys').scalar()==1
        assert not next(c for c in inspect(conn).get_columns('menu_entry') if c['name']=='reference_price')['nullable']
        assert '_menu_entry_price_upgrade' not in inspect(conn).get_table_names()
    assert allow_unpriced_references(engine)
    assert not allow_unpriced_references(engine)
    with engine.begin() as conn:
        assert conn.exec_driver_sql('PRAGMA foreign_keys').scalar()==1
        assert conn.exec_driver_sql('SELECT custom_note FROM menu_entry').scalar_one()=='Keep value'
        assert conn.exec_driver_sql('SELECT dish_id FROM dish').scalar_one()==77
        conn.exec_driver_sql('UPDATE menu_entry SET reference_price=NULL')
        assert conn.exec_driver_sql('SELECT reference_price FROM custom_reference_view').scalar_one() is None
        assert not conn.exec_driver_sql('PRAGMA foreign_key_check').all()
    for sql in ("UPDATE menu_entry SET item_name='Blocked'",'UPDATE menu_entry SET reference_price=-1',"INSERT INTO dish VALUES (78,11,'missing')"):
        with pytest.raises(DBAPIError), engine.begin() as conn:
            conn.exec_driver_sql(sql)
    assert 'idx_custom_reference_name' in {i['name'] for i in inspect(engine).get_indexes('menu_entry')}
    engine.dispose()
