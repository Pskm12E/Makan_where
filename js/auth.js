function requireLoginForFavourite() {
  if (currentUser) return true;
  let bubble = document.getElementById('loginBubble');
  if (!bubble) {
    bubble = document.createElement('div');
    bubble.id = 'loginBubble';
    bubble.className = 'login-bubble';
    bubble.setAttribute('role', 'status');
    bubble.innerHTML = '<span>Log in to save favourites and contribute.</span><a href="auth.html?mode=login">Go to login</a><button type="button" aria-label="Close notification">×</button>';
    bubble.querySelector('button').addEventListener('click', () => bubble.classList.remove('visible'));
    document.body.appendChild(bubble);
  }
  bubble.classList.add('visible');
  return false;
}

async function logoutUser(event) {
  await withAction(event?.currentTarget, async () => {
    await api('/logout', {method:'POST'});
    location.href = 'auth.html?mode=login&message=logged-out';
  });
}

function updateAuthActions() {
  const container = document.getElementById('authActions');
  document.querySelectorAll('a[href="admin.html"]').forEach(link => { link.hidden = currentUser?.role !== 'admin'; });
  if (!container) return;
  container.innerHTML = currentUser
    ? `<span class="nav-user">Hi, ${escapeHtml(currentUser.fullName.split(' ')[0])}</span><a class="nav-account" href="settings.html">Settings</a><button class="nav-logout" id="navLogout" type="button">Log out</button>`
    : '<a class="nav-login" href="auth.html">Log in</a>';
  document.getElementById('navLogout')?.addEventListener('click', logoutUser);
}

function notice(id, message, type = 'error') {
  const element = document.getElementById(id);
  if (!element) return;
  element.textContent = message;
  element.className = `form-notice ${type}`;
}

function switchAuthMode(mode) {
  const login = document.getElementById('loginForm');
  const register = document.getElementById('registerForm');
  if (!login || !register) return;
  if (['admin.html', 'database-lab.html'].includes(new URLSearchParams(location.search).get('next'))) {
    login.hidden = false;
    register.hidden = true;
    document.title = 'Administrator sign-in - MakanWhereSG';
    login.querySelector('.eyebrow').textContent = 'Administrator access';
    login.querySelector('h2').textContent = 'Manage Makan Where';
    login.querySelector('.form-help').textContent = 'Sign in with your administrator account to manage the catalogue, moderation and database schema.';
    login.querySelector('button').textContent = 'Sign in to dashboard';
    document.getElementById('authSwitch').innerHTML = '<a href="auth.html">Back to user sign-in</a>';
    document.getElementById('adminLoginLink').hidden = true;
    return;
  }
  login.hidden = mode !== 'login';
  register.hidden = mode === 'login';
  document.getElementById('authSwitch').innerHTML = mode === 'login'
    ? 'New to MakanWhereSG? <a href="auth.html?mode=register">Create an account</a>'
    : 'Already have an account? <a href="auth.html?mode=login">Log in</a>';
}

function attachAuthForms() {
  for (const mode of ['login', 'register']) {
    const form = document.getElementById(`${mode}Form`);
    if (!form) continue;
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true;
      try {
        let body;
        if (mode === 'login') {
          body = {identity: document.getElementById('loginIdentity').value.trim(), password: document.getElementById('loginPassword').value};
          body.adminOnly = ['admin.html', 'database-lab.html'].includes(new URLSearchParams(location.search).get('next'));
        } else {
          const password = document.getElementById('registerPassword').value;
          if (password !== document.getElementById('registerConfirm').value) throw new Error('Your passwords do not match.');
          body = {fullName: document.getElementById('registerName').value.trim(), username: document.getElementById('registerUsername').value.trim(), email: document.getElementById('registerEmail').value.trim(), phone: document.getElementById('registerPhone').value.trim(), password};
        }
        await api(`/${mode}`, {method:'POST', body});
        location.href = body.adminOnly ? new URLSearchParams(location.search).get('next') : 'index.html';
      } catch (error) { notice('authNotice', error.message); }
      finally { button.disabled = false; }
    });
  }
}

function updateSettingsSummary() {
  document.getElementById('settingsSummaryName').textContent = currentUser.fullName;
  document.getElementById('settingsSummaryEmail').textContent = currentUser.email;
  document.getElementById('settingsAvatar').textContent = currentUser.fullName.charAt(0).toUpperCase();
  document.getElementById('settingsMemberSince').textContent = new Date(currentUser.createdAt).toLocaleDateString('en-SG', {month:'short',year:'numeric'});
}

function attachSettingsForm() {
  const form = document.getElementById('settingsForm');
  if (!form) return;
  if (!currentUser) { location.href = 'auth.html?mode=login&message=login-required'; return; }
  for (const [field, key] of Object.entries({Name:'fullName', Username:'username', Email:'email', Phone:'phone'})) {
    document.getElementById(`settings${field}`).value = currentUser[key];
  }
  updateSettingsSummary();
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      const body = {};
      for (const [field, key] of Object.entries({Name:'fullName', Username:'username', Email:'email', Phone:'phone'})) body[key] = document.getElementById(`settings${field}`).value.trim();
      const result = await api('/profile', {method:'PATCH', body});
      currentUser = result.user;
      updateSettingsSummary();
      updateAuthActions();
      notice('settingsNotice', 'Profile saved successfully.', 'success');
    } catch (error) { notice('settingsNotice', error.message); }
    finally { button.disabled = false; }
  });
  document.getElementById('logoutButton').addEventListener('click', logoutUser);
}

document.addEventListener('DOMContentLoaded', async () => {
  const params = new URLSearchParams(location.search);
  switchAuthMode(params.get('mode') === 'register' ? 'register' : 'login');
  if (!await appReady) return;
  updateAuthActions();
  attachAuthForms();
  attachSettingsForm();
  if (params.get('message') === 'login-required') notice('authNotice', 'Please log in to open your settings.');
  if (params.get('message') === 'logged-out') notice('authNotice', 'You have been logged out.', 'success');
});
