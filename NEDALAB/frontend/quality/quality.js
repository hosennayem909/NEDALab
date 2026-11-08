requireAuth();
renderSidebar("quality");
window.NEDA_API_BASE = window.NEDA_API_BASE || "http://127.0.0.1:8000";

// Persistent state backed by localStorage
const STORAGE_KEY = "neda_quality_state";

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return {
    activeTab: "report",
    qr: { datasetId: null, result: null },
    imp: { datasetId: null, result: null },
  };
}

function saveState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (e) {}
}

const state = loadState();

// Restore active tab from saved state
function restoreActiveTab() {
  if (state.activeTab) {
    document.querySelectorAll(".q-tab").forEach(b => {
      b.classList.toggle("active", b.dataset.tab === state.activeTab);
    });
  }
}

// ============================================================
// Tab switching
// ============================================================
document.querySelectorAll(".q-tab").forEach(btn => {
  btn.addEventListener("click", async () => {
    // Save current form values before switching
    saveCurrentForm();

    document.querySelectorAll(".q-tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    state.activeTab = btn.dataset.tab;
    saveState();

    // Rebuild tab
    await renderTab();
  });
});

function saveCurrentForm() {
  if (state.activeTab === "impute") {
    const sel = document.getElementById("impSelect");
    if (sel && sel.value) state.imp.datasetId = parseInt(sel.value);
  } else if (state.activeTab === "report") {
    const sel = document.getElementById("dsSelect");
    if (sel && sel.value) state.qr.datasetId = parseInt(sel.value);
  }
}

// ============================================================
// Render tab (includes result inside)
// ============================================================
async function renderTab() {
  const box = document.getElementById("tabContent");
  if (state.activeTab === "report") {
    box.innerHTML = `
      <div class="card p-5 mb-6">
        <div class="grid grid-cols-3 gap-4">
          <div class="col-span-2">
            <label class="label">Dataset</label>
            <select id="dsSelect" class="input"><option value="">Loading...</option></select>
          </div>
          <div class="flex items-end">
            <button id="exportWordBtn" class="btn-secondary w-full" disabled>📄 Export Word Report</button>
          </div>
        </div>
      </div>
      <div id="qrLoading" style="display:none" class="card p-8 text-center">
        <span class="spinner"></span>
        <p class="text-sm text-stone-600 mt-2">Analyzing...</p>
      </div>
      <div id="qrResult"></div>
    `;
    await loadQualityDatasets();
    document.getElementById("dsSelect").addEventListener("change", onQualityDatasetChange);
    document.getElementById("exportWordBtn").addEventListener("click", exportWord);
    if (state.qr.result) {
      document.getElementById("qrResult").innerHTML = renderQualityReportHTML(state.qr.result);
    }
  } else if (state.activeTab === "impute") {
    box.innerHTML = `
      <div class="card p-6">
        <h2 class="font-semibold text-stone-900 mb-4">Advanced Imputation</h2>
        <p class="text-xs text-stone-500 mb-4">Fill missing values using machine learning techniques.</p>
        <div class="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label class="label">Dataset</label>
            <select id="impSelect" class="input"><option value="">Loading...</option></select>
          </div>
          <div>
            <label class="label">Method</label>
            <select id="impMethod" class="input">
              <option value="knn">KNN Imputation (recommended)</option>
              <option value="mice">MICE (Iterative)</option>
              <option value="interpolate">Linear Interpolation</option>
            </select>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label class="label">KNN neighbors (if KNN)</label>
            <input id="impNeighbors" type="number" min="2" max="20" value="5" class="input" />
          </div>
          <div>
            <label class="label">Max iterations (if MICE)</label>
            <input id="impMaxIter" type="number" min="1" max="30" value="10" class="input" />
          </div>
        </div>
        <div class="mb-4">
          <label class="label">Columns (leave empty for all numeric)</label>
          <div id="impColumnList" class="border rounded-md p-2 max-h-32 overflow-y-auto flex flex-wrap gap-3" style="border-color:#e7e5e4">
            <p class="text-xs text-stone-500">Select dataset first</p>
          </div>
        </div>
        <button id="impRunBtn" class="btn-primary">🩹 Run Imputation</button>
      </div>
      <div id="impLoading" style="display:none" class="card p-8 text-center mt-6">
        <span class="spinner"></span>
        <p class="text-sm text-stone-600 mt-2">Running imputation...</p>
      </div>
      <div id="impResult" class="mt-6"></div>
    `;
    await loadImputeDatasets();
    document.getElementById("impSelect").addEventListener("change", onImputeDatasetChange);
    document.getElementById("impRunBtn").addEventListener("click", runImputation);
    // Restore previous result
    if (state.imp.result) {
      document.getElementById("impResult").innerHTML = renderImputationHTML(state.imp.result);
    }
    // Restore previous dataset
    if (state.imp.datasetId) {
      const sel = document.getElementById("impSelect");
      sel.value = state.imp.datasetId;
      if (sel.value) await onImputeDatasetChange();
    }
  }
}

// ============================================================
// Quality Report
// ============================================================
async function loadQualityDatasets() {
  const sel = document.getElementById("dsSelect");
  try {
    const data = await apiFetch("/api/data/datasets");
    sel.innerHTML = '<option value="">— Select dataset —</option>' +
      data.map(d => `<option value="${d.id}">${esc(d.filename)} (${d.row_count} rows)</option>`).join("");
    if (state.qr.datasetId) {
      sel.value = state.qr.datasetId;
      if (sel.value) document.getElementById("exportWordBtn").disabled = false;
    }
  } catch (e) { sel.innerHTML = '<option value="">Error</option>'; }
}

async function onQualityDatasetChange() {
  const id = document.getElementById("dsSelect").value;
  if (!id) return;
  state.qr.datasetId = parseInt(id);
  saveState();
  document.getElementById("exportWordBtn").disabled = false;

  document.getElementById("qrLoading").style.display = "block";
  document.getElementById("qrResult").innerHTML = "";

  try {
    const res = await apiFetch("/api/data/quality/" + state.qr.datasetId);
    document.getElementById("qrLoading").style.display = "none";
    state.qr.result = res;
    saveState();
    document.getElementById("qrResult").innerHTML = renderQualityReportHTML(res);
  } catch (e) {
    document.getElementById("qrLoading").style.display = "none";
    document.getElementById("qrResult").innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

function renderQualityReportHTML(r) {
  const gradeClass = "health-" + (r.grade || "C");
  return `
    <div class="card p-6 mb-6">
      <div class="flex justify-between items-start mb-6 flex-wrap gap-4">
        <div style="flex:1">
          <h2 class="font-semibold text-stone-900 text-lg mb-1">${esc(r.filename)}</h2>
          <p class="text-xs text-stone-500">${r.n_rows.toLocaleString()} rows × ${r.n_columns} columns</p>
          <div class="grid grid-cols-3 gap-3 mt-4">
            <div class="stat-card"><p class="stat-label">Missing %</p><p class="stat-value" style="color:${r.missing_pct > 10 ? '#b91c1c' : '#047857'}">${r.missing_pct}%</p></div>
            <div class="stat-card"><p class="stat-label">Duplicates</p><p class="stat-value" style="color:${r.duplicate_rows > 0 ? '#b45309' : '#047857'}">${r.duplicate_rows}</p></div>
            <div class="stat-card"><p class="stat-label">Issues</p><p class="stat-value" style="color:${r.n_issues > 0 ? '#b45309' : '#047857'}">${r.n_issues}</p></div>
          </div>
        </div>
        <div>
          <div class="health-ring ${gradeClass}">${r.health_score}</div>
          <p class="text-center text-sm font-medium mt-2">Grade ${r.grade}</p>
        </div>
      </div>
    </div>
    ${r.issues.length ? `
      <div class="card p-6 mb-6">
        <h3 class="font-semibold text-stone-900 mb-3">Issues Detected (${r.issues.length})</h3>
        <div class="space-y-2">
          ${r.issues.map(i => `
            <div class="flex items-center gap-3 text-sm p-2 rounded-md" style="background:#fafaf9">
              <span class="severity-${i.severity}">${i.severity}</span>
              <span style="font-family:monospace;min-width:120px"><strong>${esc(i.column)}</strong></span>
              <span class="text-stone-700">${esc(i.issue)}</span>
            </div>
          `).join("")}
        </div>
      </div>
    ` : '<div class="card p-6 mb-6" style="background:#ecfdf5;border-color:#047857"><p class="text-sm font-medium" style="color:#047857">✓ No issues detected</p></div>'}
    <div class="card p-6">
      <h3 class="font-semibold text-stone-900 mb-4">Column Details</h3>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:6px;max-height:500px">
        <table class="data-table">
          <thead><tr>
            <th>Column</th><th>Type</th><th style="text-align:right">Nulls</th>
            <th style="text-align:right">Unique</th><th style="text-align:right">Mean</th>
            <th style="text-align:right">Min</th><th style="text-align:right">Max</th><th style="text-align:right">Outliers</th>
          </tr></thead>
          <tbody>
            ${r.columns.map(c => `
              <tr>
                <td><strong>${esc(c.name)}</strong></td>
                <td><span class="badge badge-stone">${esc(c.detected_type)}</span></td>
                <td style="text-align:right;color:${c.null_pct > 10 ? '#b91c1c' : '#57534e'}">${c.null_count} (${c.null_pct}%)</td>
                <td style="text-align:right">${c.unique_count}</td>
                <td style="text-align:right">${c.mean ?? '—'}</td>
                <td style="text-align:right">${c.min ?? '—'}</td>
                <td style="text-align:right">${c.max ?? '—'}</td>
                <td style="text-align:right;color:${(c.outlier_count || 0) > 0 ? '#b45309' : '#57534e'}">${c.outlier_count ?? '—'}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

async function exportWord() {
  if (!state.qr.datasetId) return;
  const token = localStorage.getItem("neda_token");
  try {
    toast("Generating Word report...", "info", 2500);
    const res = await fetch(`${window.NEDA_API_BASE}/api/data/datasets/${state.qr.datasetId}/export-word`, {
      headers: { Authorization: "Bearer " + token },
    });
    if (!res.ok) throw new Error("Export failed");
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "dataset_" + state.qr.datasetId + "_report.docx";
    a.click();
    URL.revokeObjectURL(a.href);
    toast("Word report downloaded", "success");
  } catch (e) {
    toast(e.message, "error");
  }
}

// ============================================================
// Imputation
// ============================================================
async function loadImputeDatasets() {
  const sel = document.getElementById("impSelect");
  try {
    const data = await apiFetch("/api/data/datasets");
    sel.innerHTML = '<option value="">— Select dataset —</option>' +
      data.map(d => `<option value="${d.id}">${esc(d.filename)} (${d.row_count} rows)</option>`).join("");
  } catch (e) { sel.innerHTML = '<option value="">Error</option>'; }
}

async function onImputeDatasetChange() {
  const id = document.getElementById("impSelect").value;
  if (!id) return;
  state.imp.datasetId = parseInt(id);
  saveState();
  try {
    const info = await apiFetch("/api/data/datasets/" + state.imp.datasetId + "/column-info");
    const numericColumns = info.numeric_columns || [];
    const box = document.getElementById("impColumnList");
    box.innerHTML = numericColumns.length
      ? numericColumns.map(c => `
          <label class="flex items-center gap-1.5 text-sm cursor-pointer">
            <input type="checkbox" class="imp-check" value="${esc(c)}" style="accent-color:#047857" />
            <span class="text-stone-700">${esc(c)}</span>
          </label>
        `).join("")
      : '<p class="text-xs text-stone-500">No numeric columns</p>';
  } catch (e) { toast(e.message, "error"); }
}

async function runImputation() {
  const dsId = document.getElementById("impSelect").value;
  if (!dsId) { toast("Select dataset", "warning"); return; }
  state.imp.datasetId = parseInt(dsId);

  const method = document.getElementById("impMethod").value;
  const nbr = parseInt(document.getElementById("impNeighbors").value) || 5;
  const mxi = parseInt(document.getElementById("impMaxIter").value) || 10;
  const cols = Array.from(document.querySelectorAll(".imp-check:checked")).map(c => c.value);

  document.getElementById("impLoading").style.display = "block";
  document.getElementById("impResult").innerHTML = "";

  try {
    const res = await apiFetch("/api/data/impute", {
      method: "POST",
      body: {
        dataset_id: state.imp.datasetId,
        method: method,
        columns: cols.length ? cols : null,
        n_neighbors: nbr,
        max_iter: mxi,
      },
    });
    document.getElementById("impLoading").style.display = "none";
    state.imp.result = res;
    saveState();
    document.getElementById("impResult").innerHTML = renderImputationHTML(res);
    toast("Imputation applied successfully", "success");
  } catch (e) {
    document.getElementById("impLoading").style.display = "none";
    document.getElementById("impResult").innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

function renderImputationHTML(res) {
  const rep = res.report;
  return `
    <div class="card p-6">
      <div class="p-4 rounded-md mb-4" style="background:#ecfdf5;border:1px solid #047857">
        <p class="font-medium" style="color:#047857">✓ Imputation completed</p>
        <p class="text-sm text-stone-700 mt-1">Saved as: <strong>${esc(res.output_filename)}</strong></p>
      </div>
      <div class="grid grid-cols-4 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">Method</p><p class="stat-value" style="font-size:16px">${esc(rep.method)}</p></div>
        <div class="stat-card"><p class="stat-label">Missing Before</p><p class="stat-value">${rep.missing_before}</p></div>
        <div class="stat-card"><p class="stat-label">Missing After</p><p class="stat-value">${rep.missing_after}</p></div>
        <div class="stat-card"><p class="stat-label">Filled</p><p class="stat-value" style="color:#047857">${rep.filled}</p></div>
      </div>
      <p class="text-xs text-stone-500">Columns: ${(rep.columns || []).map(esc).join(", ")}</p>
    </div>
  `;
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

// Boot
restoreActiveTab();
renderTab();
document.addEventListener("neda:dataset-uploaded", renderTab);

// Clear saved state button (add a small button in top right)
function addClearButton() {
  if (document.getElementById("clearStateBtn")) return;
  const header = document.querySelector("main .flex.items-center.gap-3");
  if (!header) return;
  const btn = document.createElement("button");
  btn.id = "clearStateBtn";
  btn.className = "btn-secondary ml-auto";
  btn.style.fontSize = "12px";
  btn.textContent = "🗑 Clear Saved Data";
  btn.addEventListener("click", () => {
    if (confirm("Clear all saved results and form data?")) {
      localStorage.removeItem(STORAGE_KEY);
      location.reload();
    }
  });
  header.appendChild(btn);
}
addClearButton();
