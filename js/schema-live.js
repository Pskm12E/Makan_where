/* Poll committed database reads while the administrator is viewing the schema. */
(() => {
  let busy = false, selection = 'sql:dish', key = '', previous = null, sequence = 0;
  let timer, counts = null, schemaError = false, lastStructureChange = '';
  const el = id => document.getElementById(id);
  const visible = () => !document.hidden && !el('panel-schema').hidden;
  const format = value => value == null ? 'NULL' : typeof value === 'object' ? JSON.stringify(value) : String(value);
  const identity = (row, keys) => JSON.stringify(keys.map(k => row[k]));
  const time = value => new Date(value).toLocaleTimeString();

  function updateCounts(snapshot) {
    counts = snapshot;
    document.querySelectorAll('#schemaDiagram [data-node]').forEach(node => {
      const id = node.dataset.node, [store, name] = id.includes(':') ? id.split(':') : ['sql', id];
      const count = snapshot[store === 'sql' ? 'sqlCounts' : 'mongoCounts'][name];
      if (count === undefined) return;
      const note = node.querySelector('.node-note');
      note.textContent = `${Number(count).toLocaleString()} ${store === 'sql' ? 'rows' : 'documents'} · select to inspect`;
    });
  }

  async function records() {
    const current = ++sequence;
    const [store, table] = selection.split(':');
    try {
      const snapshot = await api('/admin/schema-records?' + new URLSearchParams({store, table, key}));
      if (current !== sequence) return;
      const item = snapshot.selection;
      const same = previous?.selection.store === item.store && previous?.selection.name === item.name && previous?.selection.key === item.key;
      const prior = new Map((same ? previous.selection.rows : []).map(row => [identity(row, item.keys), row]));
      let changed = 0;
      const currentIds = new Set();
      const rows = item.rows.map(row => {
        const id = identity(row, item.keys), old = prior.get(id);
        currentIds.add(id);
        return `<tr>${item.columns.map(column => {
          const value = format(row[column]), was = format(old?.[column]);
          const different = same && (!old || value !== was);
          if (different) changed++;
          return `<td${different ? ' class="schema-value-changed"' : ''}>${escapeHtml(value)}${different ? `<small>${old ? 'Previously: ' + escapeHtml(was) : 'New in this view'}</small>` : ''}</td>`;
        }).join('')}</tr>`;
      }).join('');
      const gone = [...prior.keys()].filter(id => !currentIds.has(id)).length;
      el('schemaRecordKeyHint').textContent = item.keys.join(', ') + '; blank for highest 20 keys';
      el('schemaRecordStatus').textContent = `${item.store === 'sql' ? 'SQL' : 'MongoDB'} · ${item.name} · ${item.total.toLocaleString()} stored records · showing ${item.rows.length}${item.key ? ' matching the key' : ' (highest keys first)'} · read ${time(snapshot.capturedAt)}`;
      if (!same) el('schemaRecordChange').textContent = 'Watching this selection. Make a change in the app to compare the next read.';
      else if (changed || gone || item.total !== previous.selection.total) {
        el('schemaRecordChange').textContent = `Change observed at ${time(snapshot.capturedAt)}: ${changed} changed/new cells; ${gone} records left this view. Total ${previous.selection.total} → ${item.total}. Records leaving a limited view may have moved outside its 20-row window.`;
      }
      // Keep a highlighted comparison until another change, selection or manual
      // refresh replaces it. Quiet polling must not move keyboard focus/scroll.
      if (!same || changed || gone || item.total !== previous.selection.total) {
        el('schemaRecordRows').innerHTML = rows ? `<table><caption>Saved values in ${escapeHtml(item.name)}</caption><thead><tr>${item.columns.map(c => `<th scope="col">${escapeHtml(c)}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>` : '<p>No matching records. The record may have been deleted or the key may not exist.</p>';
      }
      previous = snapshot;
      updateCounts(snapshot);
      el('schemaLiveStatus').textContent = `${el('schemaAutoRefresh').checked ? 'Live' : 'Auto-refresh paused'} · records checked ${time(snapshot.capturedAt)}${schemaError ? ' · schema refresh unavailable' : ''}`;
    } catch (error) {
      if (current !== sequence) return;
      el('schemaRecordStatus').textContent = 'Records could not be refreshed: ' + error.message;
      el('schemaLiveStatus').textContent = 'Refresh failed. Any displayed values are from the last successful read.';
    }
  }

  async function refresh() {
    if (busy || !visible()) return;
    busy = true;
    try { await Promise.all([loadSchema(), records()]); }
    finally { busy = false; }
  }

  function choose(value, focus = false) {
    if (![...el('schemaRecordTable').options].some(option => option.value === value)) return;
    selection = value; key = ''; previous = null;
    el('schemaRecordTable').value = value; el('schemaRecordKey').value = '';
    el('schemaRecordRows').textContent = 'Reading saved records…';
    records();
    if (focus) { el('schemaRecords').scrollIntoView({block: 'start'}); el('schemaRecordTable').focus({preventScroll: true}); }
  }

  window.SchemaLive = {
    init() {
      el('schemaRecordTable').addEventListener('change', event => choose(event.target.value));
      el('schemaRecordFilter').addEventListener('submit', event => {
        event.preventDefault(); key = el('schemaRecordKey').value.trim(); previous = null;
        el('schemaRecordRows').textContent = 'Reading saved records…'; records();
      });
      el('schemaAutoRefresh').addEventListener('change', () => {
        if (el('schemaAutoRefresh').checked) refresh();
        else el('schemaLiveStatus').textContent = 'Auto-refresh paused. Use Refresh schema to read both structure and records.';
      });
      document.addEventListener('schema-selection', event => choose(event.detail.id.includes(':') ? event.detail.id : 'sql:' + event.detail.id, event.detail.focus));
      document.addEventListener('visibilitychange', () => { if (visible() && el('schemaAutoRefresh').checked) refresh(); });
      timer = setInterval(() => { if (visible() && el('schemaAutoRefresh').checked) refresh(); }, 10000);
      window.addEventListener('pagehide', () => clearInterval(timer), {once: true});
      el('schemaAutoRefresh').disabled = false;
      el('schemaRecordFilter').querySelectorAll('input,select,button').forEach(control => { control.disabled = false; });
    },
    refresh, records,
    schemaReceived(before, after) {
      schemaError = false;
      if (before) {
        const old = new Map(before.tables.map(t => [t.name, JSON.stringify(t)]));
        const changed = after.tables.filter(t => old.get(t.name) !== JSON.stringify(t)).map(t => t.name);
        changed.push(...before.tables.filter(t => !after.tables.some(n => n.name === t.name)).map(t => t.name));
        if (changed.length) {
          lastStructureChange = `Structure change observed at ${new Date().toLocaleTimeString()}: ${changed.join(', ')}. Diagram and column details updated.`;
          document.querySelectorAll('#schemaDiagram [data-node]').forEach(node => node.classList.toggle('is-schema-changed', changed.includes(node.dataset.node)));
        }
        el('schemaStructureStatus').textContent = lastStructureChange || 'Structure unchanged at this read. Saved values and row counts update below; editing data does not add columns or foreign keys.';
      }
      if (counts) updateCounts(counts);
    },
    schemaFailed() { schemaError = true; }
  };
})();
