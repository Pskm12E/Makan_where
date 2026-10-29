import csv
import gzip
from datetime import datetime, timezone
import json
import pytest
from sqlalchemy import func, inspect, select, text
from test_api import app
from backend.imports import import_csv, read_rows, REQUIRED, LICENCE
from backend.migrations import add_catalogue_provenance, add_listing_details, add_menu_provenance
from backend.models import db, FoodPlace, Dish
from scripts.scrape_osm import normalise, spreadsheet_safe


def row(identity="node/123", name="Real café"):
    return dict(source="OpenStreetMap", source_id=identity, source_url="https://www.openstreetmap.org/" + identity,
                fetched_at="2026-09-22T10:00:00+00:00", name=name, category="Cafe", cuisines="Coffee;Chinese",
                address="12 Orchard Road", area="Orchard", latitude="1.301000", longitude="103.830000",
                opening_hours="Mo-Fr 09:00-18:00", licence=LICENCE, attribution="© OpenStreetMap contributors")


def write_csv(tmp_path, rows):
    path = tmp_path / "places.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=sorted(REQUIRED))
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_import_preview_repeat_and_preserve_existing(app, tmp_path):
    path = write_csv(tmp_path, [row(), row("way/456", "Another branch")])
    with app.app_context():
        before_dishes = db.session.scalar(select(func.count()).select_from(Dish))
        assert import_csv(path)["new"] == 2
        assert db.session.scalar(select(func.count()).select_from(FoodPlace)) == 6
        result = import_csv(path, apply=True)
        assert result["new"] == 2
        place = db.session.get(FoodPlace, result["place_ids"][0])
        assert place.source_url == "https://www.openstreetmap.org/node/123"
        assert float(place.latitude) == 1.301
        assert {c.cuisine_name for c in place.cuisines} == {"Coffee", "Chinese"}
        assert not place.is_sample and place.image_url == ""
        place.place_name = "Administrator's corrected name"
        db.session.commit()
        repeat = import_csv(path, apply=True)
        assert repeat["new"] == 0 and repeat["existing_skipped"] == 2
        assert db.session.get(FoodPlace, place.place_id).place_name == "Administrator's corrected name"
        assert db.session.scalar(select(func.count()).select_from(Dish)) == before_dishes
    response = app.test_client().get('/api/establishments/' + str(result["place_ids"][0])).json['establishment']
    assert response['source'] == 'OpenStreetMap' and response['price'] is None and response['rating'] == 0
    assert response['menu'] == []


def test_import_rejects_whole_file_before_writing(app, tmp_path):
    bad = row("node/456")
    bad["longitude"] = "NaN"
    path = write_csv(tmp_path, [row(), bad])
    with app.app_context():
        with pytest.raises(ValueError): import_csv(path, apply=True)
        assert db.session.scalar(select(func.count()).select_from(FoodPlace)) == 6
    path = write_csv(tmp_path, [row(), row()])
    with pytest.raises(ValueError, match="duplicate"): read_rows(path)
    bad = row()
    bad['source_url'] = 'javascript:alert(1)'
    with pytest.raises(ValueError, match="source URL"): read_rows(write_csv(tmp_path, [bad]))


def test_normalise_deduplicates_without_inventing_missing_facts(tmp_path):
    elements = [dict(type="node", id=1, lat=1.3, lon=103.83,
                    tags={"amenity":"cafe", "name":"=A café", "addr:street":"Orchard Road", "addr:housenumber":"12"}),
                dict(type="way", id=2, center={"lat":1.300001,"lon":103.83},
                    tags={"amenity":"cafe", "name":"=A café", "addr:street":"Orchard Road", "addr:housenumber":"12"}),
                dict(type="node", id=3, lat=1.31, lon=103.84, tags={"amenity":"restaurant","name":"Another branch"}),
                dict(type="node", id=4, lat=2.1, lon=103.84, tags={"amenity":"restaurant","name":"Outside"})]
    rows, rejected, duplicates = normalise({"elements":elements}, "2026-09-22T10:00:00+00:00")
    assert len(rows) == 2 and len(rejected) == 1 and len(duplicates) == 1
    assert rows[1]['address'] == rows[1]['cuisines'] == rows[1]['area'] == ""
    assert rows[0]['name'] == '=A café'
    path = write_csv(tmp_path, [{k:spreadsheet_safe(v) for k,v in r.items()} for r in rows])
    assert read_rows(path)[0]['name'] == '=A café'


def test_additive_migration_from_original_schema_preserves_rows(app):
    with app.app_context():
        db.session.remove()
        dialect = db.engine.dialect.name
        # Reconstruct the previous shape only in this isolated test database.
        db.session.execute(text('ALTER TABLE food_place DROP COLUMN enrichment'))
        if dialect == 'mysql':
            # Remove the newer shared-menu dependencies before reconstructing
            # the original columns in this disposable database.
            db.session.execute(text('ALTER TABLE dish DROP FOREIGN KEY fk_dish_menu_entry'))
            db.session.execute(text('ALTER TABLE dish DROP INDEX uq_dish_offering'))
            db.session.execute(text('ALTER TABLE dish DROP CONSTRAINT ck_dish_shared_payload'))
            db.session.execute(text('ALTER TABLE dish DROP CONSTRAINT ck_dish_entry_identity'))
            db.session.execute(text('ALTER TABLE food_place DROP INDEX uq_food_place_source'))
            for name in ['source_name','source_id','source_url','source_fetched_at','opening_hours','is_sample']:
                db.session.execute(text(f'ALTER TABLE food_place DROP COLUMN {name}'))
            db.session.execute(text('ALTER TABLE dish DROP INDEX uq_dish_source'))
            for name in ['source_name','source_item_id','source_url','source_observed_at','is_reference']:
                db.session.execute(text(f'ALTER TABLE dish DROP COLUMN {name}'))
            db.session.commit()
        else:
            # SQLite cannot drop a column included in a table UNIQUE constraint.
            # Check idempotence here; the original-shape path runs on real MariaDB.
            db.session.execute(text('UPDATE food_place SET is_sample=0'))
            db.session.commit()
        assert add_catalogue_provenance()['samples_marked'] == 6
        assert add_catalogue_provenance()['samples_marked'] == 0
        assert db.session.execute(text('SELECT COUNT(*) FROM food_place')).scalar_one() == 6
        assert db.session.execute(text('SELECT COUNT(*) FROM dish')).scalar_one() == 18
        add_listing_details()
        add_menu_provenance()
        assert db.session.scalar(select(func.count()).select_from(FoodPlace)) == 6
        assert db.session.scalar(select(func.count()).select_from(Dish)) == 18


def test_compact_catalogue_compression_and_details(app):
    client = app.test_client()
    compressed = client.get('/api/catalogue', headers={'Accept-Encoding':'gzip'})
    assert compressed.status_code == 200 and compressed.headers['Content-Encoding'] == 'gzip'
    items = json.loads(gzip.decompress(compressed.data))['establishments']
    assert len(items) == 6 and items[0]['isSample'] is True
    assert 'sourceUrl' not in items[0]
    assert 'sourceUrl' in client.get('/api/establishments/1').json['establishment']
    plain = client.get('/api/catalogue', headers={'Accept-Encoding':'gzip;q=0'})
    assert 'Content-Encoding' not in plain.headers and len(plain.json['establishments']) == 6
