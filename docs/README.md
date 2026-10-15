# Makan Where documentation

Start with the [project README](../README.md) for progress-report answers, local MariaDB setup, data loading, admin setup, query inspection, troubleshooting and submission requirements. It is the main setup and coursework guide.

The current application uses SQL and MongoDB together. MongoDB now implements community CRUD, rating aggregation, voting and moderation. The current local preview and tests use SQLite + real MongoDB; MariaDB verification for this revision remains pending. The README, current architecture and lecturer walkthrough describe the new implementation. The original SQL dictionary/diagrams remain historical migration references.

| Document | Purpose |
| --- | --- |
| [System architecture](system_architecture.md) | Current component diagram, proposed SQL/MongoDB architecture, request sequence and planned document model/query comparison |
| [Relational design](relational_design.md) | Code-derived ERD and dictionary: 17 tables, 93 columns; ten active and seven legacy tables |
| [API reference](API_design.md) | Implemented routes, request fields, sessions, CSRF and access rules |
| [Roles and permissions](roles_and_permissions.md) | User/admin responsibilities, catalogue population, moderation and permission checks |
| [User manual](user_manual.md) | How to use the running application as a guest, registered user or administrator |
| [Verification record](verification_record.md) | Observed MariaDB and SQLite test results, startup/import checks and evidence limits |
| [Lecturer walkthrough](lecturer_walkthrough.md) | Trace visible features to SQL, constraints, test evidence and remaining assessment gaps |
| [Data provenance](../data/README.md) | Dataset source, attribution, quality limits and import/rebuild details |

The old [architecture SVG](assets/system_architecture.svg) predates the new MongoDB implementation. Use the current architecture document and Database evidence for current diagrams/metadata. The README records remaining verification and submission work.


## Database-focused additions — 6 October 2026

The original documentation above is retained. Read the appended [database design and evaluation addendum](system_architecture.md#database-design-and-evaluation-addendum--6-october-2026) for ownership decisions, normalization reasoning, transaction contracts, recovery boundaries and controlled measurement. The appended [verification entry](verification_record.md#database-correctness-and-evaluation--6-october-2026) records the 80-test local run and its MariaDB/deployment limits.


## Revised logical design using the class concepts - 6 October 2026

The [new design is appended below the original relational reference](relational_design.md#revised-design-using-the-week-1-to-5-concepts). It separates menu publications, entries and outlet offerings; models tags with a junction; derives candidate keys and BCNF from stated FDs; and proves losslessness and dependency preservation. [Executable model](../database/design_v2.py), [proposed MariaDB DDL](../database/design_v2_mariadb.sql), and [19 isolated design checks](evidence/design-v2-validation.json) accompany the explanation. This is a validated proposal, not the current deployed schema or an implemented live migration.

## Lecturer feedback and laptop reproducibility - 16 October 2026

- [Database evaluation guide](database_evaluation_guide.md): each feedback item mapped to implemented design decisions, invariants, tests, measurements and limitations.
- [Docker laptop guide](docker_laptop_guide.md): complete app/MariaDB/MongoDB startup, private generated accounts, persistent volumes, isolated evaluation, export, shutdown and troubleshooting.

The earlier write-ups remain above. The proposed menu decomposition remains a proposal; these instructions run and evaluate the implemented application schema.
