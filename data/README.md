# Singapore food listing data

The retained CSV is `scraped/singapore_food_places_20260922T094048Z.csv`.
It contains **8,415 OpenStreetMap food listings**, collected on 22 September 2026.
The identical public download is `assets/data/singapore_food_places.csv`.

## Source and licence

© OpenStreetMap contributors. This extract and its normalised CSV are available
under the [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
[OpenStreetMap attribution](https://www.openstreetmap.org/copyright).
Source: [Geofabrik Malaysia, Singapore and Brunei extract](https://download.geofabrik.de/asia/malaysia-singapore-brunei.html),
containing data up to 21 September 2026. The full regional PBF is cached in ignored
`work/`; its SHA-256, source timestamp and country boundary relation are retained
in the snapshot JSON.

The source snapshot and Singapore boundary are retained beside the CSV, together
with a quality report. Every CSV row includes its OSM identity, source URL,
collection time, licence and attribution. Source collection does not modify OSM.

## Selection and quality

- Named restaurants, cafes, fast-food venues and food courts inside Singapore's
  administrative country polygon. The country polygon comes from the same PBF.
- 867 bounding-box candidates outside Singapore were excluded geographically.
- 8,427 country-filtered candidates were normalised. Eleven nearby same-name,
  same-street-address duplicates were removed; one record exceeded field limits.
- 4,541 restaurants, 1,813 cafes, 1,373 fast-food venues and 688 food courts.
- 4,220 have an address; 4,330 have cuisine tags; nine have a neighbourhood tag.
  All 8,415 have coordinates. Blank cells mean the source did not provide the fact.
- Addresses may be partial. Areas not mapped in OSM display as Singapore in the
  application; no neighbourhood is guessed from a venue name.
- No menus, prices, ratings, reviews, hygiene grades or venue photos are inferred.
  Community-maintained information may be incomplete or outdated.
- Different branches and units are retained. Conservative duplicate checks can
  leave some real-world duplicates; source IDs prevent duplicate re-imports.
- CSV is UTF-8 with a BOM for Excel. Text that could be read as a spreadsheet
  formula is escaped with an apostrophe; the importer reverses only that escape.

## Rebuild without another download

```powershell
.\.venv\Scripts\python.exe scripts/scrape_osm.py --snapshot data/scraped/singapore_osm_20260922T093956Z.json
```

For a fresh extract, `scripts/scrape_osm.py` can make one bounded Overpass query.
The public query servers timed out during this collection, so the downloaded
Geofabrik PBF was processed locally instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r scripts/scraping-requirements.txt
.\.venv\Scripts\python.exe scripts/extract_osm_pbf.py work/malaysia-singapore-brunei-latest.osm.pbf
```

Use the snapshot path printed by the extractor with `scrape_osm.py --snapshot`.
This produces a new timestamped CSV and quality report. Keep previous snapshots.
Review the report before importing. Avoid repeated live Overpass calls; retain
and reuse downloaded data.

## Import

With the application's private database environment configured:

```sh
python -m flask --app backend.app migrate-catalogue
python -m flask --app backend.app import-places PATH_TO_CSV
python -m flask --app backend.app import-places PATH_TO_CSV --apply
```

The first import command previews counts. The second validates the entire CSV,
then commits new places, lookup rows and cuisine links in one transaction.
Existing OSM source IDs are skipped, including archived records, so re-importing
does not overwrite administrator edits. Existing users, reviews, favourites and
the six sample venue IDs are preserved. Sample venues are labelled individually.

The additive migration adds source fields and a unique source identity to
`food_place`. The current schema has ten active and seven legacy SQL tables. Back up the database before
migration/import. Import receipts list the exact new place IDs and CSV hash.

## Separately sourced menus

`menus/sukiya_sg_reference_20261004.json` contains eight adult/child lunch/dinner buffet reference prices from [Suki-Ya's official menu](https://www.suki-ya.com.sg/menu), observed on 4 October 2026. Four exact-name catalogue matches received 32 rows. These are published chain references; the source link is authoritative for outlet participation, GST, service charge, applicable days and other conditions.

`menus/kfc_sg_reference_20261004.json` is a separate menu source, not part of OpenStreetMap. It contains 97 distinct item names and SGD prices observed on [KFC Singapore's public menu](https://www.kfc.com.sg/menu) on 4 October 2026. Item identifiers are locally assigned stable slugs, not claimed provider API IDs. No marketing descriptions or product images are copied. Explicitly discounted, Monday-only/app-only offers and an ambiguous duplicated salad-meal variant are omitted. This is an observed reference snapshot, not a claim of permanent pricing, complete promotion coverage or outlet availability.

The importer matches only active non-sample listings named exactly `KFC` and verifies their IDs, names and OSM source identities. It marks the dishes as chain references and retains source URL/time in SQL. The local catalogue matched 72 such listings: 6,984 dish rows plus the original 18 sample dishes. Other venues retain missing menus until a suitable source is supplied. See the [menu import guide](../README.md#add-menus-and-manage-them-in-admin).

## Business links and illustrative photographs

`enrichment/osm_business_details.json` recovers website, menu-link and public business-phone tags for the existing catalogue identities from the same retained PBF. No new data was requested from OSM. The file retains the PBF checksum, OSM snapshot timestamp and ODbL licence. Run `scripts/extract_listing_details.py work/malaysia-singapore-brunei-latest.osm.pbf` to reproduce it. Exact identity and name checks prevent a similarly named branch receiving another venue's details.

`enrichment/chain_links.json` adds reviewed official McDonald's, KFC and Suki-Ya links. McDonald's names are a selected 45-item summary of its public full-menu page; there are no invented prices. An official chain menu does not confirm that every mapped outlet is still operating or offers every item.

`enrichment/illustrative_photos.json` contains six Unsplash image choices with source and credit links, under the [Unsplash licence](https://unsplash.com/license). The burger, coffee and curry photo pages were checked; the sushi, salad and general-food URLs were already used by the project's demonstration catalogue. Photographs are selected by existing cuisine/category, labelled **Illustrative photo**, and never presented as pictures of the mapped outlet or its own dishes. All 8,421 current listing photos are illustrative; no actual outlet photo coverage is claimed. Existing administrator-supplied images take priority. No Unsplash API, external photo-provider API key or generated restaurant image is used.

On 4 October, the enrichment filled 1,843 listings: 1,481 websites, 267 menu links, 1,183 phones and 151 menu-highlight sets. Five invalid source fields were skipped. Repeat application changed zero listings. Existing values and deliberate administrator removals are retained. Fields not available from these sources remain unknown.
