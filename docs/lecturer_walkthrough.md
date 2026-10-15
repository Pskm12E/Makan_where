# Lecturer walkthrough

Open `database-lab.html` on the running Flask app and sign in as an administrator. Identify the actual engine from its badge. The local preview is SQLite + real MongoDB. The live server uses MariaDB + MongoDB, with the latest verification recorded in verification_record.md. Use database_code_map.md to trace database operations to the Python code.

## Eight-minute demonstration

1. **Population (one minute):** show the 8,415-row source, attribution and SHA-256. Explain missing fields. Contrast it with generated sample venues/menus/community. Show the repeat-import preview: 8,415 skipped, zero new rows. Expand the completed population receipt to show repeat-run additions.
2. **Keys (one minute):** inspect `favourite`: `(user_id, place_id)` is a composite PK, with two FKs. Show the source-pair UNIQUE rule. Venue names are not globally unique. A nullable source pair is not an unconditional candidate key.
3. **Integrity (one minute):** run constraint tests. Explain actual errors for duplicate PK/unique value, orphan dish, negative price, missing required value, invalid Mongo rating/subtype and repeated vote pair. SQL changes roll back; Mongo validators/indexes are copied from live metadata into a disposable collection.
4. **Dependencies (one minute):** explain `place_id → area_id → area_name`, the repeated-name update anomaly and decomposition into venue/area relations. The join is lossless because area_id is a key of area. A PK alone does not prove the entire relation is in 3NF.
5. **Queries (two minutes):** show HAVING and the LEFT JOIN menu view. Explain COUNT(dish_id) versus COUNT(*) and NULL prices. Show NOT EXISTS, DISTINCT, EXPLAIN and Mongo `$match/$group/$sort`. Separate aggregates avoid reviews × favourites × dishes multiplication.
6. **Passwords (one minute):** run the dummy example. Same password, different random salts/hashes; wrong pepper fails. The pepper stays outside the database. Never display real credentials. Explain legacy login upgrades and the consequences of losing the pepper.
7. **Application (one minute):** create/edit/remove a review at a sample venue and vote twice for one persisted vote. Trace accounts/catalogue to SQL and content/ratings to MongoDB. Export the evidence and state verification limits.

## Trace concepts to code

| Concept | Implementation | Evidence |
| --- | --- | --- |
| Import validation, SQL transaction, duplicate identity | `backend/imports.py`, `models.py` | import tests; preview and checksum |
| Resumable population | `population.py`, SQL phase receipts, Mongo seed keys | repeat-run test, before/after counts |
| PK/FK/UNIQUE/CHECK/NOT NULL | `models.py`, `database_lab.constraint_probes` | live metadata and rollback-only tests |
| Document subtypes / bounded embedding | `mongo.py`, `community.dish_feedback` | direct database rejection and API tests |
| Community CRUD / moderation | `community.py` | ownership, visibility, vote and resolution tests |
| Aggregation grain / joins | `analytics.py`, `mongo.rating_pipeline` | exact count/average assertions |
| View / outer join / NULL | `database_lab.VIEW_SQL` | live menu summary rows |
| Cross-engine references | `community.py`, `database_lab.integrity_audit` | deliberately injected orphan is detected |
| Preserved migration | `community_migration.py` | IDs/history preserved, conflicts rejected |
| Salt, pepper and upgrades | `passwords.py`, login route | different salts, wrong pepper, successful legacy upgrade |
| Authentication / CSRF | `app.py`, `services.authenticated` | guest, ordinary user, administrator and CSRF tests |

## Questions to prepare

- Which rules belong to the SQL engine, Mongo validators/indexes, or Python only?
- Why can MongoDB not enforce a foreign key into SQL? How do soft deletion and reconciliation help? Concurrent state changes still occur across engines.
- Why embed bounded feedback but reference independently growing replies/votes?
- If SQL commits and Mongo fails during seeding, why can the run resume? Explain stable keys/receipts, without claiming distributed ACID.
- Why might an optimizer choose a scan? What hardware, equivalent workloads, indexes and repeated trials would a fair benchmark need?
- Does repeated name/address prove duplication? No; flag candidates instead of deleting possible branches/source representations.
- Do zero observed violations prove all functional dependencies? No; dependencies also follow semantic business rules.

The original four report pages and their comments remain intact. A revised two-page body and separate references are appended below them. Its claims and figures must match the implementation and evidence.

## Week 1–5 follow-up demonstration

Open Database evidence → **06 · Weeks 1–5**. Use the [coverage guide](course_alignment.md) to locate the relevant lecture and implementation.

1. Change the closure selector from place_id to area_id. Explain why only the first is a key of the joined Venue projection, then justify BCNF decomposition, lossless join and dependency preservation separately.
2. Expand Bag versus set, NULL, and Joins. Predict each result before revealing it; explain why an unmatched venue produces COUNT(*)=1 but COUNT(dish_id)=0.
3. Expand a query rewrite. Compare full result counts and actual execution plans, including a venue without dishes. Explain why an INNER JOIN would be an incorrect replacement for the correlated count.
4. Export JSON to retain the executed SQL, current engine/version, example results and plans. These are demonstrations, not a controlled benchmark or MariaDB evidence when the badge says SQLite.
