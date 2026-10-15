# Makan Where

Python / Flask food discovery and community reviews for INF2003. **SQL and MongoDB are now used together:** SQL owns accounts, venues, menus, favourites and events; MongoDB owns reviews, discussions, replies, votes and moderation.

**Database access is implemented in this repository.** Flask uses SQLAlchemy/PyMySQL directly for MariaDB and PyMongo directly for MongoDB. The application does not call a DBStudios API or require its dashboard. The in-app **Database evidence** page runs the fixed Python queries in `backend/database_lab.py`; see the [database code map](docs/database_code_map.md) for CRUD, aggregation, schema and connection entry points.

**Current environments:** the local preview uses SQLite + MongoDB 8.0.19. The live server uses MariaDB 10.11.14 + MongoDB 8.0.19; this release passed all 61 tests against both server engines on 4 October 2026. The webpage labels the actual SQL engine. See the [verification record](docs/verification_record.md) for evidence and remaining limits.

## Combined database evidence

The [Database evidence page](https://makanwhere.4bytedigi.com/database-lab.html) uses the site's orange and cream theme and shows all six evidence sections together. **Run all checks** collects the SQL/Mongo snapshot, nine constraint checks and password checks; **Export JSON** includes the combined results. Details are expanded by default, with overview links and optional collapse controls. The live administrator display name is `Administrator`; the existing login username/password are unchanged. Sample and generated community records remain labelled.

## Example reviews and discussions

The live featured listings (#10, #14 and #15) and KFC #9 each have three fictional example reviews, two discussion threads and four replies. [Open the examples](https://makanwhere.4bytedigi.com/restaurant.html?id=10#venueReviews). Example accounts, titles, cards and text identify the content as fictional; example review stars are excluded from venue ratings and rankings. Normal user contributions continue to count.

With the private application environment loaded, run `python -m flask --app backend.app seed-listing-examples` to preview or add `--apply` to insert. Exact listing/source identities are checked before writes. Stable seed keys preserve existing edits/removals and prevent repeat imports from adding duplicates. This is separate from the bulk coursework fixtures on sample venues.

## Open the populated demo

Open [Database evidence](http://127.0.0.1:5055/database-lab.html). The local lecturer username/password are stored in the ignored `.env.demo` file as `DEMO_ADMIN_USERNAME` and `DEMO_ADMIN_PASSWORD`. Keep that file private and retain `PASSWORD_PEPPER` permanently with the environment.

For ordinary website testing, open [the sample venues](http://127.0.0.1:5055/browse.html?dataset=demo). Switch Listing source to Imported listings to explore all 8,415 source records. Sample venues have populated menus and community content. Reviews show newest first, ten per page; section shortcuts lead to the menu, review form and discussions.

**Server update:** [the public site](https://makanwhere.4bytedigi.com/) is running release `020722529efc502a`. All 8,421 listings have attributed illustrative photos; the server includes 6,984 KFC and 32 Suki-Ya reference-menu rows, 1,481 websites, 267 menu links and 1,183 public business phones. The private menu-import key is enabled. The live lecturer accounts are `demo_lecturer` (admin) and `lecturer_user` (normal user), each with a separate generated password delivered privately to the project owner; local `.env.demo` credentials do not apply to the public site. See the [deployment runbook](deploy/README.md) for backup locations and checks.

```powershell
Set-Location 'D:\Programing\Makan_where'
powershell -File scripts/start_local_demo.ps1
```

The helper restarts this computer's portable authenticated MongoDB when needed, then the Python web server. MongoDB data lives in ignored `work/runtime/mongo-data`, bound only to loopback port 27018. If the server is already running, open the link above. The main application is at the root URL.

To repeat population or serve a configured database directly:

```powershell
.venv/Scripts/python.exe scripts/run_demo.py --setup
.venv/Scripts/python.exe scripts/run_demo.py --serve
```

Stop the web app during migrations/population. Existing records are preserved. The report document remains unchanged, with review comments only.

## Data and demonstrations

| Data | Count | Origin |
| --- | ---: | --- |
| Imported venues | 8,415 | OpenStreetMap / Geofabrik, attributed CSV |
| Sample venues / dishes | 6 / 18 | Labelled demonstration fixtures |
| KFC venues / reference dishes | 72 / 6,984 | 97 distinct official-menu items shared across matching outlets |
| Suki-Ya venues / reference dishes | 4 / 32 | Eight published buffet options per matching outlet |
| Fictional users | 60 | Generated with individual random passwords not retained |
| Reviews / threads / replies | 600 / 30 / 90 | MongoDB; generated only on sample venues |
| Votes / moderation reports | 600 / 20 | MongoDB demonstration records |
| Favourites / events | 120 / 300 | SQL demonstration records |
| Lecturer account | 1 | Private local administrator |

The studio shows source checksums, repeat-import previews, counts, population receipts, reflected PK/FK/UNIQUE/CHECK/NOT NULL rules, actual rejection tests, duplicate/orphan audits, functional dependencies and normalization, SQL JOIN/GROUP BY/HAVING/NOT EXISTS/DISTINCT/EXPLAIN, a LEFT JOIN view, Mongo validation/aggregation, and a dummy-password salt/pepper experiment. Evidence can be exported as JSON. Database outages return errors rather than fabricated results.

OSM lacks many addresses/cuisine fields and supplies no menu prices or opinions. Menu data comes separately from labelled demonstration fixtures or attributed restaurant sources. Missing price means unknown, not zero. Generated community data carries `is_demo` and visible DEMO labels. See [provenance](data/README.md).

## Photos and business details

Every active listing now has a photo. Where no outlet image is supplied, the app selects an **illustrative food photo** by cuisine/category and labels it on the card and detail page. These photos are not evidence of the venue, its dishes or its appearance. Original sample images are also labelled illustrative. Photographs retain source/credit links; the image catalogue is in `data/enrichment/illustrative_photos.json`. Failed image loads show a fallback instead of a broken image.

The retained OSM extract supplied public business details matched by exact OSM ID **and** venue name. Along with reviewed official chain links, the local import filled **1,481 websites, 267 menu links and 1,183 phone numbers across 1,843 listings**. There are **273 listings with dishes or a source menu link**, including the six sample venues. McDonald's listings show 45 published menu highlights and their official menu link; prices are left unknown because that source does not publish them. Suki-Ya reference prices include child/adult and lunch/dinner labels. All listings with coordinates offer a map link.

In **Admin → Catalogue → Edit → Photos, links and venue details**, edit descriptions, hours, public phone numbers, website/menu links and photographs. Supply a photo source, credit and either **Actual venue photo** or **Illustrative photo**. Accepted image locations are HTTPS Unsplash/Wikimedia URLs or a deployed file under `/assets/`. Leave the image blank to use the automatic illustrative image. The admin list has thumbnails, and coverage totals include menu links. Empty addresses/cuisines remain unknown instead of being saved as invented facts.

Back up the database and stop the app before adding the new `food_place.enrichment` JSON column (17 tables, now 93 columns). Preview and apply the retained business details with:

```powershell
.venv/Scripts/python.exe scripts/run_demo.py --enrich-listings
.venv/Scripts/python.exe scripts/run_demo.py --enrich-listings --apply
.venv/Scripts/python.exe scripts/run_demo.py --serve
```

The first command runs the additive schema migration and then previews data changes. Repeating the import adds nothing. Existing values and administrator edits, including deliberately cleared links, are preserved. A fresh `--setup` includes enrichment. To add the reviewed Suki-Ya prices through the scoped key:

```powershell
.venv/Scripts/python.exe scripts/import_menus.py data/menus/sukiya_sg_reference_20261004.json
.venv/Scripts/python.exe scripts/import_menus.py data/menus/sukiya_sg_reference_20261004.json --apply
```

No external data-provider API key is needed for these retained sources. Unknown reviews, hygiene grades, opening hours, exact addresses and prices have not been invented. These changes are deployed to the public server; the deployment records document the server checks and backups.

## Add menus and manage them in admin

Open [Admin](http://127.0.0.1:5055/admin.html), sign in as an administrator, and find the establishment. **Manage menu** supports adding/editing names, SGD prices, descriptions and dietary information, plus removal/restoration without breaking old review links. **Menu coverage** filters establishments with missing menus. The overview shows how many establishments have available dishes.

For bulk data, choose **Import menus**. Load a reviewed JSON file or choose **Import menu** beside an establishment to get its exact identity template. Fill the source fields and items, then **Preview import** and **Import previewed dishes**. The preview shows all target venues and prices. It expires after 15 minutes and is rejected if the payload or menu changes. Imports add new dishes atomically with a receipt; they preserve existing dishes, manual edits and removed items. Conflicting names from a different source require manual review. Browser imports use the existing administrator session and CSRF protection.

**KFC source available:** `data/menus/kfc_sg_reference_20261004.json` contains 97 distinct items and SGD prices read from [KFC Singapore's official menu](https://www.kfc.com.sg/menu) on 4 October 2026. These are **chain reference prices**, not outlet-confirmed offers. Monday/app-only promotions, the explicitly discounted Famous Bowl and ambiguous duplicate meal variants were excluded. The admin **Load KFC reference menu** button matches only active imported venues named exactly `KFC`, then requires preview. Other chains are not populated with KFC data. No photos, addresses, hygiene grades, ratings or user reviews are invented.

The KFC import added **6,984 dishes across 72 listings**, including venue #9. A repeat preview found zero new rows and skipped all 6,984. The six original demo venues retain their sample dishes and any existing availability edits. Menus display the source, observation date and chain-reference caveat; edited prices are labelled as edited by an administrator. The public website has **not** received this update: the saved SSH connection timed out on 4 October.

For an existing database, stop this app and back up its database before the additive migration:

```powershell
.venv/Scripts/python.exe scripts/run_demo.py --migrate-menus
```

It adds five provenance fields and a unique `(place_id, source_name, source_item_id)` identity to `dish`, preserving dish IDs and review links. Fresh `--setup` handles this step and the listing-details migration. The schema remains **10 active + 7 legacy SQL tables**, now **93 columns**. Run both migrations on the server before starting this code there.

### Import through an API key

The optional **MENU_IMPORT_API_KEY authenticates this application's menu import API**. It does not purchase or unlock an external restaurant database. It is stored only in a private environment file; never put it in frontend JavaScript, a URL, screenshots or Git. [Google Places](https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places) does not provide an itemised menu-price field; a restaurant provider such as [Dinlr](https://www.dinlr.com/sg/support/api) needs the restaurant's authorisation. A future provider adapter must map its licensed records into the format below.

For local setup, generate the scoped key once and restart the web app:

```powershell
.venv/Scripts/python.exe scripts/configure_menu_import.py
.venv/Scripts/python.exe scripts/run_demo.py --serve
```

In another terminal, preview and then apply the verified KFC reference source:

```powershell
.venv/Scripts/python.exe scripts/import_menus.py data/menus/kfc_sg_reference_20261004.json
.venv/Scripts/python.exe scripts/import_menus.py data/menus/kfc_sg_reference_20261004.json --apply
```

Use `--env PATH` for a different private configuration and `--url https://YOUR-APPLICATION` for its matching service. The helper reads the key without printing it, refuses non-loopback HTTP and refuses redirects. Leaving the key unset disables bearer-key imports, while administrator session imports remain available.

API calls use `Authorization: Bearer <MENU_IMPORT_API_KEY>`. `GET /api/integrations/menu-targets?name=KFC` returns exact matching imported venue identities. `POST /api/integrations/menu-imports` accepts `{"menu": MENU}` for preview; submit the returned normalized `menu` and `previewToken` with `"apply": true` to apply. This key cannot access account, moderation or schema routes. A source payload has this shape (replace the example with verified data and the exact venue identity returned by the API):

```json
{
  "sourceName": "Restaurant official menu",
  "sourceUrl": "https://example.com/menu",
  "observedAt": "2026-10-04T04:00:00Z",
  "currency": "SGD",
  "isReference": false,
  "places": [{"id": 123, "name": "Exact catalogue name", "sourceId": "node/123"}],
  "items": [{"sourceId": "stable-item-id", "name": "Verified dish name", "price": "5.50", "description": "", "dietary": ""}]
}
```

Each request supports up to 100 items and 100 establishments within the 64 KB request limit. Shared multi-outlet menus must set `isReference: true`. Stable source IDs make re-imports safe; blank prices and automatic currency conversion are rejected. Stored source URLs are displayed as links, never fetched by the server.

## Reproduce with MariaDB + MongoDB in Docker

For a fresh checkout and working Docker Desktop Linux engine:

```powershell
py -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt pytest
.venv/Scripts/python.exe scripts/configure_demo.py
docker compose --env-file .env.demo up -d --wait
.venv/Scripts/python.exe scripts/run_demo.py --setup
.venv/Scripts/python.exe scripts/run_demo.py --serve
```

Configuration generation refuses to overwrite existing secrets. On this computer `.env.demo` already contains the preview configuration. Generate `.env.compose` with `--output .env.compose`, then use `--env-file .env.compose` for Docker and `--env .env.compose` for the Python launcher. Port 27018 must be free: stop only this project's portable MongoDB first, or change the compose port and matching URLs. Do not delete database volumes to resolve a port conflict.

Compose supplies MariaDB 11.4, MongoDB 8.0, authenticated application accounts, health checks and persistent volumes, with ports bound to loopback. This compose workflow is supplied but **was not successfully executed in this session**. For an existing MariaDB installation, configure a dedicated demonstration database/account in the private environment instead. Use a matching pair of SQL/Mongo databases: do not attach populated Mongo documents to unrelated SQL IDs. Keep existing volumes and their original credentials together.

## Verification and evidence

```powershell
.venv/Scripts/python.exe scripts/run_demo.py --test
```

Tests use unique disposable Mongo databases through `MONGODB_TEST_URI`. Setting `MARIADB_TEST_ADMIN_URL` also creates/drops unique disposable MariaDB test databases; otherwise SQL tests use temporary SQLite files. Use test administrator URLs only on a dedicated local instance. They do not reset the configured demo database.

After exporting private environment values, available Flask commands are `init-db`, `init-mongo`, `migrate-community`, `seed-coursework`, `query-evidence --output NEW.json`, and `lab-evidence NEW.json`. The evidence commands refuse to overwrite existing files. `.env.demo` is loaded automatically only by `scripts/run_demo.py`, not by Flask itself.

Seven original SQL community tables are preserved as a migration source. Live community routes use MongoDB. Stable IDs, unique source/seed keys and SQL phase receipts make population resumable. These operations are **not one cross-database ACID transaction**. Run only one migration/seeder at a time, with the app stopped.

## Explain the work

- [Lecturer walkthrough](docs/lecturer_walkthrough.md): presentation sequence and feature-to-code mapping.
- [Current architecture](docs/system_architecture.md): responsibilities, consistency and tradeoffs.
- [API](docs/API_design.md), [permissions](docs/roles_and_permissions.md), [manual](docs/user_manual.md).
- [Original SQL design](docs/relational_design.md): historical ERD/dictionary, partly retained for migration. Use studio metadata for the current schema.
- [Verification record](docs/verification_record.md): observed results and limitations.

Before submission, verify this revision on MariaDB + MongoDB, reproduce startup on another computer and rehearse explanations. Address the existing report comments: readable diagrams, correct architecture, sources, honest progress and evaluation. The supplied brief requires substantial work in both SQL and NoSQL, a two-page progress body in Calibri 12, a final report of at most ten pages excluding cover/references/appendix, and a video of at most ten minutes with all members. Implementation alone cannot guarantee an Excellent grade.

References: [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [MongoDB JSON Schema](https://www.mongodb.com/docs/manual/core/schema-validation/specify-json-schema/), [PyMongo indexes](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/indexes/), [OpenStreetMap copyright](https://www.openstreetmap.org/copyright).


## Database correctness update — 6 October 2026

The earlier material is retained. The new [design addendum](docs/system_architecture.md#database-design-and-evaluation-addendum--6-october-2026) is appended below the original architecture text. It explains data ownership, functional dependencies, SQL/Mongo transaction boundaries, consistency, retry semantics and benchmark methodology.

A concurrency defect in favourite saving is fixed with a native SQL upsert. The expanded suite passed **80 tests in 232.07 seconds locally** on SQLite 3.50.4 + real MongoDB 8.0.19, including **19 database evaluation experiments**. These include six-worker concurrency, partial-import recovery before/after write acknowledgement, cross-reference fault detection and controlled 30,000-record index comparisons. The recorded JSON includes raw samples, plans, timestamps, environment and a source fingerprint. See [results and limits](docs/verification_record.md#database-correctness-and-evaluation--6-october-2026).

Run `.venv/Scripts/python.exe scripts/run_database_evaluation.py --env .env.demo --full-suite` locally. On the server, omit `--env` and privately configure MARIADB_TEST_ADMIN_URL and MONGODB_TEST_URI. Tests create fresh disposable databases. The evidence page's seventh section reads the recorded results; it does not run load/failure experiments on live data.

This revision's MariaDB run and deployment are pending: NetBird currently requires login. The public site remains on the previously deployed release until the target-engine gate succeeds. The report document has not been edited.

## Lecturer feedback and portable setup - 16 October 2026

The latest work focuses on database correctness and reproducible evidence. Follow the [database evaluation guide](docs/database_evaluation_guide.md) for MongoDB operations, cross-engine consistency, concurrency/recovery invariants and controlled benchmarks. Earlier deployment claims above describe their recorded releases.

To run the project on another laptop, use the [Docker laptop guide](docs/docker_laptop_guide.md). The new `compose.laptop.yaml` includes the Python website, MariaDB, MongoDB, resumable setup, two local lecturer accounts, persistent data volumes and an isolated evaluation profile. It is separate from the older database-only `compose.yaml`. Generate `.env.laptop` as documented before starting it. No DBStudios or production credentials are needed.

```text
docker compose --env-file .env.laptop -f compose.laptop.yaml up --build -d --wait --wait-timeout 600
docker compose --env-file .env.laptop -f compose.laptop.yaml --profile evaluation run --build --rm evaluate
```

The website defaults to <http://localhost:5056/>. Administrator and normal-user passwords are generated separately in the private `.env.laptop`; the guide lists their keys and sign-in URLs. The [verification record](docs/verification_record.md) distinguishes native database tests, Compose configuration checks and blocked container execution.

Current verification: **82 tests passed on native MariaDB 11.4.13 + MongoDB 8.0.19**. Full laptop setup was repeated successfully with identical data counts and lecturer password hashes. Compose configuration passed; Docker image/container execution is still blocked by this computer's Docker Desktop startup error. The public server was not updated in this change.
