requireAuth();
renderSidebar("ml-tune");

let activeMode = "tune";
let currentDatasetId = null;
let allAlgorithms = { classification: [], regression: [] };
let charts = {};

document.querySelectorAll(".tune-tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tune-tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeMode = btn.dataset.mode;
    document.getElementById("tuneMode").style.display = activeMode === "tune" ? "block" : "none";
    document.getElementById("shapMode").style.display = activeMode === "shap" ? "block" : "none";
    if (activeMode === "shap") loadModelsForShap();
  });
});

async function loadAlgorithms() {
  try { allAlgorithms = await apiFetch("/api/ml/algorithms"); } catch (e) {}
}

async function loadDatasets() {
  const sel = document.getElementById("dsSelect");
  try {
    const data = await apiFetch("/api/data/datasets");
    if (!data.length) { sel.innerHTML = '<option value="">No datasets</option>'; return; }
    sel.innerHTML = '<option value="">— Select —</option>' +
      data.map(d => `<option value="${d.id}">${esc(d.filename)}</option>`).join("");
  } catch (e) { sel.innerHTML = '<option value="">Error</option>'; }
}

document.getElementById("dsSelect").addEventListener("change", async () => {
  const id = document.getElementById("dsSelect").value;
  if (!id) return;
  currentDatasetId = parseInt(id);
  try {
    const info = await apiFetch("/api/data/datasets/" + currentDatasetId + "/column-info");
    const tgt = document.getElementById("targetSelect");
    tgt.disabled = false;
    tgt.innerHTML = '<option value="">— Target —</option>' +
      info.all_columns.map(c => `<option value="${c}">${esc(c)}</option>`).join("");
    const fl = document.getElementById("featureList");
    fl.innerHTML = info.all_columns.map(c => `
      <label class="flex items-center gap-1.5 text-sm cursor-pointer">
        <input type="checkbox" class="feat-check" value="${esc(c)}" style="accent-color:#047857" />
        <span class="text-stone-700">${esc(c)}</span>
      </label>
    `).join("");
    updateAlgoList();
  } catch (e) { toast(e.message, "error"); }
});

document.getElementById("taskType").addEventListener("change", updateAlgoList);

function updateAlgoList() {
  const t = document.getElementById("taskType").value;
  const algos = allAlgorithms[t] || [];
  document.getElementById("algoSelect").innerHTML =
    algos.map(a => `<option value="${a.value}">${esc(a.label)}</option>`).join("");
}

document.getElementById("runTuneBtn").addEventListener("click", async () => {
  const target = document.getElementById("targetSelect").value;
  const features = Array.from(document.querySelectorAll(".feat-check:checked")).map(c => c.value);
  if (!currentDatasetId) { toast("Select dataset", "warning"); return; }
  if (!target) { toast("Select target", "warning"); return; }
  if (!features.length) { toast("Select features", "warning"); return; }
  if (features.includes(target)) { toast("Target cannot be in features", "warning"); return; }

  const btn = document.getElementById("runTuneBtn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="border-color:rgba(255,255,255,0.3);border-top-color:white"></span> Running...';
  document.getElementById("tuneResult").innerHTML = "";
  document.getElementById("loading").style.display = "block";

  try {
    const res = await apiFetch("/api/ml/tune", {
      method: "POST",
      body: {
        dataset_id: currentDatasetId,
        target_column: target,
        feature_columns: features,
        task_type: document.getElementById("taskType").value,
        algorithm: document.getElementById("algoSelect").value,
        method: document.getElementById("searchMethod").value,
        n_iter: 20,
        cv_folds: parseInt(document.getElementById("cvFolds").value) || 5,
      },
    });
    document.getElementById("loading").style.display = "none";
    renderTuneResult(res);
    toast("Tuning complete · Best " + res.scoring + ": " + res.best_score.toFixed(4), "success", 5000);
  } catch (e) {
    document.getElementById("loading").style.display = "none";
    document.getElementById("tuneResult").innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  } finally {
    btn.disabled = false;
    btn.textContent = "🎛️ Run Tuning";
  }
});

function renderTuneResult(r) {
  const box = document.getElementById("tuneResult");
  const params = Object.entries(r.best_params).map(([k, v]) =>
    `<span class="badge badge-emerald" style="margin:2px">${esc(k)} = ${esc(v)}</span>`
  ).join("");

  box.innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-3">Tuning Result</h2>
      <div class="grid grid-cols-4 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">Best Score</p><p class="stat-value">${r.best_score.toFixed(4)}</p></div>
        <div class="stat-card"><p class="stat-label">Combos Tested</p><p class="stat-value">${r.tested}</p></div>
        <div class="stat-card"><p class="stat-label">CV Folds</p><p class="stat-value">${r.cv_folds}</p></div>
        <div class="stat-card"><p class="stat-label">Time</p><p class="stat-value">${r.elapsed_seconds}s</p></div>
      </div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2 mt-4">Best Parameters</h3>
      <div class="mb-4">${params}</div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">Top 10 Combinations</h3>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:6px">
        <table class="data-table">
          <thead><tr><th>Rank</th><th style="text-align:right">Mean Score</th><th style="text-align:right">Std</th><th>Parameters</th></tr></thead>
          <tbody>
            ${r.top_results.map(t => `<tr>
              <td>${t.rank}</td>
              <td style="text-align:right;font-weight:600;color:#047857">${t.mean_score.toFixed(4)}</td>
              <td style="text-align:right">${t.std_score.toFixed(4)}</td>
              <td style="font-family:monospace;font-size:11px">${esc(JSON.stringify(t.params))}</td>
            </tr>`).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// ============ SHAP ============
async function loadModelsForShap() {
  const box = document.getElementById("modelList");
  try {
    const models = await apiFetch("/api/ml/models");
    const usable = models.filter(m => m.model_path);
    if (!usable.length) {
      box.innerHTML = '<p class="text-sm text-stone-500 col-span-2">No saved models. Train one first.</p>';
      return;
    }
    box.innerHTML = usable.map(m => `
      <div class="model-card cursor-pointer border rounded-md p-3" data-mid="${m.id}" style="border-color:#e7e5e4">
        <p class="font-medium text-stone-900 text-sm">${esc(m.name)}</p>
        <p class="text-xs text-stone-500 mt-1">${esc(m.algorithm)} · ${esc(m.target_column)}</p>
      </div>
    `).join("");
    box.querySelectorAll(".model-card").forEach(card => {
      card.addEventListener("click", () => computeShap(parseInt(card.dataset.mid)));
    });
  } catch (e) { box.innerHTML = '<p class="text-sm text-red-600">' + esc(e.message) + '</p>'; }
}

async function computeShap(modelId) {
  document.getElementById("shapResult").innerHTML = "";
  document.getElementById("loading").style.display = "block";
  try {
    const res = await apiFetch("/api/ml/shap", {
      method: "POST",
      body: { model_id: modelId, max_samples: 100 },
    });
    document.getElementById("loading").style.display = "none";
    renderShap(res);
  } catch (e) {
    document.getElementById("loading").style.display = "none";
    document.getElementById("shapResult").innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

function renderShap(r) {
  const box = document.getElementById("shapResult");
  const gi = r.global_importance || [];
  const loc = r.local_explanation || [];
  const maxAbs = Math.max(...gi.map(x => x.mean_abs_shap), 0.0001);

  box.innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-1">Global Feature Importance (SHAP)</h2>
      <p class="text-xs text-stone-500 mb-4">${r.n_samples_explained} samples · ${r.n_features} features</p>
      <div class="space-y-2 mb-6">
        ${gi.slice(0, 15).map(f => `
          <div>
            <div class="flex justify-between text-xs text-stone-700 mb-1">
              <span style="font-family:monospace">${esc(f.feature)}</span>
              <span style="font-weight:600">${f.mean_abs_shap.toFixed(4)}</span>
            </div>
            <div class="shap-bar"><div class="shap-fill pos" style="width:${(f.mean_abs_shap / maxAbs * 100).toFixed(1)}%"></div></div>
          </div>
        `).join("")}
      </div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2 mt-6">Local Explanation (First Row)</h3>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:6px">
        <table class="data-table">
          <thead><tr><th>Feature</th><th style="text-align:right">SHAP Value</th><th style="text-align:right">Feature Value</th></tr></thead>
          <tbody>
            ${loc.slice(0, 15).map(l => `<tr>
              <td style="font-family:monospace">${esc(l.feature)}</td>
              <td style="text-align:right;color:${l.shap_value > 0 ? '#047857' : '#b91c1c'};font-weight:600">${l.shap_value.toFixed(4)}</td>
              <td style="text-align:right">${l.feature_value != null ? l.feature_value.toFixed(4) : '—'}</td>
            </tr>`).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

loadAlgorithms();
loadDatasets();
document.addEventListener("neda:dataset-uploaded", loadDatasets);
