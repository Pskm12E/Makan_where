"""Validate and import retained CSV data without overwriting curated or user records."""
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path
import re
from sqlalchemy import select
from .models import db, Area, Category, Cuisine, FoodPlace

REQUIRED = {"source", "source_id", "source_url", "fetched_at", "name", "category", "cuisines",
            "address", "area", "latitude", "longitude", "opening_hours", "licence", "attribution"}
LICENCE = "https://opendatacommons.org/licenses/odbl/1-0/"


def csv_text(value):
    # Undo only the formula escape deliberately added by our exporter.
    if value.startswith("'") and value[1:].lstrip().startswith(("=", "+", "-", "@")):
        return value[1:]
    return value


def read_rows(path):
    path = Path(path)
    if path.stat().st_size > 30_000_000:
        raise ValueError("CSV exceeds the 30 MB import limit")
    rows, seen = [], set()
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if set(reader.fieldnames or []) != REQUIRED:
            raise ValueError("CSV headers do not match the saved food listing format")
        for line, raw in enumerate(reader, 2):
            if None in raw or any(value is None for value in raw.values()):
                raise ValueError(f"CSV line {line}: wrong number of columns")
            row = {k: csv_text(v).strip() for k, v in raw.items()}
            if row["source"] != "OpenStreetMap" or not re.fullmatch(r"(node|way|relation)/[1-9][0-9]*", row["source_id"]):
                raise ValueError(f"CSV line {line}: unsupported source identity")
            if row["source_url"] != "https://www.openstreetmap.org/" + row["source_id"] or row["licence"] != LICENCE:
                raise ValueError(f"CSV line {line}: invalid source URL or licence")
            if row["source_id"] in seen:
                raise ValueError(f"CSV line {line}: duplicate source identity")
            seen.add(row["source_id"])
            for key, limit in {"name":150, "address":255, "area":100, "opening_hours":1000}.items():
                if len(row[key]) > limit or (key == "name" and not row[key]):
                    raise ValueError(f"CSV line {line}: invalid {key}")
            if row["category"] not in {"Restaurant", "Cafe", "Fast Food", "Food Court"}:
                raise ValueError(f"CSV line {line}: unsupported category")
            try:
                lat, lon = Decimal(row["latitude"]), Decimal(row["longitude"])
                if not lat.is_finite() or not lon.is_finite() or not (Decimal("1.1") <= lat <= Decimal("1.5") and Decimal("103.55") <= lon <= Decimal("104.15")):
                    raise ValueError()
                fetched = datetime.fromisoformat(row["fetched_at"].replace("Z", "+00:00"))
                if fetched.tzinfo is None: raise ValueError()
            except (ValueError, InvalidOperation) as error:
                raise ValueError(f"CSV line {line}: invalid coordinates or timestamp") from error
            cuisines = list(dict.fromkeys(c.strip() for c in row["cuisines"].split(";") if c.strip()))
            if len(cuisines) > 10 or any(len(c) > 100 for c in cuisines):
                raise ValueError(f"CSV line {line}: invalid cuisines")
            row.update(latitude=lat, longitude=lon, fetched=fetched.astimezone(timezone.utc).replace(tzinfo=None), cuisine_names=cuisines)
            rows.append(row)
            if len(rows) > 20000: raise ValueError("Import exceeds 20,000 rows")
    if not rows: raise ValueError("CSV contains no records")
    return rows


def import_csv(path, *, apply=False):
    rows = read_rows(path)
    existing = set(db.session.scalars(select(FoodPlace.source_id).where(FoodPlace.source_name == "OpenStreetMap")))
    new_rows = [r for r in rows if r["source_id"] not in existing]
    report = {"csv": str(path), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
              "rows": len(rows), "new": len(new_rows), "existing_skipped": len(rows) - len(new_rows),
              "applied": apply, "place_ids": []}
    if not apply: return report
    caches = {Area: {a.area_name.casefold(): a for a in db.session.scalars(select(Area))},
              Category: {c.category_name.casefold(): c for c in db.session.scalars(select(Category))},
              Cuisine: {c.cuisine_name.casefold(): c for c in db.session.scalars(select(Cuisine))}}

    def term(model, attr, name):
        key = name.casefold()
        if key not in caches[model]:
            item = model(**{attr: name})
            db.session.add(item)
            caches[model][key] = item
        return caches[model][key]

    added = []
    try:
        with db.session.no_autoflush:
            for row in new_rows:
                place = FoodPlace(place_name=row["name"], address=row["address"], latitude=row["latitude"],
                    longitude=row["longitude"], source_name=row["source"], source_id=row["source_id"],
                    source_url=row["source_url"], source_fetched_at=row["fetched"], opening_hours=row["opening_hours"] or None,
                    area=term(Area, "area_name", row["area"] or "Singapore"),
                    category=term(Category, "category_name", row["category"]),
                    cuisines=[term(Cuisine, "cuisine_name", c) for c in row["cuisine_names"]],
                    description="", image_url="", tags=[], is_sample=False)
                db.session.add(place)
                added.append(place)
        db.session.flush()
        report["place_ids"] = [p.place_id for p in added]
        db.session.commit()
    except BaseException:
        db.session.rollback()
        raise
    return report
