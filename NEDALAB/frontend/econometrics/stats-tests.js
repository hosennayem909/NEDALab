requireAuth();
renderSidebar("stats-tests");

let currentDatasetId = null;
let numericColumns = [];
let activeTab = "correlation";

async function loadDatasets() {
  const sel = document.getElementById("datasetSelect");
  try {
    const data = await apiFetch("/api/data/datasets");
    if (!data.length) { sel.innerHTML = '<option value="">No datasets</option>'; return; }
    sel.innerHTML = '<option value="">— Select dataset —</option>' +
      data.map(d => `<option value="${d.id}">${esc(d.filename)} (${d.row_count} rows)</option>`).join("");
  } catch (e) { sel.innerHTML = '<option value="">Error</option>'; }
}

document.getElementById("datasetSelect").addEventListener("change", async () => {
  const id = document.getElementById("datasetSelect").value;
  if (!id) { resetColumns(); return; }
  currentDatasetId = parseInt(id);
  await loadColumns();
});

async function loadColumns() {
  try {
    const info = await apiFetch("/api/data/datasets/" + currentDatasetId + "/column-info");
    numericColumns = info.numeric_columns || [];
    const box = document.getElementById("columnList");
    if (!numericColumns.length) {
      box.innerHTML = '<p class="text-xs text-stone-500">No numeric columns</p>';
      return;
    }
    box.innerHTML = numericColumns.map(c => `
      <label class="flex items-center gap-1.5 text-sm cursor-pointer">
        <input type="checkbox" class="col-check" value="${esc(c)}" checked style="accent-color:#047857" />
        <span class="text-stone-700">${esc(c)}</span>
      </label>
    `).join("");
    box.querySelectorAll(".col-check").forEach(c => c.addEventListener("change", renderTab));
  } catch (e) {
    toast(e.message, "error");
  }
}

function resetColumns() {
  currentDatasetId = null;
  numericColumns = [];
  document.getElementById("columnList").innerHTML = '<p class="text-xs text-stone-500">Select dataset first</p>';
  document.getElementById("tabContent").innerHTML = '';
}

function getSelectedColumns() {
  return Array.from(document.querySelectorAll(".col-check:checked")).map(c => c.value);
}

// Tab switching
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeTab = btn.dataset.tab;
    renderTab();
  });
});

function renderTab() {
  const box = document.getElementById("tabContent");
  if (!currentDatasetId) {
    box.innerHTML = '<div class="card p-10 text-center"><p class="text-4xl mb-3">🔬</p><p class="font-medium text-stone-700">Select a dataset to begin</p></div>';
    return;
  }
  const cols = getSelectedColumns();
  if (activeTab === "correlation") return renderCorrelation(cols);
  if (activeTab === "vif") return renderVIF(cols);
  if (activeTab === "granger") return renderGranger(cols);
  if (activeTab === "descriptives") return renderDescriptives(cols);
}

// ========== Correlation ==========
async function renderCorrelation(cols) {
  const box = document.getElementById("tabContent");
  if (cols.length < 2) {
    box.innerHTML = '<div class="card p-6"><p class="text-sm text-stone-500">Select at least 2 columns.</p></div>';
    return;
  }
  box.innerHTML = '<div class="card p-8 text-center"><span class="spinner"></span><p class="text-sm mt-2">Computing...</p></div>';
  try {
    const res = await apiFetch("/api/econometrics/correlation", {
      method: "POST",
      body: { dataset_id: currentDatasetId, columns: cols },
    });
    box.innerHTML = `
      <div class="card p-6 mb-6">
        <h2 class="font-semibold text-stone-900 mb-1">Pearson Correlation Matrix</h2>
        <p class="text-xs text-stone-500 mb-4">n = ${res.n_obs} observations</p>
        ${renderCorrGrid(res.columns, res.pearson)}
      </div>
      <div class="card p-6 mb-6">
        <h2 class="font-semibold text-stone-900 mb-4">Spearman Correlation Matrix</h2>
        ${renderCorrGrid(res.columns, res.spearman)}
      </div>
      ${res.high_correlations.length ? `
        <div class="card p-6">
          <h2 class="font-semibold text-stone-900 mb-3">⚠ High Correlations (|r| ≥ 0.7)</h2>
          <div class="space-y-2">
            ${res.high_correlations.map(h => `
              <div class="p-3 rounded-md flex justify-between items-center" style="background:#fef3c7;border:1px solid #b45309">
                <span class="text-sm font-medium">${esc(h.var1)} ↔ ${esc(h.var2)}</span>
                <span class="text-xs">Pearson: <strong>${h.pearson}</strong> · Spearman: <strong>${h.spearman}</strong> · ${h.strength}</span>
              </div>
            `).join("")}
          </div>
        </div>
      ` : ''}
    `;
  } catch (e) {
    box.innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

function renderCorrGrid(columns, matrix) {
  const n = columns.length;
  const grid = `grid-template-columns: 140px repeat(${n}, minmax(72px, 1fr));`;
  let html = '<div class="overflow-auto"><div class="corr-grid" style="' + grid + '">';
  html += '<div class="hdr"></div>';
  columns.forEach(c => { html += `<div class="hdr">${esc(c)}</div>`; });
  columns.forEach(row => {
    html += `<div class="hdr" style="text-align:left">${esc(row)}</div>`;
    columns.forEach(col => {
      const v = matrix[row][col];
      html += `<div>${corrCell(v)}</div>`;
    });
  });
  html += '</div></div>';
  return html;
}

function corrCell(v) {
  if (v === null || v === undefined) return '<span class="corr-cell" style="background:#f5f5f4;color:#a8a29e">—</span>';
  const a = Math.abs(v);
  let bg = "#f5f5f4", fg = "#57534e";
  if (a >= 0.9) { bg = "#047857"; fg = "white"; }
  else if (a >= 0.7) { bg = "#65a30d"; fg = "white"; }
  else if (a >= 0.5) { bg = "#fcd34d"; fg = "#78350f"; }
  else if (a >= 0.3) { bg = "#fde68a"; fg = "#78350f"; }
  return `<span class="corr-cell" style="background:${bg};color:${fg}">${v.toFixed(3)}</span>`;
}

// ========== VIF ==========
async function renderVIF(cols) {
  const box = document.getElementById("tabContent");
  if (cols.length < 2) {
    box.innerHTML = '<div class="card p-6"><p class="text-sm text-stone-500">Select at least 2 columns.</p></div>';
    return;
  }
  box.innerHTML = '<div class="card p-8 text-center"><span class="spinner"></span><p class="text-sm mt-2">Computing VIF...</p></div>';
  try {
    const res = await apiFetch("/api/econometrics/vif", {
      method: "POST",
      body: { dataset_id: currentDatasetId, columns: cols },
    });
    box.innerHTML = `
      <div class="card p-6">
        <div class="flex justify-between items-center mb-4">
          <h2 class="font-semibold text-stone-900">Variance Inflation Factor</h2>
          <span class="text-xs text-stone-500">n = ${res.n_obs}</span>
        </div>
        <table class="data-table">
          <thead><tr><th>Variable</th><th style="text-align:right">VIF</th><th>Interpretation</th></tr></thead>
          <tbody>
            ${res.variables.map(v => {
              const color = v.vif == null ? "#a8a29e" : v.vif < 5 ? "#047857" : v.vif < 10 ? "#b45309" : "#b91c1c";
              return `<tr>
                <td><strong>${esc(v.variable)}</strong></td>
                <td style="text-align:right;font-weight:600;color:${color}">${v.vif == null ? "—" : v.vif.toFixed(2)}</td>
                <td>${esc(v.interpretation)}</td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>
        <div class="mt-4 text-xs text-stone-500">
          <p><strong>Rule of thumb:</strong> VIF &lt; 5 → OK · 5-10 → moderate · &gt; 10 → high multicollinearity</p>
          ${res.high_vif_count > 0 ? `<p class="text-red-600 mt-2"><strong>⚠ ${res.high_vif_count} variable(s) have high VIF: ${res.high_vif_vars.map(esc).join(", ")}</strong></p>` : '<p class="text-emerald-700 mt-2">✓ No high multicollinearity detected</p>'}
        </div>
      </div>
    `;
  } catch (e) {
    box.innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

// ========== Granger ==========
function renderGranger(cols) {
  const box = document.getElementById("tabContent");
  if (cols.length < 2) {
    box.innerHTML = '<div class="card p-6"><p class="text-sm text-stone-500">Select at least 2 columns.</p></div>';
    return;
  }
  box.innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 mb-4">Granger Causality Test</h2>
      <p class="text-xs text-stone-500 mb-4">"Does X help predict Y beyond Y's own past?"</p>
      <div class="grid grid-cols-3 gap-4">
        <div>
          <label class="label">Cause (X)</label>
          <select id="grangerCause" class="input">${cols.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")}</select>
        </div>
        <div>
          <label class="label">Effect (Y)</label>
          <select id="grangerEffect" class="input">${cols.filter(c => c !== cols[0]).map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")}</select>
        </div>
        <div>
          <label class="label">Max lag</label>
          <input id="grangerLag" type="number" min="1" max="20" value="5" class="input" />
        </div>
      </div>
      <button id="runGrangerBtn" class="btn-primary mt-4">Run Granger Test</button>
    </div>
    <div id="grangerResult"></div>
  `;
  document.getElementById("runGrangerBtn").addEventListener("click", runGranger);
}

async function runGranger() {
  const cause = document.getElementById("grangerCause").value;
  const effect = document.getElementById("grangerEffect").value;
  const lag = parseInt(document.getElementById("grangerLag").value) || 5;
  const box = document.getElementById("grangerResult");
  box.innerHTML = '<div class="card p-8 text-center"><span class="spinner"></span><p class="text-sm mt-2">Running Granger test...</p></div>';
  try {
    const res = await apiFetch("/api/econometrics/granger", {
      method: "POST",
      body: { dataset_id: currentDatasetId, cause, effect, max_lag: lag },
    });
    box.innerHTML = `
      <div class="card p-6 mb-6" style="background:${res.has_causality ? '#ecfdf5' : '#fef3c7'};border-color:${res.has_causality ? '#047857' : '#b45309'}">
        <p class="font-semibold text-lg">${res.has_causality ? '✓' : '⚠'} ${esc(res.interpretation)}</p>
        <p class="text-xs text-stone-600 mt-2">n = ${res.n_obs} observations · max lag = ${res.max_lag}</p>
      </div>
      <div class="card p-6">
        <h3 class="font-semibold text-stone-900 mb-4">Lag-wise Results</h3>
        <table class="data-table">
          <thead><tr>
            <th>Lag</th>
            <th style="text-align:right">F-stat</th>
            <th style="text-align:right">F p-value</th>
            <th style="text-align:right">Chi²</th>
            <th style="text-align:right">Chi² p-value</th>
            <th style="text-align:center">Significant?</th>
          </tr></thead>
          <tbody>
            ${res.results.map(r => `
              <tr>
                <td>${r.lag}</td>
                <td style="text-align:right">${r.f_stat ?? '—'}</td>
                <td style="text-align:right">${r.f_pvalue ?? '—'}</td>
                <td style="text-align:right">${r.chi2_stat ?? '—'}</td>
                <td style="text-align:right">${r.chi2_pvalue ?? '—'}</td>
                <td style="text-align:center">${r.is_significant ? '<span class="badge badge-emerald">yes</span>' : '<span class="badge badge-stone">no</span>'}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    box.innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

// ========== Descriptives ==========
async function renderDescriptives(cols) {
  const box = document.getElementById("tabContent");
  if (!cols.length) {
    box.innerHTML = '<div class="card p-6"><p class="text-sm text-stone-500">Select at least 1 column.</p></div>';
    return;
  }
  box.innerHTML = '<div class="card p-8 text-center"><span class="spinner"></span><p class="text-sm mt-2">Computing...</p></div>';
  try {
    const res = await apiFetch("/api/econometrics/descriptives", {
      method: "POST",
      body: { dataset_id: currentDatasetId, columns: cols },
    });
    box.innerHTML = `
      <div class="card p-6">
        <h2 class="font-semibold text-stone-900 mb-4">Descriptive Statistics</h2>
        <div class="overflow-auto">
          <table class="data-table">
            <thead><tr>
              <th>Variable</th><th style="text-align:right">N</th><th style="text-align:right">Mean</th>
              <th style="text-align:right">Median</th><th style="text-align:right">Std</th>
              <th style="text-align:right">Min</th><th style="text-align:right">Q1</th>
              <th style="text-align:right">Q3</th><th style="text-align:right">Max</th>
              <th style="text-align:right">Skew</th><th style="text-align:right">Kurt</th>
            </tr></thead>
            <tbody>
              ${res.variables.map(v => {
                if (v.error) return `<tr><td><strong>${esc(v.variable)}</strong></td><td colspan="10" class="text-red-600">${esc(v.error)}</td></tr>`;
                return `<tr>
                  <td><strong>${esc(v.variable)}</strong></td>
                  <td style="text-align:right">${v.n}</td>
                  <td style="text-align:right">${v.mean}</td>
                  <td style="text-align:right">${v.median}</td>
                  <td style="text-align:right">${v.std}</td>
                  <td style="text-align:right">${v.min}</td>
                  <td style="text-align:right">${v.q1}</td>
                  <td style="text-align:right">${v.q3}</td>
                  <td style="text-align:right">${v.max}</td>
                  <td style="text-align:right">${v.skewness ?? '—'}</td>
                  <td style="text-align:right">${v.kurtosis ?? '—'}</td>
                </tr>`;
              }).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } catch (e) {
    box.innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

loadDatasets();
document.addEventListener("neda:dataset-uploaded", () => loadDatasets());
