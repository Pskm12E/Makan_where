# Database implementation in the application

Makan Where performs database operations in its Python backend. It does not call a DBStudios database API or require the external dashboard. The public application uses MariaDB and MongoDB; its browser calls same-origin Flask API routes.

| Responsibility | Implementation | How it reaches the database |
| --- | --- | --- |
| SQL connection | `backend/config.py`, `backend/app.py`, `backend/models.py` | Private `DATABASE_URL` initializes Flask-SQLAlchemy. The live `mysql+pymysql` connection uses a local MariaDB Unix socket and the dedicated `makanwhere` SQL account. |
| MongoDB connection and schema | `backend/mongo.py` | `MongoClient` reads the private `MONGODB_URI`; validators and indexes are created in code. The live service uses an authenticated local Unix socket. |
| Accounts and login | `backend/routes.py`, `backend/passwords.py` | SQL INSERT/SELECT through SQLAlchemy; passwords use salted scrypt plus a private pepper. Each API request resolves the user's current SQL role. |
| Catalogue and menu CRUD | `backend/routes.py`, `backend/services.py` | Application-controlled SQL queries and commits; admin authorization, validated inputs and database keys/checks protect writes. |
| Favourites | `backend/routes.py` | SQL records use the current session's user ID and the composite user/place key. |
| Menu imports | `backend/menu_imports.py` | Validated preview plus atomic SQL insert/receipt transaction. Session/CSRF or the narrowly scoped menu API key authorizes the application route. |
| Reviews, discussions and replies | `backend/community.py`, `backend/mongo.py` | PyMongo document operations; Python validates SQL references before writes. Ratings use a Mongo aggregation pipeline. |
| Votes and moderation | `backend/community.py` | Mongo unique upserts and conditional updates enforce vote identity and moderation state. |
| Analytics | `backend/analytics.py` | SQLAlchemy SELECTs/aggregates plus PyMongo rating aggregation. |
| Schema and migrations | `backend/models.py`, `backend/migrations.py`, `backend/commands.py` | SQL models, additive migration statements and CLI commands are part of the repository. |
| Database evidence page | `database-lab.html`, `js/database-lab.js`, `backend/database_lab.py`, `backend/course_evidence.py`, `backend/query_evidence.py` | Fixed Python SQL/Mongo queries show counts, keys, plans, validators and integrity checks. This page is part of Makan Where. It is not the external DBStudios product or an arbitrary SQL console. |

## Lecturer access

Use `demo_lecturer` at [administrator sign-in](https://makanwhere.4bytedigi.com/auth.html?next=admin.html) for catalogue, menu, moderation and database evidence controls. Use `lecturer_user` at [normal sign-in](https://makanwhere.4bytedigi.com/auth.html?mode=login) for browsing, favourites, reviews and discussions. Their different generated passwords are delivered privately to the project owner and are not included in source or this document.

The normal account has the SQL role `user`. It cannot access admin schema/evidence APIs or authenticate with the admin-only option. The admin account has the SQL role `admin`. Hiding buttons is not the access-control mechanism: `backend/services.py` enforces roles in the backend.

## Hosting references

The host's existing SSH configuration and shared Cloudflare tunnel retain historical `dbstudios` names. `deploy/install_host.py` uses those infrastructure names and checks neighbouring site health. It does not use DBStudios for Makan Where's schema, CRUD, queries or authentication. Legacy compatibility/inspection helpers were removed from the project and are excluded from new releases. The standalone `compose.yaml` defines only MariaDB and MongoDB services and does not require DBStudios.

The application service uses `PrivateNetwork=yes` and permits Unix sockets only. Its database configuration is private; full connection URLs, passwords and hashes are not exposed in the evidence page.

## Database evaluation additions — 6 October 2026

| Responsibility | Implementation | Evidence |
| --- | --- | --- |
| Concurrent favourite saves | `backend/routes.py`, `favourite()` | Native SQL upsert protected by the composite primary key; six workers, four place identities, 24 requests. |
| Behavioural evaluation | `tests/test_database_evaluation.py` | Mongo lifecycle/atomicity, six cross-reference faults, archived-parent visibility, SQL lookup failure, concurrent writes/moderation, partial-import recovery and reconnect behaviour. |
| Controlled comparisons | SQL/Mongo benchmark tests in the same evaluation file | Deterministic 30,000-record workloads, identical result checksums, three warm-ups, 20 alternating measured repetitions, raw latency samples and plans. |
| Reproducible artifact | `scripts/run_database_evaluation.py` | Engine/isolation/topology/platform metadata, test outcomes, source hash, timestamps and limitations; missing-engine skips do not count as success. |
| Evidence access | `backend/evaluation.py`, `backend/database_lab.py`, `js/database-evaluation.js` | Admin-only recorded evidence; stale/missing records labelled; no browser-triggered load/fault testing against production. |
| Target-engine release gate | `deploy/install_guest.py` | Run the complete suite in fresh disposable MariaDB/MongoDB databases and save the release's own artifact before activation. |

## Implemented refinement — 27 October 2026

| Responsibility | Current implementation | Evidence |
| --- | --- | --- |
| Shared menu facts and outlet overrides | `models.py`, `catalogue_design.py`, `menu_imports.py` | Source publication/item records; stable `dish` offering IDs; exact-source upgrade; old observation dates and outlet edits retained |
| Flat tag memberships | `Tag`, `PlaceTag`, `FoodPlace.tags` | Composite junction key; cleared legacy list; upgrade/rerun tests |
| Database domains and moderation states | SQL CHECK/FK rules; SQLite upgrade triggers; `mongo.VALIDATORS` | Direct invalid writes rejected without partial changes |
| Optimistic post edits | `community.change_content`, If-Match revision predicate | One winner for concurrent same-revision edits; stale edit/removal rejected |
| Retry-safe content creation | Request key/hash inside the content document plus unique author/key index | Same-key concurrent creates and lost-ack retries retain one ID; changed payload rejected |
| Restart/restore probe | `scripts/recovery_probe.py`; Docker `recovery` profile | Committed snapshot after graceful restart, typed logical restore into new databases, complete equality and reference audit |

The physical `dish` name is retained for existing references. Its administrator record projection returns effective name/price; stored shared facts and local overrides are inspected in their corresponding fields/tables. The original standalone `design_v2.py` is a teaching prototype; runtime ownership and compatibility semantics are documented in the latest architecture addendum. No distributed SQL/Mongo transaction or entire-schema BCNF proof is claimed.
