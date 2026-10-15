/* Explanations are tied to the current course PDFs and fixed backend evidence. */
function renderCourseEvidence(course) {
  const weeks = [
    ['01', 'Relational foundations', 'Schemas, domains and keys; abstraction and independence; DBMS advantages and ACID. Lab 1 uses Python + SQLAlchemy.', 'Inspect the live schema in Keys & integrity. Users, venue catalogue and menu data live in SQL; community data lives in MongoDB. An SQL rollback is atomic within SQL; the combined import is resumable across engines.', '985049'],
    ['02', 'ER modelling and integrity', 'Entities, attributes, participation/cardinality, weak entities, subtypes, DDL, domain/key/referential constraints and basic predicates.', 'food_place → area is many-to-one and mandatory; venues may have zero dishes. favourite and place_cuisine resolve many-to-many relationships. Mongo kind distinguishes review/thread/comment. Run the constraint probes.', '987818'],
    ['03', 'SQL semantics', 'CRUD, bags/sets, joins, aggregates, GROUP BY/HAVING, nested queries, NULL, ANY/ALL, UNIQUE, views and SQL functions. Lab 3 combines queries.', 'Expand the reproducible SQL examples below. Queries & plans also shows application queries and catalogue_menu_summary. The view is virtual, not a materialized cache.', '989704'],
    ['04', 'Database refinement', 'Anomalies, functional dependencies, Armstrong’s axioms, closure, candidate keys, BCNF, lossless decomposition and dependency preservation. Lab 4 runs SQL in Python.', 'Follow the closure trace and BCNF decomposition below. Area names are stored once. Do not infer a semantic FD just because the current sample has no duplicates.', '993268'],
    ['05', 'Algebra and optimization', 'Selection, projection, rename, union, difference, product, joins and assignment; equivalent rewrites, indexes and execution plans.', 'Compare both SQL forms against all result rows. Inspect real plans and explain why filtering earlier may help. A plan or equal results is not a timing benchmark.', '994895'],
  ];
  const n = course.dependencies;
  document.getElementById('panel-course').innerHTML = `
    <div class="card accent"><p class="eyebrow">Course concepts → implementation evidence</p><h2>Explain the design. Show the result.</h2>
      <p>These examples follow the Week 1–5 lectures, including the revised Week 4 slides. Every SQL result below is executed by <strong>${esc(course.engine)} ${esc(course.version)}</strong> when evidence is refreshed.</p>
      <p class="caption">Small CTE fixtures deliberately expose duplicate, NULL and empty-set cases without changing application data. Query comparisons use the current venue and dish tables. Export JSON saves the SQL, results, plans and closure traces.</p></div>
    <div class="course-week-grid">${weeks.map(([number,title,topics,application,id]) => `<article class="card course-week"><p class="eyebrow">Week ${number}</p><h2>${title}</h2><p>${topics}</p><p class="caption">${application}</p><a href="https://xsite.singaporetech.edu.sg/d2l/le/content/213446/viewContent/${id}/View" target="_blank" rel="noopener noreferrer">Lecture source ↗</a></article>`).join('')}</div>
    <div class="card"><p class="eyebrow">Week 4 · a worked derivation</p><h2>From functional dependencies to BCNF</h2><p>${esc(n.assumptions)}</p>
      <p><code>Venue(${esc(n.relation.join(', '))})</code></p>
      ${table(['Determinant X','Determined attributes Y'], n.fds.map(fd => [fd.left.join(', '),fd.right.join(', ')]))}
      <p><strong>Candidate key:</strong> ${esc(n.candidateKeys.map(k=>k.join(' + ')).join('; '))}. A candidate key is a minimal superkey.</p>
      <label for="closureChoice"><strong>Choose the starting attributes X</strong></label>
      <select id="closureChoice">${n.closures.map((c,i)=>`<option value="${i}">${esc(c.start.join(' + '))}</option>`).join('')}</select>
      <div id="closureTrace" aria-live="polite"></div>
      <h3>Find a violating dependency</h3><p><code>area_id → area_name</code> is nontrivial, but area_id does not determine place_id or place_name. Its determinant is not a superkey of Venue, so Venue fails BCNF.</p>
      <div class="relationship"><div class="entity"><strong>food_place projection</strong><code>place_id PK<br>place_name<br>area_id FK</code></div><span aria-label="references">→</span><div class="entity"><strong>area</strong><code>area_id PK<br>area_name UNIQUE NOT NULL</code></div></div>
      ${table(['Decomposed relation','Candidate keys','BCNF violations under F+'], n.parts.map(p=>[p.attributes.join(', '),p.candidateKeys.map(k=>k.join(' + ')).join('; '),p.violations.length]))}
      <h3>Prove the decomposition properties separately</h3><p>${esc(n.lossless)}</p><p>${esc(n.preservation)}</p>
      <details><summary>Why lossless does not imply dependency-preserving</summary><div class="detail-body"><p>${esc(n.counterexample)}</p></div></details>
      <h3>A composite key is different</h3><p><code>favourite(${esc(n.composite.relation.join(', '))})</code></p><p>${esc(n.composite.explanation)}</p>
      <p class="caption">${esc(n.caveat)}</p>
    </div>
    <div class="card"><p class="eyebrow">Weeks 1–3 & 5 · executed SQL</p><h2>Small examples make edge cases visible.</h2><p>The same fixtures are prefixed to each query. These are teaching relations, not extra stored tables.</p><details><summary>Inspect the common WITH fixtures</summary><div class="detail-body"><pre>${esc(course.fixture)}</pre></div></details>
      ${course.semantics.map(s=>`<details><summary>${esc(s.title)} <small>${esc(s.source)}</small></summary><div class="detail-body"><p>${esc(s.explanation)}</p>${s.variants.map(v=>`<h3>${esc(v.title)}</h3><pre>${esc(v.sql)}</pre>${objectTable(v.result)}`).join('')}</div></details>`).join('')}
    </div>
    <div class="card"><p class="eyebrow">Week 5 · current catalogue data</p><h2>Same answer, different query expression.</h2>
      <p>Equality below compares complete result multisets, including duplicate counts and NULL values. Only the first ten rows are displayed. A concurrent data change may cause a comparison to differ; refresh during a quiet demonstration.</p>
      ${course.rewrites.map(q=>`<details><summary>${esc(q.title)} <small>${q.equivalentOnSnapshot ? 'Equal result multisets' : 'Results differ — investigate'}</small></summary><div class="detail-body"><p><code>${esc(q.algebra)}</code></p><p>${esc(q.explanation)}</p><div class="two-cols">${q.variants.map((v,i)=>`<div><h3>Form ${i+1} · ${esc(v.rowCount)} rows</h3><pre>${esc(v.sql)}</pre>${objectTable(v.preview)}<h3>Actual execution plan</h3>${objectTable(v.plan)}</div>`).join('')}</div></div></details>`).join('')}
      <p class="caption">EXPLAIN describes optimizer choices. SQLite uses EXPLAIN QUERY PLAN; MariaDB uses EXPLAIN. Estimated rows are not measured latency. MariaDB verification and controlled performance benchmarks remain separate work.</p>
    </div>
    <div class="card"><h2>Design decisions you should be able to defend</h2>${table(['Lecture topic','Application decision / limit'],[
      ['Abstraction & independence','External: browser/API and menu view. Logical: SQL/Mongo models. Physical: storage and indexes. Adding an index can preserve the API; changing schema may require migration.'],
      ['Six design stages','Diner/admin requirements → conceptual relationships → tables/documents → FD decomposition → indexes/plans → access control.'],
      ['Weak entities and subtypes','dish has its own surrogate key; needing a venue FK alone does not make it weak by identification. Mongo kind is a disjoint, covering discriminator for review/thread/comment. Legacy SQL subtypes are migration-only.'],
      ['Attribute types','Cuisine membership is multivalued conceptually, implemented by a junction table. Starting price and review rating are derived, not duplicated authoritative fields.'],
      ['ACID and access control','SQL commits/rollbacks and Mongo single-document updates have local guarantees. No distributed transaction or tested crash-recovery guarantee is claimed. App roles are distinct from database GRANT privileges.'],
      ['Views, materialized views, UDFs','catalogue_menu_summary is a read-only aggregate view. No materialized-view refresh, updatable WITH CHECK OPTION view or database UDF is implemented. These are considered alternatives, not invented deliverables.'],
      ['Index trade-offs','dish.place_id supports joins/existence checks. Indexes cost writes/storage. Prefix LIKE and substring LIKE answer different questions; never change search semantics just to claim an index speedup.'],
      ['Python database access','SQLAlchemy models/queries support the application; SQLAlchemy text executes these fixed SQL examples. Bound parameters are required for variable user values.'],
    ])}</div>`;
  const select = document.getElementById('closureChoice');
  const displayClosure = () => {
    const c = n.closures[Number(select.value)];
    document.getElementById('closureTrace').innerHTML = `<p>Start with <code>{${esc(c.start.join(', '))}}</code>.</p>${table(['Apply FD','New attributes','Closure so far'],c.steps.map(s=>[s.using,s.added.join(', '),s.closure.join(', ')]))}<p><strong>X⁺ = {${esc(c.result.join(', '))}}</strong>. ${c.result.length===n.relation.length ? 'All attributes are reached: X is a superkey.' : 'Some attributes cannot be reached: X is not a superkey.'}</p>`;
  };
  select.addEventListener('change', displayClosure);
  displayClosure();
}
