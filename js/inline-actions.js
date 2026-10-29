/* Shared in-place actions. Drafts stay visible on validation/network errors. */
(() => {
  let active = null;
  let sequence = 0;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function notice(host, message, error = false) {
    if (!host?.isConnected) return;
    let node = host.querySelector(':scope > .inline-status');
    if (!node) {
      node = document.createElement('p');
      node.className = 'inline-status';
      node.tabIndex = -1;
      node.setAttribute('aria-atomic', 'true');
      host.append(node);
    }
    node.classList.toggle('is-error', error);
    node.setAttribute('role', error ? 'alert' : 'status');
    node.textContent = message;
    return node;
  }

  function close(restoreFocus = true) {
    if (!active || active.pending) return;
    const previous = active;
    active = null;
    previous.form.remove();
    previous.host.classList.remove('has-inline-action', 'is-editing');
    if (previous.actions) previous.actions.hidden = false;
    if (previous.copy) previous.copy.hidden = false;
    previous.trigger?.setAttribute('aria-expanded', 'false');
    previous.trigger?.removeAttribute('aria-controls');
    if (restoreFocus && previous.trigger?.isConnected) previous.trigger.focus({preventScroll: true});
  }

  function requireValue(field, message, maxLength) {
    const value = field.value.trim();
    if (!value || (maxLength && value.length > maxLength)) {
      const error = new Error(message);
      error.field = field;
      throw error;
    }
    return value;
  }

  function canLeave() {
    if (active && !active.host.isConnected) active = null;
    if (active) {
      active.error.hidden = false;
      active.error.textContent = 'Save or cancel this action before starting another.';
      active.error.focus({preventScroll: false});
      return false;
    }
    return true;
  }

  function open({host, trigger, title, content = '', submitLabel, busyLabel, destructive = false, editing = false, submit, success}) {
    if (!canLeave()) return null;
    const id = `inline-action-${++sequence}`;
    const form = document.createElement('form');
    form.className = 'inline-action-panel';
    form.id = id;
    form.noValidate = true;
    form.setAttribute('aria-labelledby', id + '-title');
    form.innerHTML = `<h4 id="${id}-title">${escape(title)}</h4>${content.replaceAll('__ACTION_ID__', id)}
      <p class="inline-action-error" id="${id}-error" role="alert" tabindex="-1" hidden></p>
      <div class="inline-action-buttons"><button type="button" class="secondary-btn" data-inline-cancel>${destructive ? 'Keep it' : 'Cancel'}</button><button type="submit" class="${destructive ? 'inline-danger-button' : 'inline-primary-button'}">${escape(submitLabel)}</button></div>`;
    const actions = host.querySelector(':scope > .content-actions, :scope > .admin-row-actions');
    const copy = editing ? host.querySelector(':scope > .post-copy') : null;
    const error = form.querySelector('.inline-action-error');
    active = {host, trigger, form, actions, copy, error, pending: false};
    host.querySelector(':scope > .inline-status')?.remove();
    host.classList.add('has-inline-action');
    if (editing) host.classList.add('is-editing');
    if (actions) actions.hidden = true;
    if (copy) copy.hidden = true;
    trigger?.setAttribute('aria-expanded', 'true');
    trigger?.setAttribute('aria-controls', id);
    host.append(form);
    form.querySelector('[data-inline-cancel]').addEventListener('click', () => close());
    form.addEventListener('keydown', event => {
      if (event.key === 'Escape') { event.preventDefault(); close(); }
      if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); if (!active?.pending) form.requestSubmit(); }
    });
    form.addEventListener('input', event => event.target.removeAttribute('aria-invalid'));
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (!active || active.pending) return;
      const current = active;
      const controls = [...form.elements];
      const before = controls.map(control => control.disabled);
      const button = form.querySelector('[type="submit"]');
      error.hidden = true;
      try {
        // Validate/capture synchronously before disabling fields.
        const operation = submit(form);
        current.pending = true;
        form.setAttribute('aria-busy', 'true');
        controls.forEach(control => { control.disabled = true; });
        button.textContent = busyLabel || 'Saving…';
        const result = await operation;
        current.pending = false;
        close(false);
        try { await success?.(result); }
        catch (_) { notice(host, 'Your change was saved, but the view could not refresh. Reload to see the latest version.'); }
      } catch (failure) {
        current.pending = false;
        error.textContent = failure.message || 'This action could not finish. Your input is still here; try again.';
        error.hidden = false;
        if (failure.status === 409) error.textContent += ' Your draft is kept here. Copy it before reloading the latest post.';
        if (failure.field) {
          failure.field.setAttribute('aria-invalid', 'true');
          failure.field.setAttribute('aria-describedby', error.id);
        }
        controls.forEach((control, i) => { control.disabled = before[i]; });
        (failure.field || error).focus({preventScroll: false});
      } finally {
        controls.forEach((control, i) => { control.disabled = before[i]; });
        form.removeAttribute('aria-busy');
        button.textContent = submitLabel;
      }
    });
    (destructive ? form.querySelector('[data-inline-cancel]') : form.querySelector('input, textarea, select') || form.querySelector('[data-inline-cancel]')).focus({preventScroll: true});
    return form;
  }

  async function run(button, host, task, busyLabel = 'Saving…') {
    if (button.disabled) return;
    const actions = button.closest('.content-actions, .admin-row-actions');
    const controls = actions ? [...actions.querySelectorAll('button')] : [button];
    const before = controls.map(control => control.disabled);
    const label = button.textContent;
    controls.forEach(control => { control.disabled = true; });
    button.textContent = busyLabel;
    try { await task(); }
    catch (error) { notice(host, error.message || 'This action could not finish. Try again.', true); }
    finally { controls.forEach((control, i) => { control.disabled = before[i]; }); button.textContent = label; }
  }

  window.InlineActions = {open, close, notice, requireValue, run, canLeave, isOpen: () => Boolean(active)};
})();
