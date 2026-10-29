let adminPage = 0;
let adminMenuPlaceId = null;
let adminSchema = null;
let menuImportPreview = null;
const ADMIN_PAGE_SIZE = 25;
const DETAIL_FIELDS = ['description', 'openingHours', 'website', 'menuUrl', 'phone', 'image', 'photoKind', 'photoSourceUrl', 'photoCredit'];

document.addEventListener('DOMContentLoaded', async () => {
  if (!await appReady) return;
  if (currentUser?.role !== 'admin') {
    document.querySelector('main').innerHTML = '<div class="empty-state"><h1>Administrator access</h1><p>Sign in with an administrator account to manage Makan Where.</p><a class="small-action" href="auth.html?next=admin.html">Administrator sign-in</a></div>';
    return;
  }
  renderAdminEstablishments();
  attachAdminForm();
  attachMenuForm();
  attachMenuImports();
  document.querySelectorAll('[data-admin-panel]').forEach(button => button.addEventListener('click', () => showAdminPanel(button.dataset.adminPanel)));
  document.getElementById('adminSearch').addEventListener('input', () => { adminPage = 0; renderAdminEstablishments(); });
  document.getElementById('adminMenuFilter').addEventListener('change', () => { adminPage = 0; renderAdminEstablishments(); });
  document.getElementById('adminPrevious').addEventListener('click', () => { adminPage--; renderAdminEstablishments(); });
  document.getElementById('adminNext').addEventListener('click', () => { adminPage++; renderAdminEstablishments(); });
  document.getElementById('refreshSchemaBtn').addEventListener('click', () => window.SchemaLive.refresh());
  document.getElementById('schemaSearch').addEventListener('input', renderSchema);
  window.SchemaEditor.init();
  window.SchemaLive.init();
  if (location.hash === '#schema') await showAdminPanel('schema');
  const requestedMenu = Number(new URLSearchParams(location.search).get('menu'));
  if (requestedMenu && foodFinderData.some(p => p.id === requestedMenu)) {
    adminMenuPlaceId = requestedMenu; renderAdminMenu();
    document.getElementById('adminMenuPanel').scrollIntoView({block:'start'});
  }
});

function adminMessage(message) {
  const notice = document.getElementById('adminNotice');
  notice.textContent = message;
  notice.hidden = false;
}

async function showAdminPanel(name) {
  if (!InlineActions.canLeave()) return;
  document.querySelectorAll('[data-admin-panel]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.adminPanel === name)));
  for (const panel of ['catalogue', 'imports', 'reports', 'schema']) document.getElementById('panel-' + panel).hidden = panel !== name;
  if (name === 'imports') await withAction(null, loadMenuImportStatus);
  if (name === 'reports') await withAction(null, loadReports);
  if (name === 'schema') await window.SchemaLive.refresh();
}

function renderAdminEstablishments() {
  if (!InlineActions.canLeave()) return;
  document.getElementById('statsPhotos').textContent = foodFinderData.filter(p => p.image).length.toLocaleString();
  document.getElementById('statsLinks').textContent = foodFinderData.filter(p => p.menuUrl || p.menu.some(d => d.availability)).length.toLocaleString();
  document.getElementById('statsCount').textContent = foodFinderData.length.toLocaleString();
  document.getElementById('statsMenus').textContent = foodFinderData.filter(p => p.menu.some(d => d.availability)).length.toLocaleString();
  const prices = foodFinderData.flatMap(p => p.menu.filter(d => d.availability && d.price !== null).map(d => d.price));
  document.getElementById('statsAvgPrice').textContent = prices.length ? priceLabel(prices.reduce((a, b) => a + b, 0) / prices.length) : 'No menu yet';
  const search = document.getElementById('adminSearch').value.trim().toLowerCase();
  const coverage = document.getElementById('adminMenuFilter').value;
  const matches = foodFinderData.filter(p => [p.name, p.area, p.cuisine, p.address].some(value => value.toLowerCase().includes(search)) &&
    (coverage === 'all' || (coverage === 'reference' ? p.hasReferenceMenu : p.menu.some(d => d.availability) === (coverage === 'available'))));
  adminPage = Math.max(0, Math.min(adminPage, Math.ceil(matches.length / ADMIN_PAGE_SIZE) - 1));
  const start = adminPage * ADMIN_PAGE_SIZE;
  const list = document.getElementById('adminEstablishments');
  document.getElementById('adminPageInfo').textContent = matches.length ? `${start + 1}–${Math.min(start + ADMIN_PAGE_SIZE, matches.length)} of ${matches.length.toLocaleString()} establishments` : 'No matching establishments';
  document.getElementById('adminPrevious').disabled = adminPage === 0;
  document.getElementById('adminNext').disabled = start + ADMIN_PAGE_SIZE >= matches.length;
  list.innerHTML = matches.slice(start, start + ADMIN_PAGE_SIZE).map(item => `<div class="admin-row"><img class="admin-row-photo" src="${imageUrl(item.image)}" alt="${escapeHtml(item.photo.kind === 'venue' ? 'Venue photo' : 'Illustrative photo')}" loading="lazy"><div><strong>${escapeHtml(item.name)}</strong><br><small>${escapeHtml(item.area)} · ${escapeHtml(item.address)}</small><p>${item.menu.filter(d => d.availability && d.price !== null).length} priced menu items ${item.menuUrl ? externalLink(item.menuUrl, 'Source menu ↗') : ''} ${listingLabel(item)}</p></div><div class="admin-row-actions"><button class="small-action" data-menu="${item.id}">Manage menu</button><button class="secondary-btn" data-import-menu="${item.id}">Import menu</button><button class="small-action" data-edit="${item.id}">Edit</button><button class="danger-btn" data-archive="${item.id}">Archive</button></div></div>`).join('') || '<p class="empty-state">Try another name, area or cuisine.</p>';
  list.querySelectorAll('[data-import-menu]').forEach(button => button.addEventListener('click', () => withAction(button, async () => {
    setMenuImportJson(await api(`/admin/establishments/${button.dataset.importMenu}/menu-template`));
    await showAdminPanel('imports');
  })));
  list.querySelectorAll('[data-archive]').forEach(button => button.addEventListener('click', () => {
    const item = foodFinderData.find(place => place.id === Number(button.dataset.archive));
    InlineActions.open({host:button.closest('.admin-row'), trigger:button, title:`Archive ${item.name}?`, destructive:true,
      content:'<p>This venue will be hidden from the catalogue. Existing reviews and favourites will be retained.</p>',
      submitLabel:'Archive venue', busyLabel:'Archiving…',
      submit:() => api(`/admin/establishments/${item.id}`, {method:'DELETE'}),
      success:async () => {
        if (adminMenuPlaceId === item.id) closeAdminMenu();
        if (document.getElementById('editId').value === String(item.id)) resetAdminForm();
        await refreshPlaces(); renderAdminEstablishments(); adminMessage('Establishment archived.');
        document.getElementById('adminSearch').focus({preventScroll:true});
      }});
  }));
  list.querySelectorAll('[data-menu]').forEach(button => button.addEventListener('click', () => {
    adminMenuPlaceId = Number(button.dataset.menu);
    resetDishForm(); renderAdminMenu();
    document.getElementById('adminMenuPanel').scrollIntoView({behavior: 'smooth', block: 'start'});
  }));
  list.querySelectorAll('[data-edit]').forEach(button => button.addEventListener('click', () => withAction(button, async () => {
    // The compact catalogue omits descriptions/hours. Load the full record so
    // editing a photo cannot accidentally clear those existing fields.
    const item = (await api(`/establishments/${button.dataset.edit}`)).establishment;
    document.getElementById('editId').value = item.id;
    for (const key of ['name', 'area', 'category', 'cuisine', 'address']) document.getElementById(`admin${key[0].toUpperCase()}${key.slice(1)}`).value = item[key];
    document.getElementById('adminAddress').value = item.address === 'Address not listed' ? '' : item.address;
    document.getElementById('adminCuisine').value = item.cuisines.join(', ');
    const details = {...item, image: item.customImage || '', photoKind: item.photo.kind, photoSourceUrl: item.photo.sourceUrl, photoCredit: item.photo.credit};
    for (const key of DETAIL_FIELDS) document.getElementById(`admin${key[0].toUpperCase()}${key.slice(1)}`).value = details[key] || '';
    document.getElementById('adminPhotoPreview').src = imageUrl(item.image);
    document.getElementById('adminPhotoPreview').hidden = false;
    document.getElementById('adminFormTitle').textContent = 'Edit establishment';
    document.getElementById('adminSubmitBtn').textContent = 'Save changes';
    document.getElementById('cancelEditBtn').hidden = false;
    document.getElementById('adminForm').scrollIntoView({behavior: 'smooth', block: 'center'});
  })));
}

function attachAdminForm() {
  document.getElementById('adminForm').addEventListener('submit', event => {
    event.preventDefault();
    withAction(document.getElementById('adminSubmitBtn'), async () => {
      const body = {};
      for (const key of ['name', 'area', 'category', 'cuisine', 'address']) body[key] = document.getElementById(`admin${key[0].toUpperCase()}${key.slice(1)}`).value.trim();
      for (const key of DETAIL_FIELDS) body[key] = document.getElementById(`admin${key[0].toUpperCase()}${key.slice(1)}`).value.trim();
      const id = document.getElementById('editId').value;
      await api(`/admin/establishments${id ? '/' + id : ''}`, {method: id ? 'PATCH' : 'POST', body});
      resetAdminForm(); await refreshPlaces(); renderAdminEstablishments(); renderAdminMenu();
      adminMessage(id ? 'Establishment updated.' : 'Establishment added.');
    });
  });
  document.getElementById('cancelEditBtn').addEventListener('click', resetAdminForm);
}

function resetAdminForm() {
  document.getElementById('adminForm').reset();
  document.getElementById('editId').value = '';
  document.getElementById('adminFormTitle').textContent = 'Add establishment';
  document.getElementById('adminSubmitBtn').textContent = 'Add establishment';
  document.getElementById('cancelEditBtn').hidden = true;
  document.getElementById('adminPhotoPreview').hidden = true;
}

function closeAdminMenu() {
  if (!InlineActions.canLeave()) return;
  adminMenuPlaceId = null;
  document.getElementById('adminMenuPanel').hidden = true;
  resetDishForm();
}

function resetDishForm() {
  document.getElementById('adminDishForm').reset();
  document.getElementById('dishPrice').required = true;
  document.getElementById('dishPrice').placeholder = '';
  document.getElementById('editDishId').value = '';
  document.getElementById('dishFormTitle').textContent = 'Add dish';
  document.getElementById('saveDishBtn').textContent = 'Add dish';
  document.getElementById('cancelDishBtn').hidden = true;
}

function attachMenuForm() {
  document.getElementById('closeMenuBtn').addEventListener('click', closeAdminMenu);
  document.getElementById('cancelDishBtn').addEventListener('click', resetDishForm);
  document.getElementById('adminDishForm').addEventListener('submit', event => {
    event.preventDefault();
    withAction(document.getElementById('saveDishBtn'), async () => {
      const id = document.getElementById('editDishId').value;
      const body = {name: document.getElementById('dishName').value.trim(), price: document.getElementById('dishPrice').value, dietary: document.getElementById('dishDietary').value.trim(), description: document.getElementById('dishDescription').value.trim()};
      await api(`/admin/establishments/${adminMenuPlaceId}/dishes${id ? '/' + id : ''}`, {method: id ? 'PATCH' : 'POST', body});
      resetDishForm(); await refreshPlaces(); renderAdminEstablishments(); renderAdminMenu();
      adminMessage(id ? 'Dish updated.' : 'Dish added.');
    });
  });
}

function renderAdminMenu() {
  if (!InlineActions.canLeave()) return;
  const place = foodFinderData.find(p => p.id === adminMenuPlaceId);
  if (!place) { closeAdminMenu(); return; }
  document.getElementById('adminMenuPanel').hidden = false;
  document.getElementById('adminMenuTitle').textContent = place.name + ' — menu';
  const list = document.getElementById('adminDishes');
  list.innerHTML = place.menu.map(d => `<div class="admin-row"><div><strong>${escapeHtml(d.name)}</strong><span class="tag">${d.availability ? 'On menu' : 'Removed'}</span>${d.isReference ? '<span class="tag">Chain reference</span>' : ''}<p>${priceLabel(d.price)} · ${escapeHtml(d.dietary || 'No dietary label')}</p><p>${escapeHtml(d.description || '')}</p>${menuSourceMarkup(d)}</div><div class="admin-row-actions"><button class="small-action" data-edit-dish="${d.id}">Edit dish</button><button class="${d.availability ? 'danger-btn' : 'secondary-btn'}" data-toggle-dish="${d.id}">${d.availability ? 'Remove from menu' : 'Restore dish'}</button></div></div>`).join('') || '<p>No dishes yet. Add the first dish below or choose Import menu.</p>';
  if (place.menuHighlights?.length) list.insertAdjacentHTML('beforeend', `<details class="listing-editor"><summary>Published menu highlights (${place.menuHighlights.length})</summary><p>From the linked chain menu. Outlet availability varies; this source does not supply item prices.</p><div class="menu-highlights">${place.menuHighlights.map(name => `<span>${escapeHtml(name)}</span>`).join('')}</div>${externalLink(place.menuHighlightsSource, 'View source menu')}</details>`);
  list.querySelectorAll('[data-edit-dish]').forEach(button => button.addEventListener('click', () => {
    const dish = place.menu.find(d => d.id === Number(button.dataset.editDish));
    document.getElementById('editDishId').value = dish.id;
    document.getElementById('dishName').value = dish.name;
    document.getElementById('dishPrice').value = dish.price === null ? '' : dish.price.toFixed(2);
    document.getElementById('dishPrice').required = dish.price !== null;
    document.getElementById('dishPrice').placeholder = dish.price === null ? 'Price not listed' : '';
    document.getElementById('dishDietary').value = dish.dietary;
    document.getElementById('dishDescription').value = dish.description || '';
    document.getElementById('dishFormTitle').textContent = 'Edit dish';
    document.getElementById('saveDishBtn').textContent = 'Save dish changes';
    document.getElementById('cancelDishBtn').hidden = false;
    document.getElementById('dishName').focus();
  }));
  list.querySelectorAll('[data-toggle-dish]').forEach(button => button.addEventListener('click', () => {
    const dish = place.menu.find(d => d.id === Number(button.dataset.toggleDish));
    const success = async () => {
      resetDishForm(); await refreshPlaces(); renderAdminEstablishments(); renderAdminMenu();
      adminMessage(dish.availability ? 'Dish removed from the public menu.' : 'Dish restored.');
      document.querySelector(`[data-toggle-dish="${dish.id}"]`)?.focus({preventScroll:true});
    };
    if (!dish.availability) {
      if (!InlineActions.canLeave()) return;
      InlineActions.run(button, button.closest('.admin-row'), async () => {
        await api(`/admin/establishments/${place.id}/dishes/${dish.id}`, {method:'PATCH',body:{...dish,availability:true}});
        await success();
      }, 'Restoring…');
      return;
    }
    InlineActions.open({host:button.closest('.admin-row'), trigger:button, title:`Remove ${dish.name} from the menu?`, destructive:true,
      content:'<p>This dish will be hidden from the public menu. Past review links will be retained. You can restore it here later.</p>',
      submitLabel:'Remove dish', busyLabel:'Removing…',
      submit:() => api(`/admin/establishments/${place.id}/dishes/${dish.id}`, {method:'DELETE'}), success});
  }));
}

async function loadSchema() {
  const button = document.getElementById('refreshSchemaBtn');
  if (button.disabled) return;
  button.disabled = true;
  const tables = document.getElementById('schemaTables');
  try {
    if (!adminSchema) tables.textContent = 'Reading the database structure…';
    const before = adminSchema;
    adminSchema = await api('/admin/schema');
    const columns = adminSchema.tables.reduce((sum, table) => sum + table.columns.length, 0);
    document.getElementById('schemaSummary').textContent = `${adminSchema.engine} · ${adminSchema.tables.length} tables · ${columns} columns · Live, read-only metadata`;
    if (JSON.stringify(before) !== JSON.stringify(adminSchema)) {
      renderSchema();
      window.SchemaDiagram?.render(adminSchema);
    }
    window.SchemaLive?.schemaReceived(before, adminSchema);
    window.SchemaEditor?.update(adminSchema);
  } catch (error) {
    adminSchema = null;
    document.getElementById('schemaSummary').textContent = 'Schema unavailable';
    tables.textContent = error.message;
    window.SchemaDiagram?.clear(error.message);
    window.SchemaLive?.schemaFailed();
  } finally { button.disabled = false; }
}

function renderSchema() {
  if (!adminSchema) return;
  const search = document.getElementById('schemaSearch').value.trim().toLowerCase();
  const matching = adminSchema.tables.filter(t => t.name.toLowerCase().includes(search) || t.columns.some(c => c.name.toLowerCase().includes(search)));
  const columnNames = values => values.map(value => escapeHtml(value)).join(', ');
  document.getElementById('schemaTables').innerHTML =
    (adminSchema.missingTables.length ? `<p class="form-notice error">Missing application tables: ${columnNames(adminSchema.missingTables)}</p>` : '') +
    matching.map(table => `<details class="schema-table" data-schema-table="${escapeHtml(table.name)}"><summary><strong>${escapeHtml(table.name)}</strong><span>${table.columns.length} columns · ${table.foreignKeys.length} relationships</span></summary>
      <div class="schema-table-body"><div class="schema-scroll"><table><caption>${escapeHtml(table.name)} columns</caption><thead><tr><th scope="col">Column</th><th scope="col">Type</th><th scope="col">Key</th><th scope="col">Nullable</th><th scope="col">Default</th></tr></thead><tbody>${table.columns.map(column => `<tr><th scope="row">${escapeHtml(column.name)}</th><td>${escapeHtml(column.type)}</td><td>${column.primaryKey ? 'PK ' : ''}${table.foreignKeys.some(f => f.columns.includes(column.name)) ? 'FK' : ''}</td><td>${column.nullable ? 'Yes' : 'No'}</td><td>${escapeHtml(column.default ?? '—')}</td></tr>`).join('')}</tbody></table></div>
      <h3>Relationships</h3>${table.foreignKeys.length ? '<ul>' + table.foreignKeys.map(f => `<li><code>${columnNames(f.columns)}</code> → <code>${escapeHtml(f.table)} (${columnNames(f.targetColumns)})</code></li>`).join('') + '</ul>' : '<p>No outgoing foreign keys.</p>'}
      <h3>Indexes and constraints</h3><ul><li>Primary key: ${columnNames(table.primaryKey) || 'None'}</li>${table.uniqueConstraints.map(u => `<li>Unique: ${columnNames(u.columns)}</li>`).join('')}${table.indexes.map(i => `<li>${i.unique ? 'Unique index' : 'Index'} ${escapeHtml(i.name)}: ${columnNames(i.columns)}</li>`).join('')}${table.checks.map(c => `<li>Check: <code>${escapeHtml(c.expression)}</code></li>`).join('')}</ul></div></details>`).join('') || '<p>No matching tables or columns.</p>';
}

async function loadReports() {
  if (!InlineActions.canLeave()) return;
  const {reports} = await api('/admin/reports');
  // The feed also works with deployments predating the single-post endpoint.
  const posts = reports.length ? await apiAll('/content', 'content') : [];
  const section = document.getElementById('moderationReports');
  section.innerHTML = `<h2>Content reports</h2>${reports.length ? reports.map(r => `<article class="review-item"><strong>${escapeHtml(r.reason)}</strong><p class="user-content">${escapeHtml(r.text)}</p><div class="content-actions"><button type="button" class="danger-btn" data-remove="${r.contentId}" ${posts.some(post => post.id === r.contentId) ? '' : 'disabled'}>${posts.some(post => post.id === r.contentId) ? 'Remove content' : 'Content already hidden'}</button><button type="button" class="secondary-btn" data-resolve="${r.id}" data-status="resolved">Resolve</button><button type="button" class="secondary-btn" data-resolve="${r.id}" data-status="dismissed">Dismiss</button></div></article>`).join('') : '<p>No open reports.</p>'}`;
  section.querySelectorAll('[data-remove]').forEach(button => button.addEventListener('click', () => {
    const item = posts.find(post => post.id === Number(button.dataset.remove));
    if (!item) return;
    const host = button.closest('article');
    InlineActions.open({host, trigger:button, title:'Remove this reported content?', destructive:true,
      content:`<p>The ${item.kind === 'thread' ? 'discussion and its replies' : 'post'} will be hidden from public view. You can then resolve this report below.</p>`,
      submitLabel:'Remove content', busyLabel:'Removing…',
      submit:() => api(`/content/${item.id}`, {method:'DELETE',headers:Number.isInteger(item.revision) ? {'If-Match':String(item.revision)} : {}}),
      success:() => {
        section.querySelectorAll(`[data-remove="${item.id}"]`).forEach(control => { control.disabled = true; control.textContent = 'Content removed'; });
        InlineActions.notice(host, 'Content removed. Resolve the report to close it.');
        host.querySelector('[data-resolve]')?.focus({preventScroll:true});
      }});
  }));
  section.querySelectorAll('[data-resolve]').forEach(button => button.addEventListener('click', () => {
    const host = button.closest('article');
    const dismiss = button.dataset.status === 'dismissed';
    InlineActions.open({host, trigger:button, title:dismiss ? 'Dismiss this report' : 'Resolve this report',
      content:`<p>${dismiss ? 'Close this report without taking further action.' : 'Record the action taken before closing this report.'}</p><label for="__ACTION_ID__-note">Moderation note<textarea id="__ACTION_ID__-note" name="note" maxlength="1000" rows="3" required></textarea></label>`,
      submitLabel:dismiss ? 'Dismiss report' : 'Resolve report', busyLabel:'Saving…',
      submit:form => api(`/admin/reports/${button.dataset.resolve}`, {method:'PATCH',body:{status:button.dataset.status,note:InlineActions.requireValue(form.elements.namedItem('note'), 'Enter a moderation note of up to 1,000 characters.', 1000)}}),
      success:() => {
        const status = document.createElement('p'); status.className = 'post-removed'; status.tabIndex = -1; status.setAttribute('role','status');
        status.textContent = dismiss ? 'Report dismissed.' : 'Report resolved.';
        host.replaceWith(status); status.focus({preventScroll:true});
      }});
  }));
}

function invalidateMenuPreview() {
  menuImportPreview = null;
  document.getElementById('applyMenuImport').disabled = true;
  document.getElementById('menuImportPreview').textContent = '';
}

function setMenuImportJson(menu) {
  document.getElementById('menuImportJson').value = JSON.stringify(menu, null, 2);
  invalidateMenuPreview();
}

async function loadMenuImportStatus() {
  const status = await api('/admin/menu-imports');
  document.getElementById('menuImportStatus').textContent = `${status.withMenu.toLocaleString()} of ${status.venues.toLocaleString()} establishments have menus. ${status.missingMenu.toLocaleString()} still need a source. API import: ${status.apiConfigured ? 'configured on server' : 'not configured; administrator import is available'}.`;
  document.getElementById('menuImportHistory').innerHTML = status.history.map(row => `<article class="review-item"><strong>${escapeHtml(row.sourceName)}</strong><p>${row.added} dishes across ${row.placeIds.length} establishments · ${new Date(row.createdAt).toLocaleString('en-SG')}${row.isReference ? ' · chain reference' : ''}</p>${menuSourceMarkup({sourceName:row.sourceName,sourceUrl:row.sourceUrl,sourceObservedAt:row.observedAt})}</article>`).join('') || '<p>No menu imports yet.</p>';
}

function attachMenuImports() {
  document.getElementById('menuImportJson').addEventListener('input', invalidateMenuPreview);
  document.getElementById('loadKfcMenu').addEventListener('click', event => withAction(event.currentTarget, async () => {
    setMenuImportJson(await api('/admin/menu-imports/kfc-reference'));
    adminMessage('KFC reference loaded. Review the source, prices and establishments, then preview.');
  }));
  document.getElementById('menuImportFile').addEventListener('change', event => withAction(null, async () => {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 60000) throw new Error('Choose a menu JSON file smaller than 60 KB. Split larger imports.');
    const menu = JSON.parse(await file.text());
    if (menu.matchNames) throw new Error('This file uses name matching. Use the supplied Python importer, or Load KFC reference menu for the bundled file.');
    setMenuImportJson(menu);
  }));
  document.getElementById('menuImportForm').addEventListener('submit', event => {
    event.preventDefault();
    withAction(document.getElementById('previewMenuImport'), async () => {
      invalidateMenuPreview();
      let menu;
      try { menu = JSON.parse(document.getElementById('menuImportJson').value); }
      catch (_) { throw new Error('The menu must be valid JSON. Check quotes, commas and brackets.'); }
      const result = await api('/admin/menu-imports', {method:'POST',body:{menu}});
      menuImportPreview = result;
      document.getElementById('applyMenuImport').disabled = !result.added || result.conflicts.length > 0;
      document.getElementById('menuImportPreview').innerHTML = `<div class="admin-card"><h3>Import preview</h3><p><strong>${result.added}</strong> new dishes · ${result.skipped} existing dishes preserved · ${result.conflicts.length} name conflicts</p><p>${escapeHtml(result.menu.sourceName)} · ${result.menu.isReference ? 'Chain reference; outlet availability and prices may differ.' : 'Outlet menu.'}</p><div class="schema-scroll"><table><thead><tr><th>Establishment</th><th>Address</th><th>New dishes</th></tr></thead><tbody>${result.places.map(p => `<tr><td>${escapeHtml(p.name)} (#${p.id})</td><td>${escapeHtml(p.address || 'Address not listed')}</td><td>${p.newItems}</td></tr>`).join('')}</tbody></table></div><details><summary>Review all ${result.menu.items.length} items and prices</summary><ul>${result.menu.items.map(d => `<li>${escapeHtml(d.name)} — ${d.price === null ? 'Price not listed' : 'SGD ' + escapeHtml(d.price)}</li>`).join('')}</ul></details>${result.conflicts.length ? '<p>Resolve matching dish names in Manage menu before importing.</p>' : ''}</div>`;
    });
  });
  document.getElementById('applyMenuImport').addEventListener('click', async event => {
    const button = event.currentTarget;
    await withAction(button, async () => {
      if (!menuImportPreview) return;
      const result = await api('/admin/menu-imports', {method:'POST',body:{menu:menuImportPreview.menu,apply:true,previewToken:menuImportPreview.previewToken}});
      invalidateMenuPreview();
      await refreshPlaces(); renderAdminEstablishments(); renderAdminMenu();
      await loadMenuImportStatus();
      adminMessage(`Imported ${result.added} dishes. ${result.skipped} existing dishes were preserved.`);
    });
    button.disabled = !menuImportPreview || !menuImportPreview.added || menuImportPreview.conflicts.length > 0;
  });
}
