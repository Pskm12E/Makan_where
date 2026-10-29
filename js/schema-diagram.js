/* No external renderer: SQL nodes and edges come from /api/admin/schema.
 * Mongo links are explicitly an application-model reference map, not SQL FKs.
 */
(() => {
  'use strict';
  const legacy = new Set(['content', 'review', 'thread', 'comment', 'content_dish', 'upvote', 'report']);
  const layout = {
    area: [24, 40], category: [24, 280], cuisine: [24, 600],
    food_place: [344, 160], place_cuisine: [344, 600], dish: [664, 40],
    favourite: [664, 340], user: [984, 340], discovery_event: [664, 640], population_run: [984, 640]
  };
  const explanations = {
    area: 'Stores each area name once. Restaurants refer to this area using area_id.',
    category: 'Groups restaurants by establishment type. Each restaurant references one category.',
    cuisine: 'Stores cuisine names. A restaurant can have several cuisines through place_cuisine.',
    food_place: 'The restaurant identity. Its dishes, saved favourites and cuisine memberships refer to place_id.',
    dish: 'Each menu item belongs to a restaurant. The database rejects negative prices; unavailable dishes retain their identity.',
    place_cuisine: 'Resolves the many-to-many relationship between restaurants and cuisines. The pair of IDs is the primary key.',
    user: 'Account identities and roles. Usernames and email addresses are unique. Passwords are stored as hashes.',
    favourite: 'Connects a user to a saved restaurant. The pair of IDs prevents duplicate saves; saved_at records when it was saved.',
    discovery_event: 'Records searches and restaurant views. User references are optional; a place_view requires a restaurant reference.',
    population_run: 'Stores import receipts and restart markers. It has no foreign keys.'
  };
  const sqlPaths = {
    'food_place:area': [[344, 200], [292, 200], [292, 105], [240, 105]],
    'food_place:category': [[344, 275], [292, 275], [292, 345], [240, 345]],
    'dish:food_place': [[664, 110], [612, 110], [612, 210], [560, 210]],
    'place_cuisine:food_place': [[452, 600], [452, 330]],
    'place_cuisine:cuisine': [[344, 680], [240, 680]],
    'favourite:food_place': [[664, 400], [612, 400], [612, 280], [560, 280]],
    'favourite:user': [[880, 420], [984, 420]],
    'discovery_event:food_place': [[664, 690], [590, 690], [590, 310], [560, 310]],
    'discovery_event:user': [[880, 720], [936, 720], [936, 485], [984, 485]]
  };
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  let schema, mode = 'sql', selected = '', zoom = 1, nodes = [], edges = [], height = 840;
  const root = () => document.getElementById('schemaDiagram');

  function sqlModel() {
    const tables = schema.tables.filter(t => !legacy.has(t.name));
    let extra = 0;
    nodes = tables.map(t => {
      const position = layout[t.name] || [24 + (extra % 4) * 320, 880 + Math.floor(extra++ / 4) * 220];
      const keyColumns = t.columns.filter(c => c.primaryKey || t.foreignKeys.some(f => f.columns.includes(c.name)));
      const shown = [...keyColumns, ...t.columns.filter(c => !keyColumns.includes(c))].slice(0, 4);
      return {id: t.name, title: t.name, x: position[0], y: position[1], width: 216, height: 170, table: t,
        fields: shown.map(c => ({name: c.name, key: [c.primaryKey ? 'PK' : '', t.foreignKeys.some(f => f.columns.includes(c.name)) ? 'FK' : ''].filter(Boolean).join('/')})),
        note: `${t.columns.length} columns · select to inspect`, description: explanations[t.name] || 'Table reflected from the connected SQL database.'};
    });
    let route = 0;
    const bottom = Math.max(...nodes.map(n => n.y + n.height), 810);
    function referencePath(source, target) {
      const right = source.x + source.width;
      if (source.id === target.id) return [[right, source.y + 115], [right + 28, source.y + 115], [right + 28, source.y + 55], [right, source.y + 55]];
      const lane = bottom + 32 + route++ * 18, parentRight = target.x + target.width;
      return [[right, source.y + 95], [right + 16, source.y + 95], [right + 16, lane], [parentRight + 32, lane], [parentRight + 32, target.y + 65], [parentRight, target.y + 65]];
    }
    edges = tables.flatMap(t => t.foreignKeys.filter(f => nodes.some(n => n.id === f.table)).map(f => {
      const target = nodes.find(n => n.id === f.table);
      const source = nodes.find(n => n.id === t.name);
      const optional = f.columns.some(name => t.columns.find(c => c.name === name)?.nullable);
      const uniqueKeys = [t.primaryKey, ...t.uniqueConstraints.map(u => u.columns), ...t.indexes.filter(i => i.unique).map(i => i.columns)];
      const unique = uniqueKeys.some(key => key.length && key.every(name => f.columns.includes(name)));
      return {from: t.name, to: f.table, label: `${t.name}.${f.columns.join(' + ')} → ${f.table}.${f.targetColumns.join(' + ')}`,
        points: sqlPaths[`${t.name}:${f.table}`] || referencePath(source, target),
        start: unique ? '0..1' : '0..*', end: optional ? '0..1' : '1'};
    }));
    height = Math.max(840, ...nodes.map(n => n.y + n.height + 30), ...edges.flatMap(e => e.points.map(p => p[1] + 30)));
  }

  function mongoModel() {
    const node = (id, title, x, y, fields, description, type = 'mongo') => ({id, title, x, y, width: 246, height: 190,
      fields: fields.map(name => ({name, key: name === '_id' ? 'ID' : ''})), description, type,
      note: type === 'external' ? 'SQL identity · application reference' : 'MongoDB · application model'});
    nodes = [
      node('mongo:content', 'content', 454, 300, ['_id', 'kind', 'author_id · place_id', 'dishes[]'], 'One collection contains reviews, threads and comments. The kind validator determines required fields: reviews have ratings (1–5), threads have titles, and comments reference a thread. Up to 20 dish-feedback entries are embedded for atomic document updates.'),
      node('mongo:upvotes', 'upvotes', 24, 80, ['_id', 'user_id', 'content_id', 'voted_at'], 'A compound unique index on (user_id, content_id) permits only one vote by a user on a post.'),
      node('mongo:reports', 'reports', 24, 540, ['_id', 'reporter_id', 'content_id', 'status'], 'Moderation reports reference a post and the reporting user. Resolution records the administrator and decision.'),
      node('mongo:counters', 'counters', 454, 640, ['_id', 'value'], 'An atomic increment allocates IDs for new content and reports. This collection is an ID allocator, not a foreign-key relationship.'),
      node('sql:user', 'user', 954, 80, ['user_id'], 'author_id, user_id, reporter_id and moderation-user references are checked against SQL accounts by the application.', 'external'),
      node('sql:food_place', 'food_place', 954, 340, ['place_id'], 'A post references an existing restaurant. Public reads check that the restaurant remains active.', 'external'),
      node('sql:dish', 'dish', 954, 600, ['dish_id'], 'Embedded dish feedback references a SQL dish at the same restaurant.', 'external')
    ];
    const edge = (from, to, label, points) => ({from, to, label, points, reference: true});
    edges = [
      edge('mongo:upvotes', 'mongo:content', 'upvotes.content_id → content._id', [[270, 185], [356, 185], [356, 355], [454, 355]]),
      edge('mongo:reports', 'mongo:content', 'reports.content_id → content._id', [[270, 610], [356, 610], [356, 445], [454, 445]]),
      edge('mongo:content', 'sql:user', 'content.author_id → user.user_id', [[700, 350], [814, 350], [814, 220], [954, 220]]),
      edge('mongo:content', 'sql:food_place', 'content.place_id → food_place.place_id', [[700, 405], [954, 405]]),
      edge('mongo:content', 'sql:dish', 'content.dishes[].dish_id → dish.dish_id', [[700, 460], [814, 460], [814, 670], [954, 670]]),
      edge('mongo:upvotes', 'sql:user', 'upvotes.user_id → user.user_id', [[147, 80], [147, 32], [1077, 32], [1077, 80]]),
      edge('mongo:reports', 'sql:user', 'reports.reporter_id → user.user_id', [[147, 540], [147, 298], [900, 298], [900, 140], [954, 140]]),
      edge('mongo:content', 'mongo:content', 'comments: content.thread_id → content._id (kind = thread)', [[530, 490], [530, 558], [630, 558], [630, 490]])
    ];
    height = 860;
  }

  function drawNode(n) {
    return `<g class="schema-node ${n.type || 'sql'}" data-node="${escape(n.id)}" role="button" tabindex="0" aria-label="Inspect ${escape(n.title)}${n.type === 'external' ? ' in SQL' : ''}" aria-pressed="false" transform="translate(${n.x} ${n.y})">
      <title>${escape(n.description)}</title><rect class="node-body" width="${n.width}" height="${n.height}" rx="10"/>
      <path class="node-head" d="M10 1H${n.width - 10}Q${n.width - 1} 1 ${n.width - 1} 10V44H1V10Q1 1 10 1Z"/>
      <text class="node-title" x="16" y="29">${escape(n.title.length > 21 ? n.title.slice(0, 19) + '…' : n.title)}</text>
      ${n.fields.map((f, i) => `<text class="node-field" x="16" y="${68 + i * 23}">${escape(f.name)}</text>${f.key ? `<text class="node-key" x="${n.width - 12}" y="${68 + i * 23}" text-anchor="end">${escape(f.key)}</text>` : ''}`).join('')}
      <text class="node-note" x="16" y="${n.height - 12}">${escape(n.note)}</text></g>`;
  }

  function endLabel(points, atStart, label) {
    if (!label) return '';
    const end = points[atStart ? 0 : points.length - 1], next = points[atStart ? 1 : points.length - 2];
    const horizontal = end[1] === next[1];
    const x = horizontal ? end[0] + Math.sign(next[0] - end[0]) * 23 : end[0] + 10;
    const y = horizontal ? end[1] - 8 : end[1] + Math.sign(next[1] - end[1]) * 20;
    return `<text x="${x}" y="${y}" text-anchor="${horizontal ? 'middle' : 'start'}">${label}</text>`;
  }

  function drawEdge(e, i) {
    const d = e.points.map((p, index) => `${index ? 'L' : 'M'}${p[0]} ${p[1]}`).join(' ');
    return `<g class="schema-edge ${e.reference ? 'reference' : ''}" data-edge="${i}"><title>${escape(e.label)}</title><path d="${d}" marker-end="url(#schemaArrow${e.reference ? 'Reference' : ''})"/>${endLabel(e.points, true, e.start)}${endLabel(e.points, false, e.end)}</g>`;
  }

  function build() {
    if (!schema || !root()) return;
    mode === 'sql' ? sqlModel() : mongoModel();
    if (!nodes.some(n => n.id === selected)) selected = '';
    const oldCount = schema.tables.filter(t => legacy.has(t.name)).length;
    root().innerHTML = `<div class="schema-diagram-header"><div><h3>Relationships at a glance</h3><p id="schemaDiagramSource">${mode === 'sql' ? `${nodes.length} active tables · foreign keys read from the connected ${escape(schema.engine)} database.` : `Application reference map · MongoDB ${schema.mongoDB?.connected ? 'connected' : 'connection not confirmed'}. Dashed links are checked by Python.`}</p></div></div>
      <div class="schema-diagram-modes" role="group" aria-label="Diagram view"><button type="button" data-mode="sql" aria-pressed="${mode === 'sql'}">SQL relationships</button><button type="button" data-mode="mongo" aria-pressed="${mode === 'mongo'}">MongoDB references</button></div>
      <div class="schema-diagram-toolbar"><label class="schema-diagram-picker">Inspect <select id="schemaNodePicker"><option value="">Choose a table or collection</option>${nodes.map(n => `<option value="${escape(n.id)}">${escape(n.title)}${n.type === 'external' ? ' (SQL)' : ''}</option>`).join('')}</select></label><div class="schema-diagram-zoom" role="group" aria-label="Diagram zoom"><button type="button" data-zoom="out" aria-label="Zoom out">−</button><output id="schemaZoomValue" aria-label="Zoom level">100%</output><button type="button" data-zoom="in" aria-label="Zoom in">+</button><button type="button" data-zoom="fit">Reset view</button><button type="button" data-action="clear">Clear selection</button></div></div>
      <div class="schema-diagram-legend">${mode === 'sql' ? '<span><i class="schema-diagram-swatch" aria-hidden="true"></i>Database foreign key</span><span><b>1</b> one</span><span><b>0..*</b> zero or many</span><span><b>0..1</b> optional</span><span><b>PK / FK</b> primary / foreign key</span>' : '<span><i class="schema-diagram-swatch dashed" aria-hidden="true"></i>Application reference, not a foreign key</span><span>Green: MongoDB collections</span><span>Neutral: SQL identities</span>'}</div>
      <div class="schema-diagram-viewport" tabindex="0" role="region" aria-label="${mode === 'sql' ? 'SQL relationship' : 'MongoDB reference'} diagram. Scroll to pan, or use the Inspect selector." aria-describedby="schemaDiagramSource"><svg class="schema-diagram-canvas" viewBox="0 0 1240 ${height}" xmlns="http://www.w3.org/2000/svg" role="group" aria-label="Selectable database entities"><defs><marker id="schemaArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M1 1L9 5L1 9" fill="none" stroke="#a68d7c" stroke-width="1.6"/></marker><marker id="schemaArrowReference" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M1 1L9 5L1 9" fill="none" stroke="#64816d" stroke-width="1.6"/></marker></defs>${edges.map(drawEdge).join('')}${nodes.map(drawNode).join('')}</svg></div>
      <p class="schema-diagram-caption">${mode === 'sql' ? `Select a table to trace its relationships. Arrows point to the referenced parent. ${oldCount} legacy SQL community tables are retained for migration and listed below.` : 'Select a collection to trace its references. Reviews, threads and comments share content; dish feedback is embedded. No cross-database foreign keys or shared transaction are implied.'} On small screens, scroll the diagram or use Inspect.</p>
      <div id="schemaDiagramInspector" class="schema-diagram-inspector" aria-live="polite"></div>`;
    root().querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => {
      mode = button.dataset.mode; selected = ''; zoom = 1; build(); root().querySelector(`[data-mode="${mode}"]`).focus();
    }));
    root().querySelectorAll('[data-node]').forEach(node => {
      node.addEventListener('click', () => select(node.dataset.node));
      node.addEventListener('keydown', event => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); select(node.dataset.node); } });
    });
    root().querySelector('#schemaNodePicker').addEventListener('change', event => select(event.target.value));
    root().querySelector('[data-action="clear"]').addEventListener('click', () => select(''));
    root().querySelectorAll('[data-zoom]').forEach(button => button.addEventListener('click', () => {
      zoom = button.dataset.zoom === 'fit' ? 1 : Math.max(.75, Math.min(2, zoom + (button.dataset.zoom === 'in' ? .25 : -.25)));
      applyZoom();
      if (button.dataset.zoom === 'fit') { const viewport = root().querySelector('.schema-diagram-viewport'); viewport.scrollTop = 0; viewport.scrollLeft = 0; }
    }));
    applyZoom(); select(selected, false);
  }

  function applyZoom() {
    const canvas = root().querySelector('svg');
    canvas.style.width = `${zoom * 100}%`; canvas.style.minWidth = `${1000 * zoom}px`;
    root().querySelector('#schemaZoomValue').textContent = `${Math.round(zoom * 100)}%`;
    root().querySelector('[data-zoom="out"]').disabled = zoom <= .75;
    root().querySelector('[data-zoom="in"]').disabled = zoom >= 2;
  }

  function select(id, notify = true) {
    selected = id;
    const item = nodes.find(n => n.id === id), linked = edges.filter(e => e.from === id || e.to === id);
    const related = new Set([id, ...linked.flatMap(e => [e.from, e.to])]);
    root().querySelectorAll('[data-node]').forEach(node => {
      node.classList.toggle('is-selected', node.dataset.node === id);
      node.classList.toggle('is-unrelated', Boolean(id) && !related.has(node.dataset.node));
      node.setAttribute('aria-pressed', String(node.dataset.node === id));
    });
    root().querySelectorAll('[data-edge]').forEach(node => {
      const match = linked.includes(edges[Number(node.dataset.edge)]);
      node.classList.toggle('is-related', Boolean(id) && match);
      node.classList.toggle('is-unrelated', Boolean(id) && !match);
    });
    root().querySelector('#schemaNodePicker').value = id;
    const inspector = root().querySelector('#schemaDiagramInspector');
    if (!item) { inspector.innerHTML = '<h4>Start with a table</h4><p>Select <strong>favourite</strong> in the SQL view to see how a user saves a restaurant, or <strong>content</strong> in the MongoDB view to trace a review.</p>'; return; }
    if (notify) document.dispatchEvent(new CustomEvent('schema-selection', {detail: {id}}));
    const key = item.table?.primaryKey || [];
    inspector.innerHTML = `<h4>${escape(item.title)}</h4><p>${escape(item.description)}</p><div class="schema-inspector-grid"><div>${item.table ? `<p><strong>${key.length > 1 ? 'Composite primary key' : 'Primary key'}:</strong> <code>${escape(key.join(' + ') || 'None')}</code></p><p class="schema-field-list">${item.table.columns.length} columns · ${item.table.foreignKeys.length} outgoing foreign keys</p>` : `<p class="schema-field-list">${item.type === 'external' ? 'Identity owned by MariaDB.' : 'Selected fields: ' + item.fields.map(f => escape(f.name)).join(', ')}</p>`}<button type="button" data-action="columns">${item.table || item.type === 'external' ? 'View all SQL columns' : 'Open database evidence'}</button></div><div><strong>${mode === 'sql' ? 'Connected relationships' : 'Application references'}</strong>${linked.length ? `<ul>${linked.map(e => `<li><code>${escape(e.label)}</code></li>`).join('')}</ul>` : '<p>No relationships in this view.</p>'}</div></div>`;
    inspector.querySelector('[data-action="columns"]').addEventListener('click', () => {
      if (!item.table && item.type !== 'external') { location.href = 'database-lab.html#section-integrity'; return; }
      const name = item.table?.name || item.title;
      document.getElementById('schemaSearch').value = name;
      document.getElementById('schemaSearch').dispatchEvent(new Event('input', {bubbles: true}));
      const detail = [...document.querySelectorAll('[data-schema-table]')].find(t => t.dataset.schemaTable === name);
      if (detail) { detail.open = true; detail.scrollIntoView({block: 'start', behavior: 'auto'}); detail.querySelector('summary').focus(); }
    });
    const recordsButton = document.createElement('button');
    recordsButton.type = 'button'; recordsButton.textContent = 'View live records';
    recordsButton.addEventListener('click', () => document.dispatchEvent(new CustomEvent('schema-selection', {detail: {id, focus: true}})));
    if (!id.startsWith('custom_')) inspector.querySelector('.schema-inspector-grid > div').append(recordsButton);
  }

  window.SchemaDiagram = {
    render(value) { schema = value; build(); },
    clear(message) { schema = null; selected = ''; if (root()) root().innerHTML = `<p role="status">Diagram unavailable. ${escape(message)} Use Refresh schema to try again.</p>`; }
  };
})();
