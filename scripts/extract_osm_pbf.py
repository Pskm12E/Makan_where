"""Extract Singapore food POIs from Geofabrik's regional OSM PBF fallback.

Install osmium and shapely locally; neither package is needed on the server.
Boundary geometry is taken from the same extract, preventing Johor/Batam imports.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import osmium
from shapely.geometry import Point, mapping
from shapely import wkb
from scrape_osm import CATEGORIES

SOURCE = "https://download.geofabrik.de/asia/malaysia-singapore-brunei.html"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pbf", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("data/scraped"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    factory = osmium.geom.WKBFactory()
    candidates, boundaries = {}, []
    print("Extracting named food venues and Singapore's boundary from the saved PBF...", flush=True)
    processor = osmium.FileProcessor(args.pbf).with_areas().with_filter(osmium.filter.KeyFilter("amenity", "ISO3166-1"))
    for obj in processor:
        tags = dict(obj.tags)
        if obj.is_area() and tags.get("ISO3166-1") == "SG" and tags.get("admin_level") == "2":
            boundaries.append((obj.orig_id(), wkb.loads(factory.create_multipolygon(obj), hex=True)))
        if tags.get("amenity") not in CATEGORIES or not tags.get("name"):
            continue
        if obj.is_node():
            if not obj.location.valid(): continue
            kind, identity, lat, lon = "node", obj.id, obj.lat, obj.lon
        elif obj.is_area():
            shape = wkb.loads(factory.create_multipolygon(obj), hex=True)
            point = shape.representative_point()
            kind, identity, lat, lon = "way" if obj.from_way() else "relation", obj.orig_id(), point.y, point.x
        elif obj.is_way():
            coords = [(n.lat, n.lon) for n in obj.nodes if n.location.valid()]
            if len(coords) != len(obj.nodes) or not coords: continue
            kind, identity = "way", obj.id
            lat = (min(p[0] for p in coords) + max(p[0] for p in coords)) / 2
            lon = (min(p[1] for p in coords) + max(p[1] for p in coords)) / 2
        else:
            continue
        if not (1.1 <= lat <= 1.5 and 103.55 <= lon <= 104.15): continue
        # Retain relevant business facts; no contributor metadata or contact info.
        kept = {k:v for k,v in tags.items() if k in {"name", "name:en", "amenity", "cuisine", "opening_hours", "disused", "abandoned", "demolished"} or k.startswith("addr:")}
        candidates[(kind, identity)] = {"type": kind, "id": identity, "lat": lat, "lon": lon, "tags": kept}
    if len(boundaries) != 1:
        raise RuntimeError(f"Expected one complete Singapore boundary, found {len(boundaries)}; no CSV produced")
    relation_id, boundary = boundaries[0]
    elements = [row for row in candidates.values() if boundary.covers(Point(row["lon"], row["lat"]))]
    if not elements: raise RuntimeError("No Singapore food listings survived boundary filtering")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with osmium.io.Reader(str(args.pbf)) as reader:
        source_time = reader.header().get("osmosis_replication_timestamp")
    envelope = {"fetched_at": datetime.now(timezone.utc).isoformat(), "endpoint": SOURCE,
        "query": "Geofabrik PBF: named restaurant/cafe/fast_food/food_court within the SG admin_level=2 boundary",
        "pbf_sha256": hashlib.file_digest(args.pbf.open("rb"), "sha256").hexdigest(),
        "source_timestamp": source_time, "boundary_relation_id": relation_id,
        "response": {"elements": elements, "osm3s": {"timestamp_osm_base": source_time}},
        "bbox_candidates": len(candidates), "outside_singapore_excluded": len(candidates) - len(elements)}
    target = args.output_dir / f"singapore_osm_{stamp}.json"
    target.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    target.with_suffix(".boundary.geojson").write_text(json.dumps({"type":"Feature","properties":{"source":"OpenStreetMap","relation_id":relation_id},"geometry":mapping(boundary)}),encoding="utf-8")
    print(json.dumps({"snapshot": str(target), "food_places": len(elements), "outside_singapore_excluded": envelope["outside_singapore_excluded"]}),flush=True)


if __name__ == "__main__": main()
