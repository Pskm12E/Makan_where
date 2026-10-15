"""Small, additive migrations for an existing Makan Where database."""
import json
from sqlalchemy import inspect, text
from .config import BASE_DIR
from .models import db


def add_listing_details():
    inspector = inspect(db.engine)
    added = []
    if 'food_place' in inspector.get_table_names() and 'enrichment' not in {c['name'] for c in inspector.get_columns('food_place')}:
        db.session.execute(text('ALTER TABLE food_place ADD COLUMN enrichment JSON'))
        db.session.commit()
        added.append('enrichment')
    return {'migration': 'listing_details', 'added': added}


def add_menu_provenance():
    """Add import identities without rebuilding dishes or changing their IDs."""
    inspector = inspect(db.engine)
    if "dish" not in inspector.get_table_names():
        return {"migration": "menu_provenance", "added": []}
    columns = {c["name"] for c in inspector.get_columns("dish")}
    types = {"source_name": "VARCHAR(80)", "source_item_id": "VARCHAR(100)",
             "source_url": "VARCHAR(500)", "source_observed_at": "DATETIME",
             "is_reference": "BOOLEAN NOT NULL DEFAULT 0"}
    added = []
    for name, sqltype in types.items():
        if name not in columns:
            db.session.execute(text(f"ALTER TABLE dish ADD COLUMN {name} {sqltype}"))
            added.append(name)
    db.session.commit()
    inspector = inspect(db.engine)
    names = {i["name"] for i in inspector.get_indexes("dish") + inspector.get_unique_constraints("dish")}
    if "uq_dish_source" not in names:
        db.session.execute(text("CREATE UNIQUE INDEX uq_dish_source ON dish (place_id, source_name, source_item_id)"))
        db.session.commit()
    return {"migration": "menu_provenance", "added": added}


def add_catalogue_provenance():
    inspector = inspect(db.engine)
    if "food_place" not in inspector.get_table_names():
        raise ValueError("Initialize the application schema first")
    columns = {column["name"] for column in inspector.get_columns("food_place")}
    types = {"source_name": "VARCHAR(40)", "source_id": "VARCHAR(80)", "source_url": "VARCHAR(500)",
             "source_fetched_at": "DATETIME", "opening_hours": "VARCHAR(1000)", "is_sample": "BOOLEAN NOT NULL DEFAULT 0"}
    for name, sqltype in types.items():
        if name not in columns:
            db.session.execute(text(f"ALTER TABLE food_place ADD COLUMN {name} {sqltype}"))
    db.session.commit()
    inspector = inspect(db.engine)
    names = {item["name"] for item in inspector.get_indexes("food_place") + inspector.get_unique_constraints("food_place")}
    if "uq_food_place_source" not in names:
        db.session.execute(text("CREATE UNIQUE INDEX uq_food_place_source ON food_place (source_name, source_id)"))
        db.session.commit()
    samples = json.loads((BASE_DIR / "database/demo_places.json").read_text(encoding="utf-8"))
    marked = 0
    for sample in samples:
        # This migration can run before newer listing/menu columns exist.
        # Loading today's ORM entity would also load those columns and dishes.
        result = db.session.execute(text(
            'UPDATE food_place SET is_sample=1 WHERE place_name=:name '
            'AND address=:address AND source_name IS NULL AND is_sample=0'),
            {'name': sample['name'], 'address': sample['address']})
        marked += result.rowcount
    db.session.commit()
    return {"migration": "catalogue_provenance", "samples_marked": marked}
