const authUsersKey = 'makanwheresg-users';
const authSessionKey = 'makanwheresg-session';

function getUsers() {
  return JSON.parse(localStorage.getItem(authUsersKey) || '[]');
}

function saveUsers(users) {
  localStorage.setItem(authUsersKey, JSON.stringify(users));
}

function getCurrentUser() {
  const sessionUsername = localStorage.getItem(authSessionKey);
  return getUsers().find(user => user.username === sessionUsername) || null;
}

function setCurrentUser(user) {
  localStorage.setItem(authSessionKey, user.username);
}

function logoutUser() {
  localStorage.removeItem(authSessionKey);
  window.location.href = 'auth.html?mode=login&message=logged-out';
}

function updateAuthActions() {
  const container = document.getElementById('authActions');
  if (!container) return;

  const user = getCurrentUser();
  if (user) {
    container.innerHTML = `
      <span class="nav-user">Hi, ${escapeHtml(user.fullName.split(' ')[0])}</span>
      <a class="nav-account" href="settings.html">Settings</a>
      <button class="nav-logout" id="navLogout" type="button">Log out</button>
    `;
    document.getElementById('navLogout').addEventListener('click', logoutUser);
  } else {
    container.innerHTML = '<a class="nav-login" href="auth.html">Log in</a>';
  }
}

function escapeHtml(value) {
  return value.replace(/[&<>'"]/g, character => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;'
  }[character]));
}

function showAuthNotice(message, type = 'error') {
  const notice = document.getElementById('authNotice');
  if (!notice) return;
  notice.textContent = message;
  notice.className = `form-notice ${type}`;
}

function switchAuthMode(mode) {
  const loginForm = document.getElementById('loginForm');
  const registerForm = document.getElementById('registerForm');
  const authSwitch = document.getElementById('authSwitch');
  if (!loginForm || !registerForm) return;

  const isLogin = mode === 'login';
  loginForm.hidden = !isLogin;
  registerForm.hidden = isLogin;

  if (authSwitch) {
    authSwitch.innerHTML = isLogin
      ? 'New to MakanWhereSG? <a href="auth.html?mode=register">Create an account</a>'
      : 'Already have an account? <a href="auth.html?mode=login">Log in</a>';
  }

  showAuthNotice('');
}

function attachAuthForms() {
  const loginForm = document.getElementById('loginForm');
  const registerForm = document.getElementById('registerForm');
  if (!loginForm || !registerForm) return;

  loginForm.addEventListener('submit', event => {
    event.preventDefault();
    const identity = document.getElementById('loginIdentity').value.trim().toLowerCase();
    const password = document.getElementById('loginPassword').value;
    const user = getUsers().find(item =>
      item.username.toLowerCase() === identity || item.email.toLowerCase() === identity
    );

    if (!user || user.password !== password) {
      showAuthNotice('We could not match those details. Check your email or username and password.');
      return;
    }

    setCurrentUser(user);
    window.location.href = 'index.html';
  });

  registerForm.addEventListener('submit', event => {
    event.preventDefault();
    const fullName = document.getElementById('registerName').value.trim();
    const username = document.getElementById('registerUsername').value.trim();
    const email = document.getElementById('registerEmail').value.trim().toLowerCase();
    const phone = document.getElementById('registerPhone').value.trim();
    const password = document.getElementById('registerPassword').value;
    const confirmation = document.getElementById('registerConfirm').value;
    const users = getUsers();

    if (!email.endsWith('@gmail.com')) {
      showAuthNotice('Please use a valid Gmail address ending in @gmail.com.');
      return;
    }

    if (!/^\+?[0-9 ()-]{8,18}$/.test(phone)) {
      showAuthNotice('Please enter a valid phone number.');
      return;
    }

    if (password !== confirmation) {
      showAuthNotice('Your passwords do not match.');
      return;
    }

    if (users.some(user => user.username.toLowerCase() === username.toLowerCase())) {
      showAuthNotice('That username is already taken.');
      return;
    }

    if (users.some(user => user.email === email)) {
      showAuthNotice('An account with that Gmail address already exists.');
      return;
    }

    const user = {
      fullName,
      username,
      email,
      phone,
      password,
      createdAt: new Date().toISOString()
    };

    users.push(user);
    saveUsers(users);
    setCurrentUser(user);
    window.location.href = 'index.html';
  });
}

function attachSettingsForm() {
  const form = document.getElementById('settingsForm');
  if (!form) return;

  const user = getCurrentUser();
  if (!user) {
    window.location.href = 'auth.html?mode=login&message=login-required';
    return;
  }

  document.getElementById('settingsName').value = user.fullName;
  document.getElementById('settingsUsername').value = user.username;
  document.getElementById('settingsEmail').value = user.email;
  document.getElementById('settingsPhone').value = user.phone;
  document.getElementById('settingsSummaryName').textContent = user.fullName;
  document.getElementById('settingsSummaryEmail').textContent = user.email;
  document.getElementById('settingsAvatar').textContent = user.fullName.charAt(0).toUpperCase();
  document.getElementById('settingsMemberSince').textContent = new Date(user.createdAt).toLocaleDateString('en-SG', {
    month: 'short',
    year: 'numeric'
  });

  form.addEventListener('submit', event => {
    event.preventDefault();
    const fullName = document.getElementById('settingsName').value.trim();
    const username = document.getElementById('settingsUsername').value.trim();
    const email = document.getElementById('settingsEmail').value.trim().toLowerCase();
    const phone = document.getElementById('settingsPhone').value.trim();
    const users = getUsers();

    if (!email.endsWith('@gmail.com')) {
      showSettingsNotice('Please use a valid Gmail address ending in @gmail.com.');
      return;
    }

    if (!/^\+?[0-9 ()-]{8,18}$/.test(phone)) {
      showSettingsNotice('Please enter a valid phone number.');
      return;
    }

    const duplicate = users.some(item => item.username !== user.username && (
      item.username.toLowerCase() === username.toLowerCase() || item.email === email
    ));
    if (duplicate) {
      showSettingsNotice('That username or Gmail address is already in use.');
      return;
    }

    const updatedUser = { ...user, fullName, username, email, phone };
    const updatedUsers = users.map(item => item.username === user.username ? updatedUser : item);
    saveUsers(updatedUsers);
    setCurrentUser(updatedUser);
    document.getElementById('settingsSummaryName').textContent = fullName;
    document.getElementById('settingsSummaryEmail').textContent = email;
    document.getElementById('settingsAvatar').textContent = fullName.charAt(0).toUpperCase();
    showSettingsNotice('Profile saved successfully.', 'success');
  });

  document.getElementById('logoutButton').addEventListener('click', logoutUser);
}

function showSettingsNotice(message, type = 'error') {
  const notice = document.getElementById('settingsNotice');
  notice.textContent = message;
  notice.className = `form-notice ${type}`;
}

document.addEventListener('DOMContentLoaded', () => {
  updateAuthActions();
  attachAuthForms();
  attachSettingsForm();

  const params = new URLSearchParams(window.location.search);
  if (document.getElementById('loginForm')) {
    const mode = params.get('mode') === 'register' ? 'register' : 'login';
    switchAuthMode(mode);
    if (params.get('message') === 'login-required') {
      showAuthNotice('Please log in to open your settings.');
    }
    if (params.get('message') === 'logged-out') {
      showAuthNotice('You have been logged out.', 'success');
    }
  }
});
