"""Fetch one Singapore food POI extract and retain an attributed CSV + source snapshot.

Uses the public read-only Overpass API, never the OSM editing API. Reprocessing
an existing snapshot does not make network requests. See data/README.md.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlencode
from urllib.request import Request, urlopen

QUERY = '''[out:json][timeout:90][bbox:1.10,103.55,1.50,104.15];
area["ISO3166-1"="SG"]["admin_level"="2"]->.sg;
(
  nwr["amenity"="restaurant"]["name"](area.sg);
  nwr["amenity"="cafe"]["name"](area.sg);
  nwr["amenity"="fast_food"]["name"](area.sg);
  nwr["amenity"="food_court"]["name"](area.sg);
);
out center tags;
'''
ENDPOINT = "https://overpass-api.de/api/interpreter"
LICENCE = "https://opendatacommons.org/licenses/odbl/1-0/"
FIELDS = ["source", "source_id", "source_url", "fetched_at", "name", "category", "cuisines",
          "address", "area", "latitude", "longitude", "opening_hours", "licence", "attribution"]
CATEGORIES = {"restaurant": "Restaurant", "cafe": "Cafe", "fast_food": "Fast Food", "food_court": "Food Court"}
CUISINES = {"coffee_shop": "Coffee", "regional": "Local", "seafood": "Seafood", "barbecue": "Barbecue",
            "bubble_tea": "Bubble Tea", "chicken_rice": "Chicken Rice", "ice_cream": "Ice Cream"}


def clean(value):
    return " ".join(unicodedata.normalize("NFC", str(value or "")).split())


def spreadsheet_safe(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def metres(a, b):
    return 111320 * math.hypot(float(a["latitude"]) - float(b["latitude"]),
                             (float(a["longitude"]) - float(b["longitude"])) * math.cos(math.radians(1.3)))


def normalise(snapshot, fetched_at):
    rows, rejected, duplicates = [], [], []
    seen_ids, addresses = set(), {}
    for element in sorted(snapshot["elements"], key=lambda e: (e["type"], e["id"])):
        tags = element.get("tags", {})
        source_id = f'{element["type"]}/{element["id"]}'
        name = clean(tags.get("name:en") or tags.get("name"))
        point = element.get("center", element)
        lat, lon = point.get("lat"), point.get("lon")
        if not name or len(name) > 150 or tags.get("amenity") not in CATEGORIES:
            rejected.append({"source_id": source_id, "reason": "missing/oversize name or unsupported category"})
            continue
        if lat is None or lon is None or not (1.1 <= lat <= 1.5 and 103.55 <= lon <= 104.15):
            rejected.append({"source_id": source_id, "reason": "missing coordinates or outside Singapore bounds"})
            continue
        if any(tags.get(key) in {"yes", "true"} for key in ("disused", "abandoned", "demolished")):
            rejected.append({"source_id": source_id, "reason": "marked inactive"})
            continue
        street = clean(tags.get("addr:street"))
        line = clean(" ".join([tags.get("addr:housenumber", ""), street])) if street else ""
        address = clean(tags.get("addr:full"))
        if not address:
            parts = [line, clean(tags.get("addr:unit"))]
            postcode = clean(tags.get("addr:postcode"))
            if postcode and re.fullmatch(r"\d{6}", postcode): parts.append("Singapore " + postcode)
            address = ", ".join(p for p in parts if p)
        area = clean(tags.get("addr:suburb") or tags.get("addr:neighbourhood") or tags.get("addr:quarter"))
        cuisines = []
        for value in re.split(r"[;,]", tags.get("cuisine", "")):
            value = clean(value).lower()
            if value and len(value) <= 100:
                cuisines.append(CUISINES.get(value, value.replace("_", " ").title()))
        row = {"source": "OpenStreetMap", "source_id": source_id,
               "source_url": "https://www.openstreetmap.org/" + source_id, "fetched_at": fetched_at,
               "name": name, "category": CATEGORIES[tags["amenity"]], "cuisines": ";".join(dict.fromkeys(cuisines)),
               "address": address, "area": area, "latitude": f"{lat:.6f}", "longitude": f"{lon:.6f}",
               "opening_hours": clean(tags.get("opening_hours")), "licence": LICENCE,
               "attribution": "© OpenStreetMap contributors"}
        if len(address) > 255 or len(area) > 100 or len(row["cuisines"]) > 1000 or len(cuisines) > 10:
            rejected.append({"source_id": source_id, "reason": "field exceeds application limit"})
            continue
        key = (name.casefold(), address.casefold())
        # Keep branches and different units. Only collapse nearby same-name,
        # same-address duplicates when the source provides a street/full address.
        duplicate = next((prior for prior in addresses.get(key, []) if metres(prior, row) < 15), None) if street or tags.get("addr:full") else None
        if source_id in seen_ids or duplicate:
            duplicates.append({"source_id": source_id, "kept": duplicate["source_id"] if duplicate else source_id})
            continue
        seen_ids.add(source_id)
        addresses.setdefault(key, []).append(row)
        rows.append(row)
    return rows, rejected, duplicates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, help="Rebuild from a saved raw JSON file without fetching")
    parser.add_argument("--endpoint", default=ENDPOINT)
    parser.add_argument("--output-dir", type=Path, default=Path("data/scraped"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.snapshot:
        raw_path = args.snapshot
        envelope = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        raw_path = args.output_dir / f"singapore_osm_{stamp}.json"
        req = Request(args.endpoint, data=urlencode({"data": QUERY}).encode(),
                      headers={"User-Agent": "MakanWhere/1.0 (+https://makanwhere.4bytedigi.com)",
                               "Content-Type": "application/x-www-form-urlencoded"})
        print("Fetching one Singapore food listing extract from Overpass...", flush=True)
        with urlopen(req, timeout=180) as response:
            raw = response.read(30_000_001)
        if len(raw) > 30_000_000: raise RuntimeError("Unexpectedly large extract; no import attempted")
        snapshot = json.loads(raw)
        if snapshot.get("remark") or not snapshot.get("elements"):
            raise RuntimeError("Incomplete or empty extract: " + str(snapshot.get("remark", "no elements")))
        envelope = {"fetched_at": datetime.now(timezone.utc).isoformat(), "endpoint": args.endpoint,
                    "query": QUERY, "response": snapshot}
        raw_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows, rejected, duplicates = normalise(envelope["response"], envelope["fetched_at"])
    if not rows: raise RuntimeError("No usable food listings")
    csv_path = args.output_dir / f"singapore_food_places_{stamp}.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({key: spreadsheet_safe(value) for key, value in row.items()} for row in rows)
    report = {"source": "OpenStreetMap", "licence": LICENCE, "attribution": "© OpenStreetMap contributors",
              "query": envelope["query"], "fetched_at": envelope["fetched_at"], "raw_snapshot": str(raw_path),
              "csv": str(csv_path), "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
              "source_elements": len(envelope["response"]["elements"]), "rows": len(rows),
              "with_address": sum(bool(r["address"]) for r in rows), "with_cuisine": sum(bool(r["cuisines"]) for r in rows),
              "with_area": sum(bool(r["area"]) for r in rows), "rejected": rejected, "duplicates": duplicates,
              "notes": ["Blank means not supplied by the source. No prices, ratings, menus or photos are inferred.",
                        "Street-address duplicates within 15 metres are collapsed; different branches/units remain.",
                        "Spreadsheet formula prefixes are escaped with an apostrophe in CSV text cells."]}
    report_path = csv_path.with_suffix(".report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["csv", "rows", "source_elements", "with_address", "with_cuisine", "with_area", "sha256"]}))


if __name__ == "__main__": main()
