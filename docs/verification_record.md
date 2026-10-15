# Verification record

## Combined database evidence — 4 October 2026, 08:44 UTC

- Deployed release `020722529efc502a`; **61 tests passed in 106.70 seconds** against MariaDB 10.11.14 and MongoDB 8.0.19. Backup: `/var/backups/makanwhere/20261004T084109Z` on the app VM. Both database health checks and neighbouring origins passed.
- Replaced mutually exclusive tabs with six continuous sections, an overview showing all six areas, expanded details, and shared site navigation, typography and orange/cream colours. **Run all checks** collects the snapshot, constraint probes and password checks sequentially; controls prevent overlapping runs. The combined export retains snapshot, probe and password results.
- The public browser completed **9/9 constraint checks and 3/3 password checks** through the new combined action. All six sections were displayed, all 39 details were expanded, and no document horizontal overflow or browser warnings/errors were observed. Counts: 8,421 venues, 7,034 menu rows, 756 community documents and 600 votes. [Live screenshot](evidence/combined-evidence-live-2026-10-04.jpg).
- Local browser verification also passed the combined action, collapse/expand controls (all six sections stay visible) and JSON download. The downloaded JSON contained all six evidence areas, six SQL queries, nine passing constraint probes and three passing password checks. The local preview used SQLite/MongoDB; the public run and deployment tests used MariaDB/MongoDB. Mobile viewport behaviour was not separately tested.
- Updated the live administrator display name from `Demonstration Lecturer` to `Administrator` through the profile API, retaining its username, password and role. Fictional accounts/posts and sample data remain labelled. The report and consultation documents were not edited.

## Lecturer accounts and direct database access — 4 October 2026

- Deployed release `a8f205aec3849494`; **61 tests passed in 105.59 seconds** on MariaDB 10.11.14 and MongoDB 8.0.19. Backup: `/var/backups/makanwhere/20261004T081338Z` on the app VM. Application and neighbouring health checks passed.
- Reused `demo_lecturer` with SQL role `admin` and created `lecturer_user` with role `user` through the public registration API. Separate generated credentials were delivered privately. Both public HTTPS logins passed; normal-user admin-only sign-in and admin schema/evidence requests returned 403. A favourite was added, read back and removed, restoring the account's initial state. Test HTTP sessions were logged out.
- Under the actual application identity, SQLAlchemy used `mysql+pymysql` over `/run/mysqld/mysqld.sock` as `makanwhere@localhost`; PyMongo reached authenticated MongoDB over its private Unix socket. The service has `PrivateNetwork=yes`, `RestrictAddressFamilies=AF_UNIX` and requires MariaDB/MongoDB, not the DBStudios application. No database credentials were included in the audit output.
- Renamed the in-app page/navigation to **Database evidence** and removed obsolete external DBStudios compatibility/inspection helpers from the source/package, retaining private local backups. Existing host SSH/tunnel names and neighbour health checks are infrastructure references. [Database code map](database_code_map.md) identifies the actual connection, CRUD, schema, migration and aggregation code.
- Corrected old evidence captions: menu totals include the SQL catalogue, and labelled example conversations on imported venues are distinct from the bulk sample fixtures. Browser checks verified normal-user profile and administrator dashboard/evidence access. [User view](evidence/lecturer-user-view-2026-10-04.jpg), [database evidence view](evidence/lecturer-database-evidence-2026-10-04.jpg). The report and consultation documents were not edited.

## Live example conversations — 4 October 2026, 07:54 UTC

- Deployed release `77d931deeec7ea3c`; **61 tests passed in 112.33 seconds** on MariaDB 10.11.14 and MongoDB 8.0.19. JavaScript syntax and whitespace checks passed. Pre-update database/configuration backup: `/var/backups/makanwhere/20261004T075256Z` on the app VM. Both database health checks and neighbouring origins passed.
- Added **12 fictional reviews, 8 discussion threads and 16 replies** across KFC #9, McDonald's #10/#14 and Suki-ya #15. Every document has `is_demo=true` and `is_example=true`, clearly labelled titles/text, and a dedicated Example Guest author. These records are distinct from the older bulk coursework fixtures on sample venues.
- The shared rating aggregation excludes `is_example=true`; the UI distinguishes example stars and counts. All four venue ratings stayed unchanged after insertion. Normal user reviews remain included. Repeated preview proposed **zero additions**; regression checks confirm edits/removals survive a repeat and identity conflicts stop before writes.
- Public API checks verified the 3 reviews, 2 threads and 4 correctly linked replies at each venue. Browser checks confirmed the labels, rating explanation and discussion replies with no console errors. [Verification JSON](evidence/server-community-examples-2026-10-04.json), [reviews screenshot](evidence/example-reviews-live-2026-10-04.jpg), [threads screenshot](evidence/example-threads-live-2026-10-04.jpg).
- The post-insertion reference audit passed. No actual user content was replaced. Report/consultation documents remain unchanged, and administrator-account selection remains pending from the previous deployment.

## Live server deployment — 4 October 2026, 07:36 UTC

- Public release: `11a89bf538af436a`; MariaDB **10.11.14** and MongoDB **8.0.19**. The final VM run passed **59 tests in 106.33 seconds**, using disposable test databases. This supersedes the earlier current-revision MariaDB and SSH limitations below.
- Corrected two deployment defects found before switching the application: the MongoDB bootstrap now uses a percent-encoded Unix-socket URI, and the catalogue migration updates only old-schema columns instead of loading newer ORM fields and dish relationships. The migration regression test now removes listing enrichment and (on MariaDB) new dish columns before exercising the upgrade. Failed attempts retained their diagnostics; the prior application was restored after the migration failure.
- Installer completed additive migrations, legacy community migration, labelled sample population and sourced listing enrichment. SQL, clean MongoDB data and configuration backups are on the app VM at `/var/backups/makanwhere/20261004T073435Z`. No local database or demonstration credentials were copied to production. The neighbouring DBStudios and event origins remained healthy.
- Enabled a new server-only scoped API key and imported the packaged KFC/Suki-Ya reference menus through the running HTTP service over its Unix socket: **6,984 + 32 new menu rows**, across **72 + 4 venues**. Each repeat preview returned zero additions. The key was neither displayed nor placed in frontend code.
- Public HTTPS checks: both engines connected; **8,421 venues/photos**, all photos explicitly illustrative; **1,481 websites**, **267 menu links**, **1,183 phones**, **82 venues with available dishes**, **7,033 active dishes**, **273 venues with dishes or menu links**. KFC #9 exposes 97 attributed reference items. Admin/menu-target endpoints returned 401 without authentication. [Public verification JSON](evidence/server-deployment-2026-10-04.json).
- All **nine constraint probes passed** under the application identity. The post-import audit found zero SQL orphans, zero Mongo cross-reference errors, zero duplicate source identities and zero duplicate vote groups. Menu-import receipts and coverage were read using the application identity. [Database evidence](evidence/server-database-audit-2026-10-04.json).
- Browser verification: public KFC photo/menu/source labels rendered; homepage McDonald's and Suki-Ya photos loaded, with no console errors. [Full live KFC page](evidence/server-kfc-2026-10-04.jpg).
- Remaining limit: **no server administrator account exists**. The user has been asked which existing app account should receive the role; authenticated production admin-browser checks remain pending. This deployment does not verify concurrency/recovery demonstrations or claim complete real outlet/menu coverage. The report and consultation documents were not edited.

## Listing photography and enrichment — 4 October 2026

- Backed up the local SQLite database before applying the additive `food_place.enrichment` migration. Current declarations: 17 tables and 93 columns. Report/consultation documents remain unchanged.
- Filled 1,843 listings with retained, exact-identity OSM business details and reviewed official chain links: 1,481 websites, 267 menu links and 1,183 business phones. Five malformed source fields were skipped. A repeated import proposed zero changes.
- Every one of 8,421 active listings returns an attributed illustrative image; there are currently **zero verified outlet photos**. All six retained image URLs returned HTTP 200 and image/jpeg. Browser checks confirmed the homepage cards render their actual images and visible illustrative labels.
- Added eight Suki-Ya reference buffet options to four exact-name venues (32 dishes). The active catalogue now has 82 venues with available dishes and 273 with dishes or a source menu link. An existing removed sample dish remains removed. McDonald's detail pages expose 45 named menu highlights and their official source, with no invented prices.
- `scripts/run_demo.py --test`: **59 passed in 130.14 seconds** on temporary SQLite plus real MongoDB. New checks cover safe photo/business URLs, admin/CSRF protection, public field roundtrip, exact source/name matching, invalid-source rejection, preservation of administrator-cleared fields, import preview/repeat behaviour and migration of an old table without changing its existing row. These are not current MariaDB runtime results.
- Browser checks cover homepage photo loading, McDonald's menu highlights/source links/map, administrator photo preview and coverage counts. JavaScript syntax checks passed. The admin editor loads the full detail record before editing so compact-catalogue omissions cannot clear existing hours/descriptions.
- The release builder completed and includes all enrichment/menu sources. NetBird reports `NeedsLogin`; SSH timed out. **No production deployment or production database change occurred.**

## Menu import and admin workflow — 4 October 2026

- Ran `.venv/Scripts/python.exe scripts/run_demo.py --test`: **53 passed in 107.73 seconds**, using temporary SQLite databases and real authenticated MongoDB. Seven new tests cover admin/CSRF/key scope, preview without writes, repeat-import preservation, invalid batches and venue identity, stale/tampered/cross-actor preview rejection, reference labelling, SQL rollback on receipt failure and additive migration from an old dish table. They do not establish full concurrent-workload behaviour or MariaDB compatibility.
- Backed up the local SQLite database under ignored `work/backups` with the app stopped. Applied `migrate-menus`; five columns and the source identity index were added without resetting existing dish IDs. Current declarations: 17 SQL tables, 92 columns.
- Read KFC Singapore's visible public menu in the browser. Retained 97 distinct item names/prices in the source JSON, excluding explicit discount/day/app offers and an ambiguous duplicate meal variant. Loaded 6,984 chain-reference dishes into 72 exact-name KFC listings, including #9. Repeat preview: zero additions, 6,984 skipped, zero conflicts. Source/date/reference labels are visible in the local venue page.
- The local bearer key is stored in ignored `.env.demo`; it was not printed or added to frontend files. The same importer is available in the admin panel using session/CSRF authorization.
- Browser checks confirmed the KFC detail page, administrator coverage/filter/history and a repeated import preview with no additions. The menu expands from eight visible dishes to all 97 and collapses again. Both pages reported no browser warnings/errors. [Menu screenshot](evidence/kfc-menu-2026-10-04.jpg).
- The saved `ssh -o BatchMode=yes -o ConnectTimeout=8 4bytedigi hostname` connection timed out. **No production deployment or production data import occurred.** Other venues' missing menus/photos/addresses/ratings remain missing unless a real source or user contribution supplies them.
- The cloud report and consultation notes were not edited. Their 46-test statement describes the prior suite; it is now 53. The current local engine remains SQLite + MongoDB, so MariaDB execution claims still require qualification.

## Two-database implementation and Database studio — 28 September 2026

Current environment: Python 3.14.7, Flask 3.1.3, SQLAlchemy 2.0.54, SQLite 3.50.4, PyMongo 4.18.2 and a real authenticated MongoDB 8.0.19 server bound to loopback. Community API workflows use MongoDB; the seven legacy SQL community tables remain empty in the new demo.

Observed: **35 tests passed in 103.69 seconds**, including actual Mongo validators/indexes, CRUD/ownership/moderation, cross-database orphan detection, seek pagination, deliberate Mongo connection failure (503 without SQL fallback), conflict-safe migration, resumable population, salted/peppered password checks and legacy upgrades. The original 25 API/import/analytics tests also passed after migration. Later changes to sample labels are checked with the focused analytics suite.

The populated local database contains 8,421 venues, 18 sample dishes, 61 accounts (60 fictional users and one lecturer), 120 favourites and 300 discovery events in SQL; MongoDB contains 720 content documents (600 reviews, 30 threads, 90 replies), 600 votes and 20 reports. A second setup added **zero business records**. All nine live constraint probes passed, with SQL writes rolled back and the private Mongo probe collection removed. The reference/duplicate audit found zero orphans and zero duplicate source/vote identities; same-name/address candidates are retained for manual review.

The browser verified administrator login, visible population counts, tab navigation, nine PASS results and the password demonstration (different salts, valid password accepted, wrong pepper rejected). No JavaScript console errors were observed. Python compilation and modified JavaScript syntax checks passed. The [captured evidence](evidence/database-studio-sqlite-mongo-2026-09-28.json) contains actual SQL plans/results, Mongo schema/indexes/aggregation and a feed EXPLAIN using `place_feed`: ten keys and ten documents examined for ten returned rows in this capture. This is not a benchmark.

**Limits:** MariaDB for this revision remains unverified. The installed server's project credentials were unavailable, its isolated initialization executable was blocked by Windows Application Control, and Docker did not respond. The preview explicitly says SQLite. Docker compose and fresh-machine startup instructions are supplied but unverified. No production deployment was performed. Earlier MariaDB results below are historical and must not be reused to claim the current two-engine revision passed MariaDB tests.

The live report remains textually unchanged with review comments only. Code completion does not by itself establish an Excellent grade or remove the need for report revisions and presentation explanations.

## SQL analytics and report review 28 September 2026

The Food insights page now uses six SQL queries in `backend/analytics.py` via
`GET /api/analytics`. Added a grouped menu-price query with `HAVING`, sample-price
labels, and a read-only `query-evidence` CLI that captures the same SELECTs with
live plans and results. Invalid JSON enumeration values, oversized numeric IDs
and non-ASCII CSRF tokens now return client errors rather than uncaught errors.

- Python **3.14.7**, Flask **3.1.3**, SQLAlchemy **2.0.54**, SQLite **3.50.4**.
- Before changes: **21 passed in 20.18 seconds** on SQLite.
- After changes: **25 passed in 20.97 seconds** on SQLite, using
  `.\.venv\Scripts\python.exe -m pytest tests -q`.
- New checks cover aggregate multiplication, removed reviews, archived places,
  unavailable dishes, the SGD 12 HAVING boundary, missing-menu exclusion,
  historical discovery totals, real EXPLAIN output, evidence-file preservation
  and invalid input handling.
- The first new-test run found two test-fixture mistakes (a wrong venue name and
  access to a detached ORM instance). Both were corrected before the passing run.
- An isolated SQLite database successfully loaded **8,421 places and 18 dishes**
  from the six sample venues plus retained OSM CSV. All six query plans executed;
  the empty-community analytics response was **768 bytes** for this dataset.
  This is a response-size observation, not a latency or throughput benchmark.
  The [SQLite query evidence](evidence/sqlite-analytics-2026-09-28.json) is retained
  with its engine version, row counts, generated SQL, plans and results.
- Browser inspection of the local analytics page confirmed all six cards,
  correct empty states, cuisine counts, menu averages and sample labels. No
  warning/error entries were returned by the browser's captured console log.
- Changed JavaScript files passed Node syntax checks; `git diff --check` passed.

Docker Desktop was initially stopped. Its startup/inspection commands did not
become responsive, and the waiting CLI processes were terminated. No existing
containers or databases were modified and no temporary MariaDB container was
created. **The new changes have not been verified against MariaDB.** The earlier
MariaDB results below apply to the earlier code only. MongoDB, cross-engine
failure behaviour, live deployment and performance benchmarking remain unverified.

See [the lecturer walkthrough](lecturer_walkthrough.md) for feature-to-query
traceability and the outstanding assessment work. The progress-report review
adds comments only; report wording and layout remain unchanged.

## MariaDB startup and integration checks: 24 September 2026

The [root README](../README.md) now provides local MariaDB configuration, initialization, data loading, administrator setup, startup and inspection instructions. Its database/application workflow was exercised against an isolated local Docker container with generated credentials and a dedicated named volume. Temporary host ports were used to avoid existing services; the README uses fixed localhost ports 3307 and 5055.

- Python: **3.14.7**.
- Docker server: **29.6.2**, Linux containers.
- Database: **11.4.13-MariaDB-ubu2404**, image `mariadb:11.4`.
- Pulled image digest: `mariadb@sha256:70cc072b29b4a89ae07abb2d4da2c64678a7f2dfe092751bb51c87d67dc1338b`.
- Command: `.\.venv\Scripts\python.exe -m pytest tests -q`, with `MARIADB_TEST_ADMIN_URL` directed at the isolated container.
- Result: **16 passed in 40.13 seconds**. Database-backed fixtures created and removed temporary test schemas.

The separate setup/API check verified:

1. A fresh MariaDB container became healthy using the official image health-check script.
2. `init-db` created 16 tables and `seed-demo` loaded six venues and 18 dishes.
3. The retained CSV preview found 8,415 new listings; applying it produced 8,421 total places. Reapplying added zero listings and skipped all 8,415 existing source identities.
4. Waitress served a connected health endpoint and an 8,421-place catalogue through HTTP.
5. Registration could not grant a requested admin role; an ordinary user received 403 on admin place creation. `set-admin` promoted the registered account, which could then add a place, add a dish and archive the place through the API.
6. After container restart, the named volume retained the registered account and 8,422 place rows, including the newly archived demonstration place.

The verification used application code directly against MariaDB, without a DBstudios connection. The temporary container and named volume were removed afterwards. No production database was used or modified. An initial verification-harness run used a dynamically published host port and could not reconnect after restart; the harness was changed to reserve a fixed host port, matching the README's approach, and the complete run then passed.

All 17 PowerShell blocks in the README passed syntax parsing. Its credential-generation and environment-loading blocks were also executed with a temporary private env file, checking the generated secret lengths, resulting connection URL and local cookie setting. The file was removed without displaying credentials. Local documentation links, code fences and the referenced architecture SVG passed validation.

These results establish the tested local MariaDB workflow and existing test cases. They do not establish MongoDB integration, browser usability, live deployment health, or compatibility with every Python/database version. No application implementation was changed for this documentation task.

## Earlier SQLite assessment

Date: 23 September 2026.

- Command: `.\.venv\Scripts\python.exe -m pytest tests -q`
- Result: **16 passed in 27.11 seconds**.
- Engine: SQLite; `MARIADB_TEST_ADMIN_URL` was not configured.
- Scope: existing API, authorization, relational constraints, imports and catalogue tests.
- Not established by this run: MariaDB compatibility, MongoDB integration, live deployment health or browser usability.
- ORM metadata: 16 tables and 84 columns.
- Retained catalogue CSV: 8,415 rows.
- SHA-256: `80db589d7a486154810b953f37185b3b7502b10d7ad9fa57c2891ff76444b36f`.

The test output above was observed during this assessment. Rerun both engines after implementation changes and preserve the new evidence with its environment and date. Historical deployment claims are not substituted for new results.
# Course alignment — 30 September 2026

- Reviewed Lectures 1–5 (including revised Lecture 4) and Lab 1–4 material; added the [course map](course_alignment.md) and Database Studio → Weeks 1–5.
- Command: `.venv/Scripts/python.exe scripts/run_demo.py --test`. Result: **46 passed in 99.73 seconds**. SQLite plus authenticated MongoDB 8.0.19; this includes six new semantic tests and the existing API/integration/deployment tests. Current MariaDB compatibility remains unverified.
- New tests cover closure cycles and minimal candidate keys, projected implied FDs/BCNF, bag/set multiplicity, SQL NULL and empty aggregates, NOT IN/NULL, ANY/ALL empty sets, outer-join counts, archived/unavailable/empty venues, and read-only comparisons beyond the ten-row preview.
- Browser at `127.0.0.1:5055`: Week 1–5 tab renders; changing closure from place_id to area_id shows the latter is not a superkey of the joined Venue projection. All three live query pairs have equal complete result multisets. The correlated count and grouped LEFT JOIN each return **8,421 venues**, retaining venues with zero available dishes; the actual SQLite plans show the dish.place_id index. Browser error/warning log was empty for this check.
- The 24 tiny SQL examples use inline CTE fixtures, not stored application rows. The three live query comparisons read existing data. Original report pages/comments are preserved; only the appended revised section and its separate references are updated.
- Verified the browser's downloaded evidence JSON contains all 24 examples and three comparisons. Rendered the cloud report after upload: **7 pages**, with the revised body on pages 5–6 and references on page 7. Original pages 1–4 are pixel-identical to the prior verified rendering; all 13 comments remain byte-preserved. Cloud DOCX readback matches the local file exactly.
- No deployment, database reset, new performance claim, or whole-schema BCNF claim was made for this change.

# Website and deployment preparation — 28 September 2026

This entry records the current revision; older MariaDB results below belong to earlier revisions.

- Re-ran 35 API/integration tests: **35 passed in 99.76 seconds**, temporary SQLite databases and authenticated MongoDB 8.0.19. Added five offline deployment boundary tests: **5 passed** (archive traversal/link rejection, overwrite refusal, environment preservation and multiline rejection). This revision has not yet been tested on MariaDB.
- Browser checks at `127.0.0.1:5055`: sample filter returns six venues; imported filter returns 8,415; imported search for `sushi` returns 127. Review pages advance from page 1 to page 2. A new temporary review persists after reload and appears first; soft removal hides it, retaining its stored document as designed. Favourite add/remove persists across reload. No browser error/warning entries were observed for these flows.
- Improved home-page navigation, sample discovery, source filtering and review pagination/section shortcuts. Generated menus and community activity remain visibly labelled.
- Prepared offline Linux CPython 3.12 wheels, source release and the official MongoDB Ubuntu 24.04 8.0.19 archive, verified against vendor SHA-256 `343c7a725beff28b546ff77633603441ec2bd67cb5c1d55f3129cf0a70dd2981`.
- Public domain remains on its previous SQL-only release. NetBird reports `NeedsLogin`; SSH to the saved server address times out. No server files, databases or services were changed. Linux service deployment, actual MariaDB constraint results and public browser acceptance remain outstanding. See [deployment instructions](../deploy/README.md).


## Database correctness and evaluation — 6 October 2026

The earlier entries are retained as historical records.

- Reproduced an actual concurrency bug: six simultaneous favourite PUTs could return 409 after a SELECT-then-INSERT race. Replaced this with native SQLite/MariaDB upserts that retain one composite-key pair and its original saved time; unsave uses one predicate DELETE.
- Expanded regression suite: **80 passed in 232.07 seconds**, no skips, on **SQLite 3.50.4 + real MongoDB 8.0.19**. The full artifact records 232.955 seconds including runner overhead. These are local results, not current MariaDB results. [Recorded JSON](evidence/database-evaluation.json) contains 19 experiments with expected invariants and observations; the source fingerprint matched after the run.
- Six-worker experiments: 24 favourite saves retained four user/place pairs, 24 vote PUTs retained one vote, 24 concurrent thread inserts received distinct IDs, and six competing report resolutions produced one 200 and five 409 responses with the winner's fields intact.
- Cross-database experiments: six separately injected reference faults were detected; SQL archive preserved identity while hiding related public Mongo content; a failed SQL reference lookup caused 503 and zero Mongo inserts, followed by a successful retry after restoration. Mongo document validation rejected an invalid multi-field update atomically.
- Recovery: population stopped with 17/18 Mongo documents after SQL activity committed, at faults before write and after write/before acknowledgement. Both resumed to 720 content documents, 600 votes and 20 reports without additional SQL activity, retained a manual edit, and added zero business records on another rerun. Actual SQL connection closure rolled back uncommitted data; an independent Mongo client read an acknowledged write.
- Controlled SQL comparison: 30,018 dish rows, three warm-ups and 20 measured repetitions per variant, alternating order, equal ordered results. SQLite indexed median **0.2025 ms**, scan median **0.5262 ms**; p95 **0.5804 / 0.8097 ms**. Default plan chose ix_dish_place_id. SQL EXPLAIN is an optimizer plan, not actual row-work measurement.
- Controlled Mongo comparison: 30,000 documents, same warm-up/repetition/order method and equal 20-row results. Indexed median **1.7569 ms**, scan median **34.0702 ms**; p95 **2.3227 / 43.3114 ms**. executionStats measured **20 versus 30,000 documents examined**. These are warm-cache synthetic measurements on one machine, not production load or a SQL-versus-Mongo comparison.
- Explicitly reproduced a remaining limit: a response read can fail after a content insert committed, giving 503 with one stored document. Content POSTs have no automatic retry-deduplication contract. Ordinary simultaneous edits remain last-write-wins. No distributed ACID, process-crash durability, replica failover or backup-restore result is claimed.
- Added admin-only recorded-evaluation access with missing/stale-source handling and included it in the combined JSON snapshot/export. The deployment gate now requires full current-source MariaDB/MongoDB evaluation evidence under the application identity.
- Appended the database design addendum beneath the existing architecture text. The original write-up, report and consultation documents were preserved. NetBird remains NeedsLogin, so this revision has not been deployed or evaluated on MariaDB yet.
- Browser verification: the local evidence section displayed all 19 experiments, 80 passed tests, the SQLite/Mongo engine labels and matching source fingerprint, with no warnings/errors. A preceding older artifact was correctly marked STALE. The downloaded combined JSON included all 19 current experiments. [Local evidence screenshot](evidence/database-evaluation-local-2026-10-06.jpg). The release package was prepared; five offline deployment boundary checks also passed after the installer update.


## Proposed logical design validation - 6 October 2026

This entry is separate from the 80-test application evaluation above.

- Command: `.venv/Scripts/python.exe scripts/verify_design_v2.py --env .env.demo`. Result: **19 checks passed**, SQLite **3.50.4** and MongoDB **8.0.19**. [Machine-readable observations](evidence/design-v2-validation.json) retain input/code SHA-256 values and the generated DDL fingerprint.
- Formal checks enumerate projected FDs and candidate keys for Publication, Entry and Offering, check BCNF under the declared business dependencies, establish both binary lossless splits and separately establish dependency preservation.
- Two retained reference sources supply 105 shared entries. A fixture with 76 outlet identities reconstructs 7,016 outlet-item relationships. The complete multiset comparison covers 12 fields, including description, dietary label, price, source identity, source URL, observation time and reference status. These are fixture identities mirroring import cardinalities, not a read or backfill of the production catalogue.
- A local override preserves a zero price and affects only one offering. Inserting a newer synthetic publication and switching references in one SQL transaction retains old source entries, all offering IDs and the outlet override. SQL rejects missing publication parents, mismatched composite references, duplicate offering/tag/fingerprint keys, a negative override and deletion of a referenced publication.
- Actual MongoDB validators reject an unknown subtype, a thread with review-only fields, more than 20 embedded feedback items and a duplicate user/content vote. Probes use only a unique disposable database, removed afterwards.
- Five new MariaDB tables are emitted with InnoDB DDL, but **this DDL has not been executed on MariaDB**, the app still uses its current models, and no live migration has been implemented or run. No new latency or server deployment result is claimed.
- The original relational write-up was preserved byte-for-byte and the revised explanation appended below it. The schema exporter now retains that authored addendum; two successive regenerations in a temporary file preserved it exactly. The cloud report and consultation document were not edited.

## Lecturer feedback and portable setup verification - 16 October 2026

Earlier entries are historical. This run evaluates the implemented application schema; the menu-design proposal has not been migrated.

- **82 tests passed in 258.84 seconds**, with no skips, on native Windows **MariaDB 11.4.13 + MongoDB 8.0.19**. Total runner time was 259.759 seconds. The code fingerprint remained unchanged. [Full recorded artifact](evidence/database-evaluation-2026-10-16-native.json) contains all 19 database experiments, package versions, SQL isolation (`REPEATABLE READ`) and standalone Mongo topology. This is a real MariaDB result, but not a Docker or live-server result.
- Dedicated test servers bound only to loopback ports 33028/27028 and used new directories under ignored `work/runtime`. Tests created/dropped their own unique databases. Portable MariaDB came from the official archive; its ZIP matched vendor SHA-256 `d62986d433eeebfde218560b276103831604a61e929e87f1a17f5aebd80257e2`. No Windows database service was installed. An initial test-launch credential configuration was corrected and verified before the successful full rerun.
- SQL benchmark: 30,018 rows, identical 20-row results, 3 warm-ups and 20 alternating measured pairs. Indexed median/p95 **0.8788 / 1.2847 ms**; scan **7.1236 / 7.5113 ms**. Additional untimed MariaDB ANALYZE samples measured **20 rows with one loop** using `ix_dish_place_id`, versus **30,018 rows with one loop** using access type ALL. The forced scan excludes the primary index as well as secondary indexes. Full observed plans remain in the artifact.
- Mongo benchmark: 30,000 documents, same paired method and identical 20-row results. Indexed median/p95 **1.4203 / 1.8386 ms**; scan **29.1552 / 39.4306 ms**. Timings are specific to this workload/host; neither general production speed nor a cross-engine performance ranking is claimed.
- Ran `scripts/laptop_setup.py` twice against the isolated native engines using the application SQL account. First setup took **43.825 s**, repeat **7.559 s**. Both retained **8,421 venues, 7,034 dishes, 62 accounts, 720 community documents, 600 votes and 20 reports**. Repeat imports added zero menu rows; counts and lecturer password hashes stayed identical. Both integrity audits were clean. [Setup observations](evidence/laptop-setup-native-2026-10-16.json).
- Verified both lecturer roles can log in. The administrator received current passing evaluation evidence; the normal user received 403. New regression tests cover private unique credential creation, overwrite refusal, retained account hashes and conflicting credentials. Web evidence can now read a configured read-only artifact volume through `DATABASE_EVALUATION_FILE`.
- `docker compose --env-file .env.laptop -f compose.laptop.yaml config --quiet` passed. Resolved configuration checks confirmed private database ports, localhost web binding, no root/test credentials in the web service, successful-setup dependency and read-only web evidence mount. Python compilation, JavaScript syntax and local guide links passed.
- **Docker image build and container execution remain unverified on this computer.** Docker Desktop 4.85.0 failed during its own Inference manager/Secrets Engine listener startup. Its data was not factory-reset; stale zero-byte listener files were retained under backup names. Native test results above do not establish container networking, image builds, Linux permissions, Docker volume persistence or other laptop architectures. Repeat the documented Compose flow on a working Docker engine.
- Added the [Docker laptop guide](docker_laptop_guide.md) and [feedback-to-evidence guide](database_evaluation_guide.md), with links appended to the existing README/manual. The report, consultation document and public server were not changed.
