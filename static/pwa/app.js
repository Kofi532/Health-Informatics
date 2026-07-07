const API_BASE = '/api';
const tokenKey = 'mhealth_token';

async function request(path, options = {}) {
  const token = localStorage.getItem(tokenKey);
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'same-origin',
    ...options,
    headers,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || res.statusText);
  }
  return res.json();
}

function setAppHtml(html) {
  const el = document.getElementById('app');
  el.innerHTML = html;
}

function isAuthenticated() {
  return !!localStorage.getItem(tokenKey);
}

function renderLogin() {
  setAppHtml(`
    <div>
      <h2>Sign in</h2>
      <div class="error" id="error" style="display:none"></div>
      <label for="username">Username</label>
      <input id="username" type="text" placeholder="Username" autocomplete="username">
      <label for="password">Password</label>
      <input id="password" type="password" placeholder="Password" autocomplete="current-password">
      <button id="loginButton">Login</button>
      <p>Use your username and password to sign in and access the directory.</p>
      <p>No account yet? <a href="/signup/">Create one now</a>.</p>
    </div>
  `);

  document.getElementById('loginButton').addEventListener('click', async () => {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const errorEl = document.getElementById('error');
    errorEl.style.display = 'none';

    try {
      const data = await fetch(`${API_BASE}/token/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      }).then(async (res) => {
        if (!res.ok) {
          const json = await res.json().catch(() => ({}));
          throw new Error(json.detail || 'Login failed');
        }
        return res.json();
      });
      localStorage.setItem(tokenKey, data.access);
      renderApp();
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.style.display = 'block';
    }
  });
}

function renderPatientCard(patient) {
  return `
    <div class="patient-card">
      <h2>${patient.first_name} ${patient.last_name}</h2>
      <p><strong>DOB:</strong> ${patient.date_of_birth}</p>
      <p><strong>Gender:</strong> ${patient.gender}</p>
      <p><strong>Email:</strong> ${patient.email || '—'}</p>
      <p><strong>Phone:</strong> ${patient.phone_number || '—'}</p>
      <p><strong>Address:</strong> ${patient.address || '—'}</p>
      <p><strong>Emergency:</strong> ${patient.emergency_contact || '—'}</p>
    </div>
  `;
}

function renderPatients(data, query, page, pageSize) {
  const patients = data.results || [];
  const prevLink = data.previous;
  const nextLink = data.next;

  setAppHtml(`
    <div>
      <div class="meta">
        <div class="search-row">
          <input id="searchQuery" type="text" value="${query}" placeholder="Search patients by name, email, phone, address">
          <button id="searchButton">Search</button>
        </div>
        <div>
          <span>${data.count} patients found</span>
        </div>
      </div>
      <div class="patient-list">
        ${patients.map(renderPatientCard).join('')}
      </div>
      <div class="pagination">
        <button id="prevButton" ${prevLink ? '' : 'disabled'} class="small-button">Previous</button>
        <button id="nextButton" ${nextLink ? '' : 'disabled'} class="small-button">Next</button>
        <span>Page ${page}</span>
      </div>
    </div>
  `);

  document.getElementById('searchButton').addEventListener('click', () => {
    loadPatients(document.getElementById('searchQuery').value.trim(), 1, pageSize);
  });
  document.getElementById('prevButton').addEventListener('click', () => {
    if (prevLink) {
      loadPatients(query, page - 1, pageSize);
    }
  });
  document.getElementById('nextButton').addEventListener('click', () => {
    if (nextLink) {
      loadPatients(query, page + 1, pageSize);
    }
  });
}

async function loadPatients(query = '', page = 1, pageSize = 20) {
  try {
    setAppHtml('<p>Loading patients...</p>');
    const params = new URLSearchParams();
    if (query) params.set('q', query);
    params.set('page', String(page));
    params.set('page_size', String(pageSize));

    const data = await request(`/patients/?${params.toString()}`);
    renderPatients(data, query, page, pageSize);
  } catch (err) {
    const message = err.message || 'An unexpected error occurred.';
    setAppHtml(`<div class="error">${message}</div>`);
  }
}

async function fetchCurrentUser() {
  return request('/me/');
}

function setUserInfo(user) {
  const userInfo = document.getElementById('userInfo');
  if (!userInfo) return;
  if (!user || !user.username) {
    userInfo.textContent = '';
    return;
  }
  const name = user.first_name || user.last_name ? `${user.first_name} ${user.last_name}`.trim() : user.username;
  userInfo.textContent = `Signed in as ${name}`;
}

async function renderApp() {
  const logoutButton = document.getElementById('logoutButton');
  const authenticated = isAuthenticated();
  logoutButton.hidden = !authenticated;

  if (!logoutButton.dataset.bound) {
    logoutButton.addEventListener('click', () => {
      localStorage.removeItem(tokenKey);
      setUserInfo(null);
      renderApp();
    });
    logoutButton.dataset.bound = 'true';
  }

  if (!authenticated) {
    setUserInfo(null);
    renderLogin();
    return;
  }

  try {
    const user = await fetchCurrentUser();
    setUserInfo(user);
  } catch (err) {
    localStorage.removeItem(tokenKey);
    setUserInfo(null);
    renderLogin();
    return;
  }

  loadPatients('', 1, 20);
}

async function init() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/pwa/service-worker.js')
      .then(() => console.log('Service worker registered'))
      .catch(console.error);
  }

  if (!isAuthenticated()) {
    renderLogin();
    return;
  }

  renderApp();
}

init();
