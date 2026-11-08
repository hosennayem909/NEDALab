/**
 * Online Learning UI — NEDA Lab
 */

const API_BASE = 'http://127.0.0.1:8000';
let activeSession = null;
let datasetsCache = [];
let currentColumns = { all: [], numeric: [], date: [] };

// ---------- Auth ----------
function getToken() {
  return (
    localStorage.getItem('access_token') ||
    localStorage.getItem('token') ||
    sessionStorage.getItem('access_token') ||
    sessionStorage.getItem('token') ||
    ''
  );
}

function authHeaders() {
  const token = getToken();
  return token
    ? { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' };
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers || {}) },
  });

  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { detail: text }; }

  if (!res.ok) {
    const msg = (data && (data.detail || data.message)) || `HTTP ${res.status}`;
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return data;
}

// ---------- UI Helpers ----------
function showAlert(message, type = 'info') {
  const el = document.getElementById('alert');
  el.textContent = message;
  el.className = `alert alert-${type} show`;
  if (type === 'success' || type === 'info') {
    setTimeout(() => el.classList.remove('show'), 4000);
  }
}

function hideAlert() {
  document.getElementById('alert').classList.remove('show');
}

// ---------- Load Datasets ----------
async function loadDatasets() {
  try {
    const data = await apiFetch('/api/data/datasets');
    datasetsCache = data.datasets || data || [];

    const sel = document.getElementById('dataset');
    sel.innerHTML = '<option value="">— Select a dataset —</option>' +
      datasetsCache.map(d =>
        `<option value="${d.id}">${d.filename || d.name} (${d.row_count || '?'} rows)</option>`
      ).join('');
  } catch (e) {
    showAlert(`Failed to load datasets: ${e.message}`, 'error');
  }
}

// ---------- Load Columns ----------
async function loadColumns(datasetId) {
  if (!datasetId) {
    resetColumnSelectors();
    return;
  }

  try {
    const cols = await apiFetch(`/api/data/datasets/${datasetId}/column-info`);
    currentColumns = {
      all: cols.all_columns || [],
      numeric: cols.numeric_columns || [],
      date: cols.date_columns || [],
    };

    // Target dropdown — numeric columns only
    const tgt = document.getElementById('target');
    tgt.innerHTML = '<option value="">— Select target —</option>' +
      currentColumns.numeric.map(c => `<option value="${c}">${c}</option>`).join('');

    // Features checkboxes — numeric columns only
    const featDiv = document.getElementById('features');
    if (currentColumns.numeric.length === 0) {
      featDiv.innerHTML = '<div class="empty">No numeric columns in this dataset</div>';
    } else {
      featDiv.innerHTML = currentColumns.numeric.map(c => `
        <label class="checkbox-item">
          <input type="checkbox" value="${c}">
          <span>${c}</span>
        </label>
      `).join('');
      // add click handler for style
      featDiv.querySelectorAll('.checkbox-item').forEach(item => {
        const cb = item.querySelector('input');
        cb.addEventListener('change', () => {
          item.classList.toggle('checked', cb.checked);
        });
      });
    }
  } catch (e) {
    showAlert(`Failed to load columns: ${e.message}`, 'error');
    resetColumnSelectors();
  }
}

function resetColumnSelectors() {
  document.getElementById('target').innerHTML = '<option value="">— Select target —</option>';
  document.getElementById('features').innerHTML = '<div class="empty">Select a dataset first</div>';
  currentColumns = { all: [], numeric: [], date: [] };
}

function getSelectedFeatures() {
  const cbs = document.querySelectorAll('#features input[type="checkbox"]:checked');
  return Array.from(cbs).map(cb => cb.value);
}

// ---------- Init Session ----------
async function initSession() {
  hideAlert();

  const datasetId = parseInt(document.getElementById('dataset').value);
  const target = document.getElementById('target').value;
  const features = getSelectedFeatures();
  const task = document.getElementById('task').value;
  const model = document.getElementById('model').value;

  if (!datasetId) return showAlert('Select a dataset', 'error');
  if (!target) return showAlert('Select a target column', 'error');
  if (features.length === 0) return showAlert('Select at least one feature', 'error');
  if (features.includes(target)) return showAlert('Target cannot also be a feature', 'error');

  const btn = document.getElementById('btn-init');
  btn.disabled = true;
  btn.textContent = '⏳ Creating...';

  try {
    const payload = {
      dataset_id: datasetId,
      target: target,
      features: features,
      task: task,
      model: model,
    };

    const res = await apiFetch('/api/ml/online/init', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    activeSession = res;
    showAlert(`✅ Session created: ${res.session_id}`, 'success');
    renderActiveSession();
    await loadSessions();
  } catch (e) {
    showAlert(`Failed: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '✨ Create Session';
  }
}

// ---------- Render Active Session ----------
function renderActiveSession() {
  if (!activeSession) {
    document.getElementById('session-card').style.display = 'none';
    return;
  }

  document.getElementById('session-card').style.display = 'block';
  document.getElementById('session-badge').textContent = activeSession.session_id;
  document.getElementById('session-info').textContent =
    `Session: ${activeSession.session_id}\n` +
    `Target:  ${activeSession.target}\n` +
    `Features: ${(activeSession.features || []).join(', ')}\n` +
    `Task:     ${activeSession.task}  |  Model: ${activeSession.model_name}`;

  document.getElementById('stat-n').textContent = activeSession.n_samples_seen || 0;
  document.getElementById('stat-metric-name').textContent = activeSession.metric_name || 'R2';
  document.getElementById('stat-metric').textContent =
    activeSession.metric_value != null ? Number(activeSession.metric_value).toFixed(4) : '-';
  document.getElementById('stat-rolling').textContent =
    activeSession.rolling_metric != null ? Number(activeSession.rolling_metric).toFixed(4) : '-';

  // Build step-features inputs
  const stepDiv = document.getElementById('step-features');
  stepDiv.innerHTML = activeSession.features.map(f => `
    <div class="field">
      <label>${f}</label>
      <input type="number" class="step-feat" data-feature="${f}" step="any" placeholder="0">
    </div>
  `).join('');
}

// ---------- Train from Dataset ----------
async function trainFromDataset() {
  if (!activeSession) return;
  const btn = document.getElementById('btn-train-dataset');
  btn.disabled = true;
  btn.textContent = '⏳ Training...';

  try {
    const payload = {
      dataset_id: activeSession.dataset_id,
      target: activeSession.target,
      features: activeSession.features,
      task: activeSession.task,
      model: activeSession.model_name,
    };

    const res = await apiFetch('/api/ml/online/train-from-dataset', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    // New session was created on backend (train-from-dataset creates one)
    activeSession = {
      ...activeSession,
      ...res,
    };

    showAlert(`✅ Trained on ${res.trained_rows} rows — R²: ${res.final_metric}`, 'success');
    renderActiveSession();
    await loadSessions();
  } catch (e) {
    showAlert(`Training failed: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '🚀 Train from Dataset';
  }
}

// ---------- Send One Sample ----------
async function sendStep() {
  if (!activeSession) return;

  const featureInputs = document.querySelectorAll('.step-feat');
  const x = {};
  for (const inp of featureInputs) {
    const val = inp.value;
    if (val === '' || isNaN(Number(val))) {
      return showAlert(`Enter a value for "${inp.dataset.feature}"`, 'error');
    }
    x[inp.dataset.feature] = Number(val);
  }

  const yRaw = document.getElementById('step-y').value;
  const y = yRaw === '' ? null : Number(yRaw);
  const learn = document.getElementById('step-learn').checked;

  try {
    const res = await apiFetch('/api/ml/online/step', {
      method: 'POST',
      body: JSON.stringify({
        session_id: activeSession.session_id,
        x: x,
        y: y,
        learn: learn,
      }),
    });

    // Update stats
    activeSession.n_samples_seen = res.n_samples_seen;
    activeSession.metric_value = res.metric_value;
    activeSession.rolling_metric = res.rolling_metric;

    // Show prediction
    if (res.prediction != null) {
      document.getElementById('prediction-box').style.display = 'block';
      document.getElementById('prediction-value').textContent =
        Number(res.prediction).toFixed(4);
    }

    renderActiveSession();
    showAlert(`✅ ${res.learned ? 'Learned + ' : ''}Predicted: ${res.prediction}`, 'success');
    await loadSessions();
  } catch (e) {
    showAlert(`Step failed: ${e.message}`, 'error');
  }
}

// ---------- Sessions List ----------
async function loadSessions() {
  try {
    const data = await apiFetch('/api/ml/online/sessions');
    const sessions = data.sessions || [];

    const tbody = document.querySelector('#sessions-table tbody');
    if (sessions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty">No sessions yet.</td></tr>';
      return;
    }

    tbody.innerHTML = sessions.map(s => `
      <tr>
        <td><code>${s.session_id}</code></td>
        <td>${s.model_name}</td>
        <td>${s.task}</td>
        <td>${s.n_samples_seen}</td>
        <td>${s.metric_value != null ? Number(s.metric_value).toFixed(4) : '-'}</td>
        <td>
          <button class="btn btn-secondary btn-sm" data-act="load" data-sid="${s.session_id}">Load</button>
          <button class="btn btn-danger btn-sm" data-act="del" data-sid="${s.session_id}">Delete</button>
        </td>
      </tr>
    `).join('');

    // Bind actions
    tbody.querySelectorAll('button[data-act]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const sid = btn.dataset.sid;
        const act = btn.dataset.act;
        if (act === 'load') {
          const target = sessions.find(x => x.session_id === sid);
          if (target) {
            activeSession = target;
            renderActiveSession();
            showAlert(`Loaded session ${sid}`, 'info');
          }
        } else if (act === 'del') {
          if (!confirm(`Delete session ${sid}?`)) return;
          try {
            await apiFetch(`/api/ml/online/session/${sid}`, { method: 'DELETE' });
            if (activeSession && activeSession.session_id === sid) activeSession = null;
            renderActiveSession();
            await loadSessions();
            showAlert(`Deleted session ${sid}`, 'success');
          } catch (e) {
            showAlert(`Delete failed: ${e.message}`, 'error');
          }
        }
      });
    });
  } catch (e) {
    // silent
  }
}

// ---------- Save Session ----------
async function saveSession() {
  if (!activeSession) return;
  try {
    const res = await apiFetch(`/api/ml/online/session/${activeSession.session_id}/save`, {
      method: 'POST',
    });
    showAlert(`💾 Saved: ${res.path}`, 'success');
  } catch (e) {
    showAlert(`Save failed: ${e.message}`, 'error');
  }
}

// ---------- Delete Active Session ----------
async function deleteActiveSession() {
  if (!activeSession) return;
  if (!confirm(`Delete session ${activeSession.session_id}?`)) return;
  try {
    await apiFetch(`/api/ml/online/session/${activeSession.session_id}`, { method: 'DELETE' });
    activeSession = null;
    renderActiveSession();
    await loadSessions();
    showAlert('Session deleted', 'success');
  } catch (e) {
    showAlert(`Delete failed: ${e.message}`, 'error');
  }
}

// ---------- Bind Events ----------
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('dataset').addEventListener('change', e => {
    loadColumns(e.target.value);
  });

  document.getElementById('btn-init').addEventListener('click', initSession);
  document.getElementById('btn-refresh-sessions').addEventListener('click', loadSessions);
  document.getElementById('btn-train-dataset').addEventListener('click', trainFromDataset);
  document.getElementById('btn-step').addEventListener('click', sendStep);
  document.getElementById('btn-save-session').addEventListener('click', saveSession);
  document.getElementById('btn-delete-session').addEventListener('click', deleteActiveSession);

  loadDatasets();
  loadSessions();
});