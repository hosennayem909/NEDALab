requireAuth();
renderSidebar("automl");

let activeTab = "run";
let currentDatasetId = null;
let allAlgorithms = { classification: [], regression: [] };

document.querySelectorAll(".am-tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".am-tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeTab = btn.dataset.tab;
    document.getElementById("result").innerHTML = "";
    renderTab();
  });
});

function renderTab() {
  const box = document.getElementById("tabContent");
  if (activeTab === "run") renderRun(box);
  else if (activeTab === "history") renderHistory(box);
  else if (activeTab === "api") renderAPI(box);
  else if (activeTab === "drift") renderDrift(box);
}

// ============ TAB 1: AutoML Run ============
async function renderRun(box) {
  box.innerHTML = `
    <div class="card p-6">
      <h2 class="font-semibold text-stone-900 mb-4">Configure AutoML</h2>
      <div class="grid grid-cols-3 gap-4 mb-4">
        <div class="col-span-2">
          <label class="label">Dataset</label>
          <select id="dsSelect" class="input"><option value="">Loading...</option></select>
        </div>
        <div>
          <label class="label">Task type</label>
          <select id="taskType" class="input">
            <option value="auto">Auto detect</option>
            <option value="classification">Classification</option>
            <option value="regression">Regression</option>
          </select>
        </div>
      </div>
      <div class="grid grid-cols-3 gap-4 mb-4">
        <div>
          <label class="label">Target column</label>
          <select id="targetSel" class="input" disabled><option value="">—</option></select>
        </div>
        <div>
          <label class="label">Max models</label>
          <input id="maxModels" type="number" min="3" max="10" value="8" class="input" />
        </div>
        <div>
          <label class="label">Test size</label>
          <input id="testSize" type="number" step="0.05" min="0.1" max="0.5" value="0.2" class="input" />
        </div>
      </div>
      <div class="mb-4">
        <label class="label">Features (X)</label>
        <div id="featureList" class="border rounded-md p-2 max-h-40 overflow-y-auto flex flex-wrap gap-3" style="border-color:#e7e5e4">
          <p class="text-xs text-stone-500">Select dataset first</p>
        </div>
      </div>
      <button id="runAutomlBtn" class="btn-primary">✨ Run AutoML</button>
      <p class="text-xs text-stone-500 mt-2">AutoML trains 7-8 models. Expect 5-15 minutes on CPU.</p>
    </div>
  `;

  // Load datasets
  try {
    const data = await apiFetch("/api/data/datasets");
    document.getElementById("dsSelect").innerHTML = '<option value="">— Select dataset —</option>' +
      data.map(d => `<option value="${d.id}">${esc(d.filename)} (${d.row_count} rows)</option>`).join("");
  } catch (e) {}

  document.getElementById("dsSelect").addEventListener("change", async () => {
    const id = document.getElementById("dsSelect").value;
    if (!id) return;
    currentDatasetId = parseInt(id);
    try {
      const info = await apiFetch("/api/data/datasets/" + currentDatasetId + "/column-info");
      const tgt = document.getElementById("targetSel");
      tgt.disabled = false;
      tgt.innerHTML = '<option value="">— Select —</option>' +
        info.all_columns.map(c => `<option value="${c}">${esc(c)}</option>`).join("");
      const fl = document.getElementById("featureList");
      fl.innerHTML = info.all_columns.map(c => `
        <label class="flex items-center gap-1.5 text-sm cursor-pointer">
          <input type="checkbox" class="feat-check" value="${esc(c)}" style="accent-color:#047857" />
          <span class="text-stone-700">${esc(c)}</span>
        </label>
      `).join("");
    } catch (e) { toast(e.message, "error"); }
  });

  document.getElementById("runAutomlBtn").addEventListener("click", runAutoML);
}

async function runAutoML() {
  const target = document.getElementById("targetSel").value;
  const features = Array.from(document.querySelectorAll(".feat-check:checked")).map(c => c.value);
  if (!currentDatasetId) { toast("Select dataset", "warning"); return; }
  if (!target) { toast("Select target", "warning"); return; }
  if (!features.length) { toast("Select features", "warning"); return; }
  if (features.includes(target)) { toast("Target cannot be in features", "warning"); return; }

  document.getElementById("result").innerHTML = "";
  document.getElementById("loading").style.display = "block";

  try {
    const res = await apiFetch("/api/automl/run", {
      method: "POST",
      body: {
        dataset_id: currentDatasetId,
        target_column: target,
        feature_columns: features,
        task_type: document.getElementById("taskType").value,
        test_size: parseFloat(document.getElementById("testSize").value) || 0.2,
        max_models: parseInt(document.getElementById("maxModels").value) || 8,
      },
    });
    document.getElementById("loading").style.display = "none";
    renderAutoMLResult(res);
    toast("AutoML completed · " + res.total_successful + "/" + res.total_models_tested + " models", "success", 5000);
  } catch (e) {
    document.getElementById("loading").style.display = "none";
    document.getElementById("result").innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

function renderAutoMLResult(r) {
  const leaderboard = r.leaderboard || [];
  const metricKey = r.task_type === "classification" ? "accuracy" : "r2";

  document.getElementById("result").innerHTML = `
    <div class="card p-6 mb-6">
      <div class="flex justify-between items-start mb-4 flex-wrap gap-2">
        <div>
          <h2 class="font-semibold text-stone-900 text-lg">AutoML Run #${r.run_id}</h2>
          <p class="text-xs text-stone-500 mt-1">${esc(r.task_type)} · ${r.total_models_tested} models tested</p>
        </div>
        <div class="flex gap-3">
          <div class="stat-card" style="min-width:120px"><p class="stat-label">Best Score</p><p class="stat-value">${r.best_score != null ? r.best_score.toFixed(4) : "—"}</p></div>
          <div class="stat-card" style="min-width:120px"><p class="stat-label">Time</p><p class="stat-value">${r.elapsed_seconds}s</p></div>
        </div>
      </div>
      ${r.best_algorithm ? `
        <div class="p-4 rounded-md mb-4" style="background:#ecfdf5;border:1px solid #047857">
          <p class="font-semibold text-stone-900">🏆 Winner: <span style="color:#047857">${esc(r.best_algorithm)}</span></p>
          <p class="text-xs text-stone-600 mt-1">Best model saved as ML Model #${r.best_model_id}</p>
        </div>
      ` : ''}
    </div>

    <div class="card p-6">
      <h3 class="font-semibold text-stone-900 mb-4">Leaderboard</h3>
      <div class="space-y-2">
        ${leaderboard.map(m => renderLeaderCard(m, metricKey)).join("")}
      </div>
    </div>
  `;
}

function renderLeaderCard(m, metricKey) {
  const isWinner = m.rank === 1;
  const isFailed = m.status === "failed";

  if (isFailed) {
    return `
      <div class="leader-card" style="opacity:0.6">
        <div>
          <p class="font-medium text-sm">${esc(m.algorithm_label)}</p>
          <p class="text-xs text-red-600">${esc(m.error || 'Failed')}</p>
        </div>
        <span class="badge badge-red">failed</span>
      </div>
    `;
  }

  const metricVal = m.metrics?.[metricKey];
  return `
    <div class="leader-card ${isWinner ? 'winner' : ''}">
      <div style="flex:1;min-width:0">
        <div class="flex items-center gap-2 mb-1">
          ${isWinner ? '<span class="badge badge-emerald">🏆 Best</span>' : `<span class="badge badge-stone">#${m.rank}</span>`}
          <p class="font-medium text-sm text-stone-900">${esc(m.algorithm_label)}</p>
        </div>
        <p class="text-xs text-stone-500">Trained in ${m.elapsed_seconds}s</p>
      </div>
      <div class="text-right">
        <p class="text-xs text-stone-500">${esc(metricKey)}</p>
        <p class="text-lg font-bold" style="color:${isWinner ? '#047857' : '#57534e'}">${metricVal != null ? metricVal.toFixed(4) : "—"}</p>
      </div>
    </div>
  `;
}

// ============ TAB 2: Run History ============
async function renderHistory(box) {
  box.innerHTML = '<div class="card p-8 text-center"><span class="spinner"></span> Loading runs...</div>';
  try {
    const runs = await apiFetch("/api/automl/runs");
    if (!runs.length) {
      box.innerHTML = '<div class="card p-10 text-center"><p class="text-4xl mb-3">📚</p><p class="font-medium text-stone-700">No AutoML runs yet</p></div>';
      return;
    }
    box.innerHTML = `
      <div class="card p-6">
        <h2 class="font-semibold text-stone-900 mb-4">Run History (last 50)</h2>
        <div class="space-y-2">
          ${runs.map(r => `
            <div class="leader-card" style="cursor:pointer" data-run="${r.id}">
              <div style="flex:1">
                <div class="flex items-center gap-2 mb-1">
                  <span class="badge badge-${r.status === 'completed' ? 'emerald' : 'red'}">${esc(r.status)}</span>
                  <p class="font-medium text-sm">${esc(r.name)}</p>
                </div>
                <p class="text-xs text-stone-500">${r.total_models_tested} models · ${r.elapsed_seconds}s · ${new Date(r.started_at).toLocaleString()}</p>
              </div>
              <span class="text-xs text-indigo-600">View →</span>
            </div>
          `).join("")}
        </div>
      </div>
    `;
    box.querySelectorAll("[data-run]").forEach(card => {
      card.addEventListener("click", () => viewRunDetail(parseInt(card.dataset.run)));
    });
  } catch (e) {
    box.innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

async function viewRunDetail(runId) {
  document.getElementById("result").innerHTML = '<div class="card p-8 text-center"><span class="spinner"></span></div>';
  try {
    const r = await apiFetch("/api/automl/runs/" + runId);
    renderAutoMLResult({
      run_id: r.id,
      task_type: r.task_type,
      best_algorithm: r.leaderboard?.[0]?.algorithm,
      best_score: r.leaderboard?.[0]?.score,
      best_model_id: r.best_model_id,
      total_models_tested: r.total_models_tested,
      elapsed_seconds: r.elapsed_seconds,
      leaderboard: r.leaderboard || [],
    });
  } catch (e) {
    document.getElementById("result").innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

// ============ TAB 3: API Keys ============
async function renderAPI(box) {
  box.innerHTML = '<div class="card p-8 text-center"><span class="spinner"></span> Loading models...</div>';
  try {
    const models = await apiFetch("/api/ml/models");
    const usable = models.filter(m => m.model_path);
    if (!usable.length) {
      box.innerHTML = '<div class="card p-10 text-center"><p class="text-4xl mb-3">🔑</p><p class="font-medium text-stone-700">No models with saved files</p><p class="text-sm text-stone-500 mt-1">Train a model first or run AutoML.</p></div>';
      return;
    }
    box.innerHTML = `
      <div class="card p-6">
        <h2 class="font-semibold text-stone-900 mb-4">Select Model to Generate API Key</h2>
        <div class="grid grid-cols-2 gap-3 mb-4">
          ${usable.map(m => `
            <div class="leader-card" style="cursor:pointer" data-model="${m.id}" data-name="${esc(m.name)}">
              <div style="flex:1;min-width:0">
                <p class="font-medium text-sm">${esc(m.name)}</p>
                <p class="text-xs text-stone-500">${esc(m.algorithm)} · ${esc(m.target_column)}</p>
              </div>
              <span class="text-xs text-indigo-600">Manage →</span>
            </div>
          `).join("")}
        </div>
      </div>
      <div id="apiKeySection"></div>
    `;
    box.querySelectorAll("[data-model]").forEach(card => {
      card.addEventListener("click", () => showModelKeys(parseInt(card.dataset.model), card.dataset.name));
    });
  } catch (e) {
    box.innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

async function showModelKeys(modelId, modelName) {
  const box = document.getElementById("apiKeySection");
  box.innerHTML = '<div class="card p-6 mt-4"><span class="spinner"></span></div>';
  try {
    const keys = await apiFetch("/api/models/" + modelId + "/api-keys");
    box.innerHTML = `
      <div class="card p-6 mt-4">
        <div class="flex justify-between items-center mb-4 flex-wrap gap-2">
          <div>
            <h2 class="font-semibold text-stone-900">API Keys for: ${esc(modelName)}</h2>
            <p class="text-xs text-stone-500 mt-1">Use these keys to call POST /api/predict/${modelId}</p>
          </div>
          <button id="newKeyBtn" class="btn-primary">+ Generate New Key</button>
        </div>
        ${keys.length ? `
          <div class="space-y-2">
            ${keys.map(k => `
              <div class="leader-card">
                <div style="flex:1;min-width:0">
                  <p class="font-medium text-sm">${esc(k.name || 'Unnamed')}</p>
                  <p class="text-xs text-stone-500" style="font-family:monospace">${esc(k.key_prefix)}...  ·  ${k.call_count} calls</p>
                  <p class="text-xs text-stone-500">Created: ${new Date(k.created_at).toLocaleString()}</p>
                </div>
                <div class="flex items-center gap-2">
                  <span class="badge badge-${k.active ? 'emerald' : 'stone'}">${k.active ? 'active' : 'revoked'}</span>
                  ${k.active ? `<button class="revoke-key btn-ghost" data-key="${k.id}" style="color:#b91c1c">Revoke</button>` : ''}
                </div>
              </div>
            `).join("")}
          </div>
        ` : '<p class="text-sm text-stone-500">No API keys yet. Generate one to get started.</p>'}
      </div>
    `;
    document.getElementById("newKeyBtn").addEventListener("click", () => createKey(modelId));
    box.querySelectorAll(".revoke-key").forEach(btn => {
      btn.addEventListener("click", () => revokeKey(parseInt(btn.dataset.key), modelId, modelName));
    });
  } catch (e) {
    box.innerHTML = '<div class="card p-6 mt-4"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

async function createKey(modelId) {
  const name = prompt("Give this key a name (optional):", "");
  try {
    const res = await apiFetch("/api/api-keys", {
      method: "POST",
      body: { model_id: modelId, name: name || null },
    });
    alert("✓ API Key Created\n\nSAVE THIS KEY NOW (it won't be shown again):\n\n" + res.api_key);
    showModelKeys(modelId, "model");
  } catch (e) { toast(e.message, "error"); }
}

async function revokeKey(keyId, modelId, modelName) {
  if (!confirm("Revoke this API key?")) return;
  try {
    await apiFetch("/api/api-keys/" + keyId, { method: "DELETE" });
    toast("Key revoked", "success");
    showModelKeys(modelId, modelName);
  } catch (e) { toast(e.message, "error"); }
}

// ============ TAB 4: Drift Monitoring ============
async function renderDrift(box) {
  box.innerHTML = '<div class="card p-8 text-center"><span class="spinner"></span> Loading models...</div>';
  try {
    const models = await apiFetch("/api/ml/models");
    const usable = models.filter(m => m.model_path);
    if (!usable.length) {
      box.innerHTML = '<div class="card p-10 text-center"><p class="text-4xl mb-3">📊</p><p class="font-medium text-stone-700">No models available</p></div>';
      return;
    }
    box.innerHTML = `
      <div class="card p-6">
        <h2 class="font-semibold text-stone-900 mb-4">Check Data Drift for a Model</h2>
        <p class="text-xs text-stone-500 mb-4">Compares the model's training dataset against a new dataset using KS test + PSI.</p>
        <div class="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label class="label">Model</label>
            <select id="driftModel" class="input">
              <option value="">— Select model —</option>
              ${usable.map(m => `<option value="${m.id}">${esc(m.name)}</option>`).join("")}
            </select>
          </div>
          <div>
            <label class="label">Comparison dataset</label>
            <select id="driftDataset" class="input"><option value="">Loading...</option></select>
          </div>
        </div>
        <button id="driftBtn" class="btn-primary">📊 Run Drift Check</button>
      </div>
      <div id="driftResult" class="mt-4"></div>
    `;
    const dsList = await apiFetch("/api/data/datasets");
    document.getElementById("driftDataset").innerHTML = '<option value="">— Select dataset —</option>' +
      dsList.map(d => `<option value="${d.id}">${esc(d.filename)}</option>`).join("");
    document.getElementById("driftBtn").addEventListener("click", runDriftCheck);
  } catch (e) {
    box.innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

async function runDriftCheck() {
  const modelId = document.getElementById("driftModel").value;
  const dsId = document.getElementById("driftDataset").value;
  if (!modelId || !dsId) { toast("Select both model and dataset", "warning"); return; }

  document.getElementById("driftResult").innerHTML = '<div class="card p-8 text-center"><span class="spinner"></span> Analyzing...</div>';
  try {
    const res = await apiFetch("/api/models/" + modelId + "/drift-check", {
      method: "POST",
      body: { model_id: parseInt(modelId), dataset_id: parseInt(dsId) },
    });
    renderDriftResult(res);
  } catch (e) {
    document.getElementById("driftResult").innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

function renderDriftResult(r) {
  const statusClass = r.overall_status === "healthy" ? "drift-healthy" : r.overall_status === "warning" ? "drift-warning" : "drift-critical";
  const statusLabel = r.overall_status.toUpperCase();

  document.getElementById("driftResult").innerHTML = `
    <div class="card p-6 mb-4">
      <div class="flex justify-between items-start mb-4 flex-wrap gap-2">
        <div>
          <h3 class="font-semibold text-stone-900 text-lg">Drift Analysis: ${esc(r.model_name)}</h3>
          <p class="text-xs text-stone-500 mt-1">${esc(r.reference_dataset)} → ${esc(r.current_dataset)}</p>
        </div>
        <span class="drift-badge ${statusClass}" style="font-size:13px;padding:6px 14px">${statusLabel}</span>
      </div>
      <div class="grid grid-cols-3 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">Columns Analyzed</p><p class="stat-value">${r.columns_analyzed}</p></div>
        <div class="stat-card"><p class="stat-label">Drift Detected</p><p class="stat-value" style="color:${r.columns_with_drift > 0 ? '#b91c1c' : '#047857'}">${r.columns_with_drift}</p></div>
        <div class="stat-card"><p class="stat-label">Overall</p><p class="stat-value" style="font-size:16px">${statusLabel}</p></div>
      </div>
      <h4 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">Per-Feature Details</h4>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:6px">
        <table class="data-table">
          <thead><tr>
            <th>Feature</th><th style="text-align:right">Ref Mean</th><th style="text-align:right">Cur Mean</th>
            <th style="text-align:right">KS p-value</th><th style="text-align:right">PSI</th><th>Status</th>
          </tr></thead>
          <tbody>
            ${r.details.map(d => `
              <tr>
                <td><strong>${esc(d.column)}</strong></td>
                <td style="text-align:right">${d.ref_mean}</td>
                <td style="text-align:right">${d.cur_mean}</td>
                <td style="text-align:right">${d.ks_pvalue ?? "—"}</td>
                <td style="text-align:right">${d.psi ?? "—"}</td>
                <td><span class="drift-badge drift-${d.psi_label === 'no_drift' ? 'healthy' : d.psi_label === 'moderate_drift' ? 'warning' : 'critical'}">${d.psi_label.replace(/_/g, ' ')}</span></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
      <p class="text-xs text-stone-500 mt-3"><strong>PSI interpretation:</strong> &lt;0.1 no drift · 0.1-0.25 moderate · &gt;0.25 significant</p>
    </div>
  `;
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

renderTab();
document.addEventListener("neda:dataset-uploaded", () => { if (activeTab === "run") renderTab(); });
