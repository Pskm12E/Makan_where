"""Shared menu facts with stable outlet/dish identities and repeatable upgrades.

The physical `dish` table is the outlet offering. Its original columns remain
for manual dishes and upgrade compatibility; shared offerings clear those
payloads and read menu_entry plus explicit outlet overrides instead.
"""
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from sqlalchemy import inspect, select, text, or_
from .config import BASE_DIR
from .models import db, Dish, FoodPlace, MenuPublication, MenuEntry, Tag, PlaceTag, now

EFFECTIVE_MENU_SQL = '''SELECT d.dish_id, d.place_id, d.is_available,
CASE WHEN d.publication_id IS NULL THEN d.dish_name ELSE COALESCE(d.dish_name_override,e.item_name) END AS dish_name,
CASE WHEN d.publication_id IS NULL THEN d.price ELSE COALESCE(d.price_override,e.reference_price) END AS price,
CASE WHEN d.publication_id IS NULL THEN d.description ELSE COALESCE(d.description_override,e.description) END AS description,
CASE WHEN d.publication_id IS NULL THEN d.dietary_label ELSE COALESCE(d.dietary_label_override,e.dietary_label) END AS dietary_label
FROM dish d LEFT JOIN menu_entry e ON e.publication_id=d.publication_id AND e.source_item_id=d.source_item_id'''


def publication_for(menu):
    facts = {k: menu[k] for k in ('sourceName', 'sourceUrl', 'observedAt', 'isReference')}
    facts['items'] = sorted(menu['items'], key=lambda i: i['sourceId'])
    fingerprint = hashlib.sha256(json.dumps(facts, sort_keys=True, default=str).encode()).hexdigest()
    publication = db.session.scalar(select(MenuPublication).where(MenuPublication.payload_sha256 == fingerprint))
    if publication:
        return publication
    publication = MenuPublication(source_name=menu['sourceName'], source_url=menu['sourceUrl'],
        observed_at=datetime.fromisoformat(menu['observedAt'].replace('Z', '+00:00')).replace(tzinfo=None),
        payload_sha256=fingerprint, is_reference=menu['isReference'])
    db.session.add(publication)
    db.session.flush()
    for item in facts['items']:
        db.session.add(MenuEntry(publication=publication, source_item_id=item['sourceId'],
            item_name=item['name'], reference_price=Decimal(str(item['price'])) if item['price'] is not None else None,
            description=item.get('description', ''), dietary_label=item.get('dietary', '')))
    db.session.flush()
    return publication


def bind_offering(dish, publication, source_id, preserve=False):
    values = {name: getattr(dish, name) for name in ('dish_name', 'description', 'price', 'dietary_label')} if preserve else {}
    edited = preserve and dish.source_observed_at is None
    entry = db.session.get(MenuEntry, (publication.publication_id, source_id))
    dish.menu_entry = entry
    for name, value in values.items():
        setattr(dish, name, value)
    dish.legacy_dish_name = dish.legacy_description = dish.legacy_dietary_label = ''
    dish.legacy_price = 0
    dish.legacy_source_name = dish.legacy_source_url = dish.legacy_source_observed_at = None
    dish.legacy_is_reference = False
    if edited or any(getattr(dish, n + '_override') is not None for n in values):
        dish.menu_edited_at = now()


def upgrade_catalogue_design():
    """Run offline after backup. No row IDs, manual dishes or overrides reset."""
    inspector = inspect(db.engine)
    if 'food_place' not in inspector.get_table_names():
        return {'status': 'fresh schema; init-db creates the normalized tables'}
    from .migrations import add_catalogue_provenance, add_menu_provenance, add_listing_details
    add_catalogue_provenance()
    add_menu_provenance()
    add_listing_details()
    invalid = db.session.execute(text("SELECT place_id FROM food_place WHERE latitude NOT BETWEEN -90 AND 90 OR longitude NOT BETWEEN -180 AND 180 OR hygiene_grade NOT IN ('A','B','C','D')")).scalars().all()
    if invalid:
        raise ValueError(f'Correct invalid coordinate/grade values before upgrading: {invalid[:20]}')
    for model in (Tag, PlaceTag, MenuPublication, MenuEntry):
        model.__table__.create(db.engine, checkfirst=True)
    db.session.commit()
    from .reference_menus import allow_unpriced_references
    allow_unpriced_references(db.engine)
    columns = {c['name'] for c in inspect(db.engine).get_columns('dish')}
    for column in Dish.__table__.columns:
        if column.name not in columns:
            kind = column.type.compile(dialect=db.engine.dialect)
            db.session.execute(text(f'ALTER TABLE dish ADD COLUMN {column.name} {kind}'))
    db.session.commit()
    install_upgrade_constraints()
    converted_tags = converted_dishes = 0
    for place in db.session.scalars(select(FoodPlace)):
        if place.legacy_tags:
            place.tags = place.legacy_tags
            converted_tags += 1
    from .menu_imports import normalise_menu
    for filename in ('kfc_sg_reference_20261004.json', 'sukiya_sg_reference_20261004.json'):
        raw = json.loads((BASE_DIR / 'data/menus' / filename).read_text(encoding='utf-8'))
        # Normalization validates source facts without inventing outlet identities.
        raw['places'] = [{'id': 1, 'name': 'Migration source identity', 'sourceId': ''}]
        menu = normalise_menu(raw)
        publication = publication_for(menu)
        ids = [i['sourceId'] for i in menu['items']]
        candidates = list(db.session.scalars(select(Dish).where(Dish.publication_id.is_(None),
            Dish.legacy_source_name == menu['sourceName'], Dish.legacy_source_url == menu['sourceUrl'],
            Dish.legacy_is_reference.is_(True), Dish.source_item_id.in_(ids),
            or_(Dish.legacy_source_observed_at == publication.observed_at, Dish.legacy_source_observed_at.is_(None)))))
        for dish in candidates:
            bind_offering(dish, publication, dish.source_item_id, preserve=True)
            converted_dishes += 1
    db.session.commit()
    from .database_lab import install_views
    install_views()
    return {'status': 'upgraded', 'taggedPlacesConverted': converted_tags,
            'offeringsConverted': converted_dishes, 'dishIdsPreserved': True}


def install_upgrade_constraints():
    """Old SQLite tables need triggers; MariaDB supports additive CHECK/FK DDL."""
    rules = {
        'ck_place_latitude': ('food_place', 'latitude IS NULL OR latitude BETWEEN -90 AND 90'),
        'ck_place_longitude': ('food_place', 'longitude IS NULL OR longitude BETWEEN -180 AND 180'),
        'ck_place_hygiene': ('food_place', "hygiene_grade IS NULL OR hygiene_grade IN ('A','B','C','D')"),
        'ck_dish_override_price': ('dish', 'price_override IS NULL OR price_override >= 0'),
        'ck_dish_entry_identity': ('dish', 'publication_id IS NULL OR source_item_id IS NOT NULL'),
        'ck_dish_shared_payload': ('dish', "publication_id IS NULL OR (dish_name = '' AND price = 0 AND description = '' AND dietary_label = '' AND source_name IS NULL AND source_url IS NULL AND source_observed_at IS NULL)"),
    }
    if db.engine.dialect.name == 'sqlite':
        for name, (table, condition) in rules.items():
            # Trigger expressions use a row alias for every referenced column.
            for col in sorted(db.metadata.tables[table].columns.keys(), key=len, reverse=True):
                import re
                condition = re.sub(r'\b' + col + r'\b', 'NEW.' + col, condition)
            for action in ('INSERT', 'UPDATE'):
                db.session.execute(text(f"CREATE TRIGGER IF NOT EXISTS {name}_{action} BEFORE {action} ON {table} WHEN NOT ({condition}) BEGIN SELECT RAISE(ABORT,'{name}'); END"))
        for action in ('INSERT', 'UPDATE'):
            db.session.execute(text(f"CREATE TRIGGER IF NOT EXISTS fk_dish_entry_{action} BEFORE {action} ON dish WHEN NEW.publication_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM menu_entry e WHERE e.publication_id=NEW.publication_id AND e.source_item_id=NEW.source_item_id) BEGIN SELECT RAISE(ABORT,'fk_dish_menu_entry'); END"))
        for action in ('DELETE', 'UPDATE'):
            operation = 'UPDATE OF publication_id,source_item_id' if action == 'UPDATE' else action
            db.session.execute(text(f"CREATE TRIGGER IF NOT EXISTS fk_entry_restrict_{action} BEFORE {operation} ON menu_entry WHEN EXISTS (SELECT 1 FROM dish WHERE publication_id=OLD.publication_id AND source_item_id=OLD.source_item_id) BEGIN SELECT RAISE(ABORT,'referenced menu entry'); END"))
    else:
        for name, (table, condition) in rules.items():
            checks = {c['name'] for c in inspect(db.engine).get_check_constraints(table)}
            if name not in checks:
                db.session.execute(text(f'ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({condition})'))
        if 'fk_dish_menu_entry' not in {f['name'] for f in inspect(db.engine).get_foreign_keys('dish')}:
            db.session.execute(text('ALTER TABLE dish ADD CONSTRAINT fk_dish_menu_entry FOREIGN KEY (publication_id,source_item_id) REFERENCES menu_entry(publication_id,source_item_id)'))
    indexes = {i['name'] for i in inspect(db.engine).get_indexes('dish')} | {i['name'] for i in inspect(db.engine).get_unique_constraints('dish')}
    if 'uq_dish_offering' not in indexes:
        db.session.execute(text('CREATE UNIQUE INDEX uq_dish_offering ON dish(place_id,publication_id,source_item_id)'))
    db.session.commit()
