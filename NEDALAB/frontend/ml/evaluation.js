requireAuth();
renderSidebar("ml-eval");

let activeEval = "cv";
let currentDatasetId = null;
let allAlgorithms = { classification: [], regression: [] };
let charts = {};

async function loadDatasets() {
  const sel = document.getElementById("dsSelect");
  try {
    const data = await apiFetch("/api/data/datasets");
    if (!data.length) { sel.innerHTML = '<option value="">No datasets</option>'; return; }
    sel.innerHTML = '<option value="">— Select dataset —</option>' +
      data.map(d => `<option value="${d.id}">${esc(d.filename)} (${d.row_count} rows)</option>`).join("");
  } catch (e) { sel.innerHTML = '<option value="">Error</option>'; }
}

async function loadAlgorithms() {
  try {
    allAlgorithms = await apiFetch("/api/ml/algorithms");
  } catch (e) {}
}

document.getElementById("dsSelect").addEventListener("change", onDatasetChange);
document.getElementById("taskType").addEventListener("change", () => {
  updateAlgorithms();
  if (currentDatasetId) loadFeatureList();
});

async function onDatasetChange() {
  const id = document.getElementById("dsSelect").value;
  if (!id) { currentDatasetId = null; return; }
  currentDatasetId = parseInt(id);
  try {
    const info = await apiFetch("/api/data/datasets/" + currentDatasetId + "/column-info");
    const tgt = document.getElementById("tgtSelect");
    tgt.disabled = false;
    tgt.innerHTML = '<option value="">— Select —</option>' +
      info.all_columns.map(c => `<option value="${c}">${esc(c)}</option>`).join("");
    updateAlgorithms();
    loadFeatureList();
  } catch (e) { toast(e.message, "error"); }
}

function updateAlgorithms() {
  const taskType = document.getElementById("taskType").value;
  const algos = allAlgorithms[taskType] || [];
  const sel = document.getElementById("algoSelect");
  sel.disabled = false;
  sel.innerHTML = algos.map(a => `<option value="${a.value}">${esc(a.label)}</option>`).join("");
}

async function loadFeatureList() {
  if (!currentDatasetId) return;
  try {
    const info = await apiFetch("/api/data/datasets/" + currentDatasetId + "/column-info");
    const box = document.getElementById("featList");
    box.innerHTML = info.all_columns.map(c => `
      <label class="flex items-center gap-1.5 text-sm cursor-pointer">
        <input type="checkbox" class="feat-check" value="${esc(c)}" style="accent-color:#047857" />
        <span class="text-stone-700">${esc(c)}</span>
      </label>
    `).join("");
  } catch (e) {}
}

document.querySelectorAll(".eval-tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".eval-tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeEval = btn.dataset.eval;
    runEvaluation();
  });
});

function getPayload() {
  const target = document.getElementById("tgtSelect").value;
  if (!currentDatasetId) { toast("Select dataset", "warning"); return null; }
  if (!target) { toast("Select target column", "warning"); return null; }
  const features = Array.from(document.querySelectorAll(".feat-check:checked")).map(c => c.value);
  if (!features.length) { toast("Select at least one feature", "warning"); return null; }
  if (features.includes(target)) { toast("Target cannot be in features", "warning"); return null; }

  return {
    dataset_id: currentDatasetId,
    target_column: target,
    feature_columns: features,
    task_type: document.getElementById("taskType").value,
    algorithm: document.getElementById("algoSelect").value,
  };
}

async function runEvaluation() {
  const base = getPayload();
  if (!base) return;

  document.getElementById("empty").style.display = "none";
  document.getElementById("result").innerHTML = "";
  document.getElementById("loading").style.display = "block";

  try {
    if (activeEval === "cv") {
      base.n_folds = 5;
      const res = await apiFetch("/api/ml/cross-validate", { method: "POST", body: base });
      renderCV(res);
    } else if (activeEval === "roc") {
      const res = await apiFetch("/api/ml/roc-curve", { method: "POST", body: base });
      renderROC(res);
    } else if (activeEval === "pr") {
      const res = await apiFetch("/api/ml/pr-curve", { method: "POST", body: base });
      renderPR(res);
    } else if (activeEval === "lc") {
      base.n_folds = 5;
      const res = await apiFetch("/api/ml/learning-curve", { method: "POST", body: base });
      renderLC(res);
    } else if (activeEval === "diag") {
      const res = await apiFetch("/api/ml/regression-diagnostics", { method: "POST", body: base });
      renderDiagnostics(res);
    }
    document.getElementById("loading").style.display = "none";
  } catch (e) {
    document.getElementById("loading").style.display = "none";
    document.getElementById("result").innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

// ============ CV ============
function renderCV(r) {
  const box = document.getElementById("result");
  box.innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-1">${r.n_folds}-Fold Cross-Validation</h2>
      <p class="text-xs text-stone-500 mb-4">Scoring: ${esc(r.scoring)} · n = ${r.n_samples} · ${esc(r.algorithm)}</p>
      <div class="grid grid-cols-4 gap-3 mb-6">
        <div class="stat-card"><p class="stat-label">Mean</p><p class="stat-value">${fmt(r.mean)}</p></div>
        <div class="stat-card"><p class="stat-label">Std Dev</p><p class="stat-value">${fmt(r.std)}</p></div>
        <div class="stat-card"><p class="stat-label">Min</p><p class="stat-value">${fmt(r.min)}</p></div>
        <div class="stat-card"><p class="stat-label">Max</p><p class="stat-value">${fmt(r.max)}</p></div>
      </div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">Per-fold scores</h3>
      <div class="rounded-md" style="border:1px solid #e7e5e4">
        ${r.scores.map((s, i) => `
          <div class="cv-fold-row">
            <span class="text-stone-500" style="min-width:80px">Fold ${i + 1}</span>
            <span style="font-weight:600;color:#047857">${fmt(s)}</span>
          </div>
        `).join("")}
      </div>
      <div class="mt-4" style="height:220px"><canvas id="cvChart"></canvas></div>
    </div>
  `;
  setTimeout(() => {
    const ctx = document.getElementById("cvChart").getContext("2d");
    if (charts.cv) charts.cv.destroy();
    charts.cv = new Chart(ctx, {
      type: "bar",
      data: {
        labels: r.scores.map((_, i) => "Fold " + (i + 1)),
        datasets: [{
          label: "Score",
          data: r.scores,
          backgroundColor: "#047857",
          borderRadius: 4,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: false, grid: { color: "#e7e5e4" } }, x: { grid: { display: false } } },
      },
    });
  }, 100);
}

// ============ ROC ============
function renderROC(r) {
  const box = document.getElementById("result");
  box.innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-1">ROC Curve</h2>
      <p class="text-xs text-stone-500 mb-4">n_test = ${r.n_test}</p>
      <div class="grid grid-cols-2 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">AUC</p><p class="stat-value">${fmt(r.auc)}</p></div>
        <div class="stat-card"><p class="stat-label">Interpretation</p><p class="stat-value" style="font-size:16px">${aucLabel(r.auc)}</p></div>
      </div>
      <div style="height:400px"><canvas id="rocChart"></canvas></div>
    </div>
  `;
  setTimeout(() => {
    const ctx = document.getElementById("rocChart").getContext("2d");
    if (charts.roc) charts.roc.destroy();
    charts.roc = new Chart(ctx, {
      type: "line",
      data: {
        labels: r.fpr,
        datasets: [
          {
            label: "ROC Curve (AUC = " + fmt(r.auc) + ")",
            data: r.tpr,
            borderColor: "#047857",
            backgroundColor: "rgba(4,120,87,0.1)",
            borderWidth: 2, fill: true, tension: 0.1,
            pointRadius: 0,
          },
          {
            label: "Random (AUC = 0.5)",
            data: r.fpr,
            borderColor: "#a8a29e",
            borderDash: [6, 4],
            borderWidth: 1, fill: false, pointRadius: 0,
          },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } },
        scales: {
          x: { title: { display: true, text: "False Positive Rate" }, grid: { color: "#e7e5e4" } },
          y: { title: { display: true, text: "True Positive Rate" }, grid: { color: "#e7e5e4" } },
        },
      },
    });
  }, 100);
}

function aucLabel(auc) {
  if (auc === null || auc === undefined) return "—";
  if (auc >= 0.9) return "Excellent";
  if (auc >= 0.8) return "Good";
  if (auc >= 0.7) return "Fair";
  if (auc >= 0.6) return "Poor";
  return "Failed";
}

// ============ PR ============
function renderPR(r) {
  const box = document.getElementById("result");
  box.innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-1">Precision-Recall Curve</h2>
      <p class="text-xs text-stone-500 mb-4">n_test = ${r.n_test}</p>
      <div class="grid grid-cols-2 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">Average Precision</p><p class="stat-value">${fmt(r.avg_precision)}</p></div>
        <div class="stat-card"><p class="stat-label">Interpretation</p><p class="stat-value" style="font-size:16px">${aucLabel(r.avg_precision)}</p></div>
      </div>
      <div style="height:400px"><canvas id="prChart"></canvas></div>
    </div>
  `;
  setTimeout(() => {
    const ctx = document.getElementById("prChart").getContext("2d");
    if (charts.pr) charts.pr.destroy();
    charts.pr = new Chart(ctx, {
      type: "line",
      data: {
        labels: r.recall,
        datasets: [{
          label: "PR Curve (AP = " + fmt(r.avg_precision) + ")",
          data: r.precision,
          borderColor: "#b45309",
          backgroundColor: "rgba(180,83,9,0.1)",
          borderWidth: 2, fill: true, tension: 0.1,
          pointRadius: 0,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } },
        scales: {
          x: { title: { display: true, text: "Recall" }, grid: { color: "#e7e5e4" } },
          y: { title: { display: true, text: "Precision" }, grid: { color: "#e7e5e4" }, min: 0, max: 1 },
        },
      },
    });
  }, 100);
}

// ============ Learning Curve ============
function renderLC(r) {
  const box = document.getElementById("result");
  const gap = (r.train_mean[r.train_mean.length - 1] || 0) - (r.val_mean[r.val_mean.length - 1] || 0);
  const overfit = gap > 0.1;

  box.innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-1">Learning Curve</h2>
      <p class="text-xs text-stone-500 mb-4">Scoring: ${esc(r.scoring)}</p>
      <div class="grid grid-cols-3 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">Final Train Score</p><p class="stat-value">${fmt(r.train_mean[r.train_mean.length - 1])}</p></div>
        <div class="stat-card"><p class="stat-label">Final Val Score</p><p class="stat-value">${fmt(r.val_mean[r.val_mean.length - 1])}</p></div>
        <div class="stat-card"><p class="stat-label">Gap</p><p class="stat-value">${fmt(gap)}</p></div>
      </div>
      <div class="p-3 rounded-md mb-4" style="background:${overfit ? '#fef3c7' : '#ecfdf5'};border:1px solid ${overfit ? '#b45309' : '#047857'}">
        <p class="text-sm font-medium">${overfit ? '⚠ Possible overfitting (large train-val gap)' : '✓ Good fit (small train-val gap)'}</p>
      </div>
      <div style="height:400px"><canvas id="lcChart"></canvas></div>
    </div>
  `;
  setTimeout(() => {
    const ctx = document.getElementById("lcChart").getContext("2d");
    if (charts.lc) charts.lc.destroy();
    charts.lc = new Chart(ctx, {
      type: "line",
      data: {
        labels: r.train_sizes,
        datasets: [
          {
            label: "Training Score",
            data: r.train_mean,
            borderColor: "#047857",
            backgroundColor: "rgba(4,120,87,0.1)",
            borderWidth: 2, fill: false, tension: 0.2,
            pointRadius: 4, pointBackgroundColor: "#047857",
          },
          {
            label: "Validation Score",
            data: r.val_mean,
            borderColor: "#b45309",
            backgroundColor: "rgba(180,83,9,0.1)",
            borderWidth: 2, fill: false, tension: 0.2,
            pointRadius: 4, pointBackgroundColor: "#b45309",
          },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } },
        scales: {
          x: { title: { display: true, text: "Training Samples" }, grid: { color: "#e7e5e4" } },
          y: { title: { display: true, text: r.scoring }, grid: { color: "#e7e5e4" } },
        },
      },
    });
  }, 100);
}

// ============ Regression Diagnostics ============
function renderDiagnostics(r) {
  const box = document.getElementById("result");
  const rs = r.residual_stats;

  box.innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-1">Regression Diagnostics</h2>
      <p class="text-xs text-stone-500 mb-4">n_train = ${r.n_train} · n_test = ${r.n_test}</p>
      <div class="grid grid-cols-4 gap-3 mb-6">
        <div class="stat-card"><p class="stat-label">Residual Mean</p><p class="stat-value">${fmt(rs.mean)}</p></div>
        <div class="stat-card"><p class="stat-label">Residual Std</p><p class="stat-value">${fmt(rs.std)}</p></div>
        <div class="stat-card"><p class="stat-label">Min Residual</p><p class="stat-value">${fmt(rs.min)}</p></div>
        <div class="stat-card"><p class="stat-label">Max Residual</p><p class="stat-value">${fmt(rs.max)}</p></div>
      </div>

      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Actual vs Predicted</h3>
      <div style="height:380px" class="mb-8"><canvas id="scatterChart"></canvas></div>

      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Residual Distribution</h3>
      <div style="height:280px"><canvas id="residChart"></canvas></div>
    </div>
  `;

  setTimeout(() => {
    // Scatter
    const sctx = document.getElementById("scatterChart").getContext("2d");
    if (charts.scatter) charts.scatter.destroy();
    const points = r.scatter.map(p => ({ x: p.actual, y: p.predicted }));
    const allVals = points.flatMap(p => [p.x, p.y]).filter(v => v !== null);
    const minV = Math.min(...allVals);
    const maxV = Math.max(...allVals);

    charts.scatter = new Chart(sctx, {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "Predictions",
            data: points,
            backgroundColor: "rgba(4,120,87,0.6)",
            pointRadius: 3,
          },
          {
            label: "Perfect (y=x)",
            data: [{ x: minV, y: minV }, { x: maxV, y: maxV }],
            type: "line",
            borderColor: "#a8a29e",
            borderDash: [6, 4],
            borderWidth: 1,
            pointRadius: 0,
            fill: false,
          },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } },
        scales: {
          x: { title: { display: true, text: "Actual" }, grid: { color: "#e7e5e4" } },
          y: { title: { display: true, text: "Predicted" }, grid: { color: "#e7e5e4" } },
        },
      },
    });

    // Residual histogram
    const rctx = document.getElementById("residChart").getContext("2d");
    if (charts.resid) charts.resid.destroy();
    const edges = r.residual_histogram.bin_edges;
    const labels = edges.slice(0, -1).map((e, i) => ((e + edges[i + 1]) / 2).toFixed(2));

    charts.resid = new Chart(rctx, {
      type: "bar",
      data: {
        labels,
        datasets: [{
          label: "Frequency",
          data: r.residual_histogram.counts,
          backgroundColor: "#047857",
          borderRadius: 3,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { title: { display: true, text: "Residual Value" }, grid: { display: false } },
          y: { title: { display: true, text: "Count" }, grid: { color: "#e7e5e4" }, beginAtZero: true },
        },
      },
    });
  }, 100);
}

function fmt(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return v.toFixed(4);
  return String(v);
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

loadDatasets();
loadAlgorithms();
document.addEventListener("neda:dataset-uploaded", loadDatasets);
