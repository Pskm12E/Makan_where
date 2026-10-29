"""Promote retained, attributed menu names to reviewable SQL offerings.

Unknown source prices stay NULL in the shared entry. An offering keeps its
normal dish_id, so Mongo feedback still validates against its venue in SQL.
"""
import hashlib
import json
import re
from sqlalchemy import inspect, select
from .config import BASE_DIR
from .models import db, Dish, FoodPlace, PopulationRun


def allow_unpriced_references(engine):
    """Offline, repeatable upgrade of the former NOT NULL reference price."""
    inspector = inspect(engine)
    if 'menu_entry' not in inspector.get_table_names():
        return False
    column = next(c for c in inspector.get_columns('menu_entry') if c['name'] == 'reference_price')
    if column['nullable']:
        return False
    if engine.dialect.name in {'mysql', 'mariadb'}:
        with engine.begin() as connection:
            connection.exec_driver_sql('ALTER TABLE menu_entry MODIFY COLUMN reference_price NUMERIC(10, 2) NULL')
        return True
    if engine.dialect.name != 'sqlite':
        raise ValueError('Unpriced reference migration supports MariaDB/MySQL and SQLite.')
    # SQLite needs a table rebuild. Preserve the actual DDL, including custom
    # columns, indexes, triggers and views; do all replacements in one transaction.
    with engine.connect() as connection:
        enabled = connection.exec_driver_sql('PRAGMA foreign_keys').scalar()
        if connection.exec_driver_sql('PRAGMA foreign_key_check').all():
            raise ValueError('Repair existing SQLite foreign-key violations before migrating.')
        original = connection.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type='table' AND name='menu_entry'").scalar_one()
        changed, count = re.subn(r'(\breference_price\s+NUMERIC\(10,\s*2\))\s+NOT NULL\b', r'\1', original, flags=re.I)
        if count != 1:
            raise ValueError('Unexpected menu_entry price definition; inspect before migrating.')
        changed, count = re.subn(r'^CREATE TABLE\s+(?:menu_entry|"menu_entry")\s*\(', 'CREATE TABLE "_menu_entry_price_upgrade" (', changed, count=1, flags=re.I)
        if count != 1 or '_menu_entry_price_upgrade' in inspect(connection).get_table_names():
            raise ValueError('Unexpected SQLite migration state; existing data was not changed.')
        objects = connection.exec_driver_sql("SELECT type,name,sql FROM sqlite_master WHERE (type IN ('view','trigger') OR (type='index' AND tbl_name='menu_entry')) AND sql IS NOT NULL").all()
        connection.commit()
        connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
        connection.commit()
        quote = engine.dialect.identifier_preparer.quote
        try:
            with connection.begin():
                # sqlite3 legacy transaction mode otherwise auto-commits DDL
                # before the first INSERT, which would break failure rollback.
                if not connection.connection.driver_connection.in_transaction:
                    connection.exec_driver_sql('BEGIN IMMEDIATE')
                for kind, name, sql in objects:
                    if kind in {'view', 'trigger'}:
                        connection.exec_driver_sql(f'DROP {kind.upper()} {quote(name)}')
                connection.exec_driver_sql(changed)
                connection.exec_driver_sql('INSERT INTO _menu_entry_price_upgrade SELECT * FROM menu_entry')
                connection.exec_driver_sql('DROP TABLE menu_entry')
                connection.exec_driver_sql('ALTER TABLE _menu_entry_price_upgrade RENAME TO menu_entry')
                for kind, name, sql in objects:
                    connection.exec_driver_sql(sql)
                if connection.exec_driver_sql('PRAGMA foreign_key_check').all():
                    raise ValueError('Reference migration failed its foreign-key check.')
        finally:
            connection.exec_driver_sql(f'PRAGMA foreign_keys={int(enabled)}')
            connection.commit()
    return True


def import_menu_highlights(*, apply=False):
    """Import only retained source names matching each venue's current source.

    Existing names, edits, prices and removed offerings are retained. This is
    an offline setup/import operation; public GET requests never create data.
    """
    from .menu_imports import normalise_menu, digest
    from .catalogue_design import publication_for, bind_offering
    chains = json.loads((BASE_DIR / 'data/enrichment/chain_links.json').read_text(encoding='utf-8'))
    summary = {'added': 0, 'retained': 0, 'venues': 0, 'sources': [], 'applied': apply}
    for chain in chains:
        if not chain.get('menuHighlights'):
            continue
        places = list(db.session.scalars(select(FoodPlace).where(FoodPlace.archived_at.is_(None),
            FoodPlace.is_sample.is_(False), FoodPlace.place_name.in_(chain['names'])).order_by(FoodPlace.place_id)))
        places = [p for p in places if (p.enrichment or {}).get('menuHighlightsSource') == chain['sourceUrl']
                  and (p.enrichment or {}).get('menuUrl') == chain['menuUrl']]
        if not places:
            continue
        items = [{'sourceId': 'name-' + hashlib.sha256(name.casefold().encode()).hexdigest()[:32],
                  'name': name, 'price': None} for name in chain['menuHighlights']]
        menu = normalise_menu({'sourceName': chain['names'][0] + ' Singapore published menu names',
            'sourceUrl': chain['sourceUrl'], 'observedAt': chain['observedAt'] + 'T00:00:00+08:00',
            'currency': 'SGD', 'isReference': True, 'items': items,
            'places': [{'id': p.place_id, 'name': p.place_name, 'sourceId': p.source_id or ''} for p in places[:100]]})
        new = []
        for place in places:
            existing_names = {dish.dish_name.casefold() for dish in place.dishes}
            existing_source_ids = {dish.source_item_id for dish in place.dishes if dish.source_url == menu['sourceUrl']}
            added_here = 0
            for item in menu['items']:
                if item['name'].casefold() in existing_names or item['sourceId'] in existing_source_ids:
                    summary['retained'] += 1
                    continue
                new.append((place.place_id, item))
                added_here += 1
            summary['venues'] += bool(added_here)
        summary['added'] += len(new)
        summary['sources'].append({'sourceUrl': menu['sourceUrl'], 'added': len(new), 'price': None})
        if apply and new:
            publication = publication_for(menu)
            for place_id, item in new:
                dish = Dish(place_id=place_id, source_item_id=item['sourceId'], is_available=True)
                bind_offering(dish, publication, item['sourceId'])
                db.session.add(dish)
            key = digest({'source': publication.payload_sha256, 'offerings': [(pid, i['sourceId']) for pid, i in new]})
            db.session.add(PopulationRun(run_key='highlights:' + key, details={'operation': 'menu_import',
                'sourceName': menu['sourceName'], 'sourceUrl': menu['sourceUrl'], 'observedAt': menu['observedAt'],
                'isReference': True, 'actor': 'retained-menu-highlights', 'added': len(new),
                'placeIds': sorted({pid for pid, item in new})}))
    if apply:
        db.session.commit()
        db.session.expire_all()
    return summary
