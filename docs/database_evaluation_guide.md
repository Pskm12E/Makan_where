# Database evaluation aligned with the lecturer's feedback

Added 16 October 2026. The earlier design and verification write-ups are retained. The priorities are correctness and evidence for the implemented database design. The separate normalised-menu prototype is a proposal and is not presented as the deployed schema.

## What to demonstrate

| Priority | Design decision and expected invariant | Code / reproducible evidence |
| --- | --- | --- |
| Complete MongoDB operations | Community content belongs to MongoDB. Invalid multi-field updates change nothing; ownership and soft removal agree with public visibility; derived ratings reflect active, non-example reviews. | `backend/community.py`, `backend/mongo.py`; lifecycle/atomicity experiment and API regression tests |
| Cross-database behaviour | SQL owns account/venue/dish identities. Mongo references are checked by application code and reconciled by an audit. An unavailable SQL reference lookup prevents a Mongo insert. | `integrity_audit()` and six injected invalid-reference cases; archive and SQL-failure experiments |
| Concurrent writes | A unique user/venue key plus native upsert retains one favourite. A Mongo unique user/content pair retains one vote. Atomic counters allocate distinct IDs. A conditional open-status update permits one moderation winner. | Six-worker experiments with independent sessions and 24-request workloads; exact status/count assertions |
| Recovery | Population uses stable seed keys and SQL receipts. A retry fills missing Mongo documents after a partial commit while preserving edits and avoiding duplicate SQL events. | Faults before insert and after insert/before acknowledgement; rerun and further no-op rerun; real SQL disconnect rollback |
| Controlled performance | Compare the same query/result on the same dataset with index/scan access paths. Keep result equality independent of timing. | Deterministic ~30,000-row/document workloads; 3 warm-ups, 20 measured pairs in alternating order; full samples, median/p95 and plans |

The database experiment implementations are in [`tests/test_database_evaluation.py`](../tests/test_database_evaluation.py), with expected invariants stored beside observations. The runner in [`scripts/run_database_evaluation.py`](../scripts/run_database_evaluation.py) rejects missing-engine skips as a successful evaluation. It records the code fingerprint, package/engine versions, SQL isolation and Mongo topology/write concern.

## Explain the design, then show its enforcement

**Relational integrity.** Favourites and cuisine membership are relationships with composite keys. SQL foreign keys and CHECK constraints reject illegal states even if a browser misses a check. Application validation provides a readable error, while the engine supplies the final uniqueness/domain guarantee. A SELECT-then-INSERT is not enough under concurrency; the favourite operation uses a native upsert.

**Document aggregate boundary.** A community post and its bounded dish feedback are one Mongo document, enabling an atomic validated update. Replies, votes and reports can grow independently and are separate documents. A disjoint, covering `kind` schema distinguishes review/thread/comment shapes. The unique vote index, rather than an earlier existence check, is the concurrency guarantee.

**Cross-engine consistency.** There is no SQL foreign key into MongoDB and no distributed transaction. Parent validation prevents normal invalid writes; soft deletion retains identities; public reads recheck visibility; reconciliation detects out-of-band invalid references. These are explicit application rules with tests, not a claim of global serializability.

**Recovery contract.** Idempotent population phases can resume after partial success. This does not imply that every API POST is idempotent: the existing experiment shows an HTTP 503 after a committed post can leave one stored document. Re-reading establishes what happened; blindly retrying may duplicate it. Ordinary concurrent edits remain last-write-wins. Do not describe those limitations as solved.

**Normalisation scope.** The appended [relational redesign](relational_design.md#revised-design-using-the-week-1-to-5-concepts) contains actual FDs, candidate keys, weak-entity identity and separate lossless/dependency-preservation reasoning for the proposed menu decomposition. Its 19 isolated checks establish the proposal's stated properties. Current application evidence must continue to describe `Dish` and the implemented schema until a migration is completed.

## Repeat the measurements on the target engines

Follow the [Docker laptop guide](docker_laptop_guide.md), then run:

```text
docker compose --env-file .env.laptop -f compose.laptop.yaml --profile evaluation run --build --rm evaluate
```

This creates separate evaluation engine containers and disposable test databases. It does not run load or injected faults on the website catalogue. The web container reads the resulting artifact from a read-only evidence volume; Database evidence exposes it only to administrators and labels a changed source fingerprint as stale. A new laptop has no embedded successful artifact from another machine.

For a preconfigured host instead of Docker:

```text
python scripts/run_database_evaluation.py --full-suite --output docs/evidence/database-evaluation.json
```

Set `MARIADB_TEST_ADMIN_URL` and `MONGODB_TEST_URI` to dedicated test engines. Omitting the SQL test URL uses SQLite and must be reported as such. Host setup needs the application requirements and pytest; Docker supplies them automatically. Neither flow requires a database GUI.

## Interpret benchmark output correctly

- Compare equal ordered result sets and checksums before comparing latency.
- Present every measured sample and median/p95, rather than a single best run. Indexed access is not asserted to be faster on every laptop.
- Report the dataset size, selected predicate, projection, order, limit, warm-up count, repetition count and cache conditions.
- SQL EXPLAIN reports estimates. The MariaDB variant also retains executed `ANALYZE FORMAT=JSON` output, including observed row/loop fields. Mongo executionStats records keys/documents examined.
- State that the tests use independent Flask clients and real database drivers. They are not an HTTP throughput benchmark, production capacity estimate, power-loss test, replica-failover test or backup-restore test.

## Suggested evaluation sequence

1. Show the SQL/Mongo ownership diagram, keys, validators and relationship assumptions.
2. Perform a normal-user create/edit/remove flow and show the persisted document and derived result through the application evidence tools.
3. Show a rejected invalid write and the unchanged prior state.
4. Show the cross-database audit and one controlled unavailable-reference case.
5. Show the concurrency and resumable-population results with their exact invariants.
6. Show paired benchmark results and actual execution information with the workload conditions.
7. Close with the remaining limitations and the distinction between implemented design and the proposed menu refinement.

The [verification record](verification_record.md) contains dated observed results. Earlier passing results belong to their recorded revisions and must not be substituted for a fresh target-engine run.
