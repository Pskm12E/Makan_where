# INF2003 Week 1–5 coverage and demonstration guide

Reviewed 30 September 2026 against Tong Rong's AY2026/27 T1 lectures 1–5,
including the revised Lecture 4 linked in the 22 September announcement,
and the supplied Lab 1–4 materials. Lecture PDFs are course material and are
not republished in this repository. This is a project-specific evidence map,
not a claim that every lecture feature is implemented or a guarantee of marks.

Open **Database evidence → 06 · Weeks 1–5** as an administrator. Refresh executes
24 small SQL examples and three pairs of catalogue queries. Export JSON keeps
their SQL, actual results, execution plans and FD derivations. The engine badge
identifies SQLite versus MariaDB; do not present SQLite evidence as MariaDB.

## Coverage by week

| Teaching material | Where the build demonstrates it | Scope / explanation to give |
| --- | --- | --- |
| W1: DBMS versus flat files, CRUD | Flask services, SQL constraints, Mongo validators; Population and Keys & integrity tabs | Central constraints reject invalid writes, unlike CSV alone. CSV remains an input, not the authoritative application database. |
| W1: three abstraction levels; logical/physical independence; tiers | Browser/API → models and menu view → engine indexes/storage; architecture figure | An index can change without changing API fields. Schema changes may require migrations; logical independence is not automatic. |
| W1: six design stages | Requirements → ER relationships → relations/documents → FD refinement → indexes/plans → authorization | Trace one requirement: a user can save many venues once each → favourite relationship → composite PK. |
| W1: relations, schema, domains, NULL | `models.py`, live schema inspector, SQL examples | Rows are unordered without ORDER BY. DECIMAL prices, mandatory references, optional source fields, and missing-menu NULLs have different meanings. |
| W1: super/candidate/primary/foreign keys | Live inspector and closure demonstration | `user_id`, username and email identify users; the latter two are UNIQUE NOT NULL. A superkey may have redundant attributes. Nullable unique source IDs are not global candidate keys. |
| W1: ACID | SQL transactions and rollback probes, Mongo bounded document updates | SQL and Mongo have separate transactional boundaries. Seeding is resumable using receipts/IDs, not a distributed ACID transaction. Crash recovery and concurrent workloads have not been experimentally established. |
| Lab 1: Python SQLAlchemy CRUD | SQLAlchemy models and catalogue/favourite/admin services | Explain the Python call, generated SQL, database constraint and persisted result. ORM use does not remove the need to understand SQL. |
| W2: entities, attributes, relationships, participation/cardinality | [complete model](relational_design.md), [full diagrams](assets/database-model-full.pdf) | A venue has exactly one area; an area can have zero venues. A dish has one venue; a venue can have zero dishes. Favourite.saved_at is a relationship attribute. |
| W2: multivalued/composite/derived attributes | Cuisine junction; stored address; derived SQL menu prices and Mongo rating aggregate | Cuisine membership is represented by one junction tuple per pair. Address is stored as a source string, not falsely shown as split street/unit/postcode attributes. Ratings and minimum prices are computed. |
| W2: weak entities, unary/binary/ternary relationships, ISA constraints | `kind` validator for review/thread/comment; comment→thread reference; legacy subtype tables | Dish has its own surrogate ID: a mandatory FK alone does not make it identification-dependent. Mongo content uses disjoint covering kinds. No ternary relationship is needed by current requirements. Legacy SQL community tables are not live storage. |
| W2: domain/key/referential integrity; DDL, defaults, constraints | `models.py`, schema exports, Mongo validators and nine negative probes | PK/UNIQUE/FK/CHECK/NOT NULL are separate rules. Mongo cannot enforce SQL FKs. Client validation is not a substitute for engine enforcement. |
| W2: SQL types, arithmetic/Boolean/string predicates, BETWEEN/IN/LIMIT/LIKE | Catalogue query builder and queries tab; decimal dish price | Bind input values; stable ORDER BY plus LIMIT makes pagination meaningful. Substring and prefix search differ semantically. |
| Lab 2: MariaDB installation, privileges, DDL and CRUD | Deployment configuration, migration commands, admin operations | Current-revision MariaDB rerun remains pending. Application roles do not equal MariaDB GRANT privileges. Do not expose an arbitrary DDL console to demonstrate the lab. |
| W3: INSERT/UPDATE/DELETE/SELECT; bag versus set, sorting | Existing admin/community CRUD; executable SELECT/DISTINCT and UNION/UNION ALL examples | DISTINCT changes result multiplicity. Removing it is only correct if duplicates are permitted or impossible by keys. |
| W3: UNION/INTERSECT/EXCEPT; joins and aliases | CTE set examples; intersection/difference expressed using EXISTS/NOT EXISTS; inner/left join examples | Set operands need compatible schemas. Natural join is avoided in application SQL because unrelated columns such as description share names. RIGHT JOIN can be written by swapping a LEFT JOIN; no FULL OUTER JOIN requirement in this catalogue. |
| W3: SUM/COUNT/AVG/MIN/MAX; GROUP BY/HAVING | All five aggregates on the fixture, affordable menu groups; production analytics | WHERE filters tuples before aggregation, HAVING filters groups. Aggregating review×dish×save joins together would multiply counts, so engines/aggregates are combined at venue grain. |
| W3: NULL, UNIQUE and empty aggregates | Executed NULL/=NULL/IS NULL, COUNT(*) versus COUNT(column), empty SUM/AVG, NOT IN trap | UNIQUE nullable columns can have NULLs; pair UNIQUE does not force NOT NULL. A missing menu is not price zero. |
| W3: nested/correlated queries, EXISTS/NOT EXISTS, ANY/ALL | Missing-menu query, existence rewrite, non-null ANY/ALL equivalent examples | `= ANY` corresponds to IN; general `> ANY` does not. ALL(empty) is true, but `> MAX(empty)` is UNKNOWN. The shown EXISTS rewrites assume non-null operands. |
| W3: regular/updatable/materialized views and UDFs | Implemented `catalogue_menu_summary` regular aggregate view; built-in SQL functions | No updatable CHECK OPTION view, materialized-view refresh or stored UDF is claimed. The aggregate view is read-only. Caching would require a freshness/refresh policy and evidence of benefit. |
| Lab 3: complex SQL and empty-table reasoning | Executed bag/set, joins, aggregation, subquery and empty-set counterexamples | Avoid cross-joining an unrelated empty relation in an OR query: it can remove every row before WHERE is evaluated. |
| W4: insertion/update/deletion anomalies, FDs, axioms, closure | Worked area decomposition and selectable closure trace | State semantic assumptions first. An area rename should update one area row. A data snapshot can refute an FD, but cannot prove it for all legal future states. |
| W4: 1NF/2NF/3NF/BCNF; lossless join and preservation | Dependencies tab plus formal Week 4 example | BCNF is checked against projected F+, including implied dependencies. Prove losslessness and dependency preservation separately. JSON presentation/receipt columns are exceptions to strict flat-relational 1NF claims. |
| Lab 4: SQL in Python, connections/cursors, joins | `course_evidence.py` executes fixed SQL through SQLAlchemy connections and consumes mappings | The lab's sqlite3 API differs, but the connection → execute → consume result → close pattern is the same. User values in actual application queries are parameterized. |
| W5: σ, π, ρ, ∪, −, ×, joins, assignment | CTE product/selection/join equivalence; aliases and WITH; bag/set examples | Product yields 3×3=9 rows in the fixture. Selection on the join key reduces to three. Relational projection is a set operation; plain SQL projection is usually a bag. |
| W5: selection/projection pushdown, join order, WHERE/HAVING, EXISTS/count, correlated rewrites | Three pairs of live SQL queries with complete multiset comparisons and actual EXPLAIN | Retain join keys during projection pushdown. Predicates cannot be moved across outer joins indiscriminately. LEFT JOIN + COALESCE preserves zero-menu venues. Join order is selected by the optimizer and statistics. |
| W5: index trade-offs, sargability, EXPLAIN/ANALYZE | Live indexed schema, SQL plans, Mongo feed execution statistics | Indexes cost storage/writes and may be ignored on small tables. A function/leading wildcard can obstruct an index access path. EXPLAIN is not elapsed-time evidence; MariaDB ANALYZE runs the query and measures execution statistics. |

## Explain the Week 4 derivation

Use the **teaching projection**, not an invented physical table:

`Venue(place_id, place_name, area_id, area_name)`

Assume `place_id → place_name, area_id`, `area_id → area_name`, and
`area_name → area_id` (the last follows the actual UNIQUE NOT NULL rule).
By transitivity, `place_id → area_name`. Closure of place_id reaches all four
attributes; removing place_id leaves the empty set, so place_id is a candidate
key. Closure of area_id reaches only area_id and area_name: its nontrivial FD
violates BCNF in the joined projection.

Decompose into `P(place_id, place_name, area_id)` and
`A(area_id, area_name)`. Their intersection `{area_id}` determines A, proving
lossless binary decomposition for legal instances. Each given FD is enforceable
within P or A, proving dependency preservation in this case. Both projected
relations satisfy BCNF under those FDs. This is **not** a BCNF proof of the
entire application.

The closure trace applies Armstrong reasoning: reflexivity starts with X,
decomposition lets us treat a multi-attribute RHS separately, and repeated
transitivity derives new attributes. Augmentation preserves a dependency when
the same attributes are added to both sides. For favourite,
`(user_id, place_id) → saved_at`; neither component alone is enough. The extra
attribute in `(user_id, place_id, saved_at)` makes a superkey but not a minimal key.

Losslessness does not imply dependency preservation. The UI shows the
counterexample `R(A,B,C), F={A→B,B→C}` split as AB and AC: locally valid rows
can join to violate B→C. Splitting into AB and BC preserves both dependencies.

## What belongs in the two-page progress report

Keep the required application, architecture, data, implementation plan and
current-deliverables sections, with the real SQL/Mongo diagrams. Give one
concrete FD/decomposition argument and name the SQL/algebra demonstrations;
put detailed derivations and screenshots in this guide/Studio and final report.
The lecturer's 22 September announcement says a high-level progress plan is
sufficient. Original report pages/comments must stay intact; revised content
is appended below them. References are outside the two-page revised body.

Before final submission, supply actual team task allocation, current MariaDB
results, clean-machine instructions/verification, a repeatable backup/restore
test and a fair SQL/Mongo performance comparison. Do not label these complete
based only on course coverage. Team names are left for the group as requested.

## Sources checked

All lectures: Tong Rong, *INF2003 Database Systems*, AY2026/27 Trimester 1,
Singapore Institute of Technology, course-only xSITe materials, accessed
30 September 2026.

1. [Lecture 1 — DB and relational model](https://xsite.singaporetech.edu.sg/d2l/le/content/213446/viewContent/985049/View), 35 slides; especially pp. 3, 8–16, 18–31 and project/lab pp. 33–35.
2. [Lecture 2 — ER diagram and SQL part 1](https://xsite.singaporetech.edu.sg/d2l/le/content/213446/viewContent/987818/View), 46 slides; ER pp. 5–20, constraints pp. 22–26, SQL pp. 29–44. Read from the user's local lecture PDF.
3. [Lecture 3 — SQL part 2](https://xsite.singaporetech.edu.sg/d2l/le/content/213446/viewContent/989704/View), 43 slides; SQL pp. 2–34, views/functions pp. 36–42.
4. [Lecture 4 — Database refinement, revised](https://xsite.singaporetech.edu.sg/d2l/le/content/213446/viewContent/993268/View), 41 slides; anomalies pp. 4–8, FDs/closure pp. 9–20, BCNF/decomposition pp. 21–36.
5. [Lecture 5 — Relational algebra & query optimization](https://xsite.singaporetech.edu.sg/d2l/le/content/213446/viewContent/994895/View), 36 slides; operators pp. 8–21, optimization pp. 24–35.
6. Lab 1 student notebook (SQLAlchemy CRUD), Lab 2 PDF (MariaDB basics), Lab 3 template (complex queries), Lab 4 PDF (SQL in Python), from the user's local course folder. These were inspected for teaching scope; no lab submission was changed.

Implementation: [course evidence backend](../backend/course_evidence.py),
[UI](../js/course-evidence.js), [semantic tests](../tests/test_course_evidence.py),
[verification record](verification_record.md).


## Applied schema refinement - 6 October 2026

The [appended revised design](relational_design.md#revised-design-using-the-week-1-to-5-concepts) applies the actual Lecture 2 and Lecture 4 concepts to reference-menu redundancy. Follow requirements -> ER participation/weak identity -> composite keys and FDs -> closure -> BCNF decomposition -> separate lossless/preservation proofs -> DDL and negative constraint probes. The proposed tag junction makes that multivalued attribute relational. Joins, NULL-aware overrides, NOT EXISTS, zero-count outer joins and index trade-offs connect the model to Weeks 3 and 5.

The [19-check artifact](evidence/design-v2-validation.json) is an isolated executable proposal. It does not replace the descriptions of the currently deployed schema above. See the separate [6 October correctness evaluation](verification_record.md#database-correctness-and-evaluation--6-october-2026) for actual concurrency and recovery experiments and their limits.
