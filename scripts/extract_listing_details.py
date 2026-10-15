"""Recover public business links from the retained OSM PBF, by exact source ID.

No geocoding, matching by restaurant name, contributor metadata or network calls.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import osmium


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pbf', type=Path)
    parser.add_argument('--output', type=Path, default=Path('data/enrichment/osm_business_details.json'))
    args = parser.parse_args()
    with Path('data/scraped/singapore_food_places_20260922T094048Z.csv').open(encoding='utf-8-sig') as stream:
        targets = {r['source_id']: r for r in csv.DictReader(stream)}
    rows = []
    class BusinessDetails(osmium.SimpleHandler):
        def collect(self, obj, kind):
            identity = f'{kind}/{obj.id}'
            if identity not in targets:
                return
            tags = dict(obj.tags)
            fields = {}
            for output, keys in {'website': ['website', 'contact:website'],
                                 'menuUrl': ['website:menu', 'contact:website:menu', 'menu:website'],
                                 'phone': ['phone', 'contact:phone']}.items():
                value = next((tags[k].strip() for k in keys if tags.get(k, '').strip()), '')
                if value:
                    fields[output] = value
            if fields:
                rows.append({'sourceId': identity, 'name': targets[identity]['name'],
                             'sourceUrl': 'https://www.openstreetmap.org/' + identity, **fields})
        def node(self, obj): self.collect(obj, 'node')
        def way(self, obj): self.collect(obj, 'way')
        def relation(self, obj): self.collect(obj, 'relation')
    BusinessDetails().apply_file(str(args.pbf))
    with osmium.io.Reader(str(args.pbf)) as reader:
        source_time = reader.header().get('osmosis_replication_timestamp')
    result = {'source': 'OpenStreetMap contributors', 'sourceTimestamp': source_time,
              'licence': 'https://opendatacommons.org/licenses/odbl/1-0/',
              'pbfSha256': hashlib.file_digest(args.pbf.open('rb'), 'sha256').hexdigest(),
              'places': sorted(rows, key=lambda r: r['sourceId'])}
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'file': str(args.output), 'places': len(rows),
                      **{k: sum(bool(r.get(k)) for r in rows) for k in ['website', 'menuUrl', 'phone']}}))


if __name__ == '__main__': main()
