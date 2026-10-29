(() => {
  let schema, reviewed = null, working = false;
  const el = id => document.getElementById(id);
  function invalidate() { reviewed = null; el('schemaEditPreview').hidden = true; }
  function options(select, values) {
    const html = values.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
    if (select.innerHTML === html) return;
    const old = select.value; select.innerHTML = html;
    if (values.includes(old)) select.value = old;
  }
  function parentColumns() {
    const table = schema?.tables.find(t => t.name === el('schemaEditParent').value);
    options(el('schemaEditParentColumn'), table?.primaryKey.length === 1 ? table.primaryKey : []);
  }
  function operation() {
    invalidate(); const op = el('schemaEditOperation').value;
    el('schemaEditNameField').hidden = op !== 'create_table';
    el('schemaEditTableField').hidden = op === 'create_table';
    el('schemaEditTypeField').hidden = op !== 'add_column';
    el('schemaEditParentField').hidden = op !== 'add_foreign_key';
    el('schemaEditParentColumnField').hidden = op !== 'add_foreign_key';
    el('schemaEditColumnLabel').textContent = op === 'create_table' ? 'Primary key name' : op === 'add_column' ? 'New column name' : 'Existing child column';
    el('schemaEditColumn').value = op === 'create_table' ? 'id' : '';
    el('schemaEditColumn').placeholder = op === 'create_table' ? 'id' : 'custom_place_id';
  }
  function change() {
    return {operation: el('schemaEditOperation').value,
      table: el('schemaEditOperation').value === 'create_table' ? el('schemaEditName').value.trim() : el('schemaEditTable').value,
      column: el('schemaEditColumn').value.trim(), type: el('schemaEditType').value,
      parentTable: el('schemaEditParent').value, parentColumn: el('schemaEditParentColumn').value};
  }
  function controls() {
    const enabled = ['MariaDB', 'mysql', 'mariadb'].includes(schema?.engine) && !working;
    el('schemaEditForm').querySelectorAll('input,select,button').forEach(control => {control.disabled = !enabled;});
    el('schemaApplyBtn').disabled = !enabled;
  }
  window.SchemaEditor = {
    init() {
      el('schemaEditForm').addEventListener('input', invalidate);
      el('schemaEditForm').addEventListener('change', invalidate);
      el('schemaEditOperation').addEventListener('change', operation);
      el('schemaEditParent').addEventListener('change', parentColumns);
      el('schemaEditForm').addEventListener('submit', async event => {
        event.preventDefault(); if (working) return;
        const proposal = change(); invalidate(); working = true; controls();
        el('schemaEditStatus').textContent = 'Checking the proposed change against the database…';
        try {
          const preview = await api('/admin/schema/preview', {method:'POST', body:{change:proposal}});
          reviewed = {change: proposal, previewToken: preview.previewToken};
          el('schemaEditSQL').textContent = preview.sql + ';';
          el('schemaEditDescription').textContent = preview.description;
          el('schemaEditPreview').hidden = false;
          el('schemaEditStatus').textContent = 'Preview ready. No structure has changed. This preview expires in 5 minutes.';
        } catch (error) { el('schemaEditStatus').textContent = error.message; }
        finally { working = false; controls(); }
      });
      el('schemaApplyBtn').addEventListener('click', async () => {
        if (!reviewed || working) return;
        working = true; controls(); el('schemaEditStatus').textContent = 'Applying the reviewed schema change…';
        try {
          const result = await api('/admin/schema/apply', {method:'POST', body:reviewed});
          invalidate(); el('schemaEditStatus').textContent = `Applied successfully to ${result.table}. The database diagram is refreshing.`;
          await loadSchema();
          el('schemaEditStatus').textContent = `Applied successfully to ${result.table}. See its columns and relationships in the diagram below.`;
        } catch (error) { invalidate(); el('schemaEditStatus').textContent = error.message; await loadSchema(); }
        finally { working = false; controls(); }
      });
    },
    update(value) {
      const first = !schema; schema = value;
      options(el('schemaEditTable'), value.tables.map(t => t.name));
      options(el('schemaEditParent'), value.tables.filter(t => t.primaryKey.length === 1).map(t => t.name));
      parentColumns(); controls();
      if (first) el('schemaEditStatus').textContent = ['MariaDB','mysql','mariadb'].includes(schema.engine) ? 'Choose an operation and preview its SQL.' : 'Schema editing requires a MariaDB/MySQL connection.';
    }
  };
})();
