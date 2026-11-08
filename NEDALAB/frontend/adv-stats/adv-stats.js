requireAuth();
renderSidebar("adv-stats");

let currentDatasetId = null;
let currentColumns = [];
let selectedMethod = null;

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
  if (!id) { showEmpty(); return; }
  currentDatasetId = parseInt(id);
  await loadColumns();
  document.getElementById("empty").style.display = "none";
  document.getElementById("workspace").style.display = "block";
  document.getElementById("preview").style.display = "none";
  document.getElementById("tsResult").style.display = "none";
  selectedMethod = null;
  document.querySelectorAll(".method-btn").forEach(b => { b.style.borderColor = "#e7e5e4"; b.style.background = ""; });
});

async function loadColumns() {
  try {
    const info = await apiFetch("/api/data/datasets/" + currentDatasetId + "/column-info");
    currentColumns = info.all_columns;
    const colSel = document.getElementById("columnSelect");
    colSel.innerHTML = '<option value="">— Select —</option>' + info.all_columns.map(c => `<option value="${c}">${esc(c)}</option>`).join("");
    const dateSel = document.getElementById("dateColSelect");
    const dateOpts = info.date_columns.length ? info.date_columns : info.all_columns;
    dateSel.innerHTML = '<option value="">— Select —</option>' + dateOpts.map(c => `<option value="${c}">${esc(c)}</option>`).join("");
    document.getElementById("columnWrap").style.display = "block";
  } catch (e) {
    toast(e.message, "error");
  }
}

document.querySelectorAll(".method-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    selectedMethod = btn.dataset.method;
    document.querySelectorAll(".method-btn").forEach(b => { b.style.borderColor = "#e7e5e4"; b.style.background = ""; });
    btn.style.borderColor = "#047857";
    btn.style.background = "#ecfdf5";
    const col = document.getElementById("columnSelect").value;
    if (!col) { toast("Select a column first", "warning"); return; }
    previewTransform(col, selectedMethod);
  });
});

document.getElementById("columnSelect").addEventListener("change", () => {
  if (selectedMethod) {
    const col = document.getElementById("columnSelect").value;
    if (col) previewTransform(col, selectedMethod);
  }
});

async function previewTransform(column, method) {
  const box = document.getElementById("preview");
  const body = document.getElementById("previewBody");
  box.style.display = "block";
  body.innerHTML = '<div style="display:flex;align-items:center;gap:10px;color:#78716c"><span class="spinner"></span> Computing...</div>';
  try {
    const res = await apiFetch(`/api/data/datasets/${currentDatasetId}/transform-preview`, {
      method: "POST",
      body: { column, method, lower_pct: 1.0, upper_pct: 99.0 },
    });
    const b = res.before || {}, a = res.after || {};
    body.innerHTML = `
      <div class="grid grid-cols-2 gap-4 mb-4">
        <div class="p-3 rounded-md" style="background:#fafaf9;border:1px solid #e7e5e4">
          <p class="text-xs text-stone-500 mb-2 font-medium">BEFORE</p>
          ${statRow("Mean", b.mean)} ${statRow("Std", b.std)} ${statRow("Median", b.median)}
          ${statRow("Skewness", b.skewness)} ${statRow("Kurtosis", b.kurtosis)}
          ${statRow("Min", b.min)} ${statRow("Max", b.max)}
        </div>
        <div class="p-3 rounded-md" style="background:#ecfdf5;border:1px solid #047857">
          <p class="text-xs text-stone-500 mb-2 font-medium">AFTER</p>
          ${statRow("Mean", a.mean)} ${statRow("Std", a.std)} ${statRow("Median", a.median)}
          ${statRow("Skewness", a.skewness)} ${statRow("Kurtosis", a.kurtosis)}
          ${statRow("Min", a.min)} ${statRow("Max", a.max)}
        </div>
      </div>
      <p class="text-xs text-stone-500 mb-4">${esc(JSON.stringify(res.meta))}</p>
      <button id="applyTransformBtn" class="btn-primary">Apply & Save as new dataset</button>
    `;
    document.getElementById("applyTransformBtn").addEventListener("click", () => applyTransform(column, method));
  } catch (e) {
    body.innerHTML = '<p class="text-sm text-red-600">' + esc(e.message) + '</p>';
  }
}

function statRow(label, val) {
  return `<div style="display:flex;justify-content:space-between;font-size:13px;padding:2px 0">
    <span class="text-stone-600">${label}</span>
    <span class="font-medium text-stone-900">${val == null ? "—" : val}</span>
  </div>`;
}

async function applyTransform(column, method) {
  const btn = document.getElementById("applyTransformBtn");
  if (btn) { btn.disabled = true; btn.textContent = "Applying..."; }
  try {
    const res = await apiFetch(`/api/data/datasets/${currentDatasetId}/transform-apply`, {
      method: "POST",
      body: { column, method, lower_pct: 1.0, upper_pct: 99.0, save_as_new: true },
    });
    toast("Transform applied", "success");
    await loadDatasets();
  } catch (e) {
    toast(e.message, "error");
    if (btn) { btn.disabled = false; btn.textContent = "Apply & Save as new dataset"; }
  }
}

document.getElementById("analyzeTsBtn").addEventListener("click", async () => {
  const dateCol = document.getElementById("dateColSelect").value;
  const valueCol = document.getElementById("columnSelect").value;
  if (!dateCol || !valueCol) { toast("Select date column and value column", "warning"); return; }
  const box = document.getElementById("tsResult");
  const body = document.getElementById("tsBody");
  box.style.display = "block";
  body.innerHTML = '<div style="display:flex;align-items:center;gap:10px;color:#78716c"><span class="spinner"></span> Analyzing...</div>';
  try {
    const res = await apiFetch(`/api/data/datasets/${currentDatasetId}/timeseries-analyze?date_column=${encodeURIComponent(dateCol)}&value_column=${encodeURIComponent(valueCol)}`);
    const g = res.gaps, s = res.stationarity;
    body.innerHTML = `
      <div class="grid grid-cols-2 gap-4">
        <div class="p-4 rounded-md" style="background:#fafaf9;border:1px solid #e7e5e4">
          <h3 class="font-medium text-sm mb-2">Gap Detection</h3>
          <p class="text-2xl font-bold" style="color:${g.gap_count > 0 ? '#b91c1c' : '#047857'}">${g.gap_count ?? 0}</p>
          <p class="text-xs text-stone-500">missing dates</p>
          <p class="text-xs text-stone-500 mt-2">Expected: ${g.expected ?? '—'} · Actual: ${g.actual ?? '—'}</p>
          ${g.date_min ? `<p class="text-xs text-stone-500">Range: ${g.date_min} → ${g.date_max}</p>` : ''}
        </div>
        <div class="p-4 rounded-md" style="background:${s.is_stationary ? '#ecfdf5' : '#fef3c7'};border:1px solid ${s.is_stationary ? '#047857' : '#b45309'}">
          <h3 class="font-medium text-sm mb-2">Stationarity (ADF test)</h3>
          <p class="text-lg font-bold">${s.is_stationary ? '✓ Stationary' : '⚠ Non-stationary'}</p>
          <p class="text-xs text-stone-600 mt-1">p-value: ${s.p_value ?? '—'}</p>
          <p class="text-xs text-stone-600">ADF: ${s.adf_statistic ?? '—'}</p>
          <p class="text-xs text-stone-500 mt-2">${esc(s.interpretation || '')}</p>
        </div>
      </div>
    `;
  } catch (e) {
    body.innerHTML = '<p class="text-sm text-red-600">' + esc(e.message) + '</p>';
  }
});

document.getElementById("fillGapsBtn").addEventListener("click", async () => {
  const dateCol = document.getElementById("dateColSelect").value;
  if (!dateCol) { toast("Select date column", "warning"); return; }
  const freq = document.getElementById("freqSelect").value;
  const method = document.getElementById("fillMethodSelect").value;
  try {
    const res = await apiFetch(`/api/data/datasets/${currentDatasetId}/timeseries-fill`, {
      method: "POST",
      body: { date_column: dateCol, frequency: freq, method, value_columns: null },
    });
    toast("Gaps filled · " + res.output_filename, "success");
    await loadDatasets();
  } catch (e) { toast(e.message, "error"); }
});

document.getElementById("diffBtn").addEventListener("click", async () => {
  const col = document.getElementById("columnSelect").value;
  if (!col) { toast("Select a numeric column", "warning"); return; }
  try {
    const res = await apiFetch(`/api/data/datasets/${currentDatasetId}/difference`, {
      method: "POST",
      body: { column: col, order: 1, save_as_new: true },
    });
    toast("Differencing applied", "success");
    await loadDatasets();
  } catch (e) { toast(e.message, "error"); }
});

function showEmpty() {
  document.getElementById("empty").style.display = "block";
  document.getElementById("workspace").style.display = "none";
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

loadDatasets();
document.addEventListener("neda:dataset-uploaded", () => loadDatasets());
