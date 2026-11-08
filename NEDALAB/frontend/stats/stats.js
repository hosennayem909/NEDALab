requireAuth();
renderSidebar("stats");

async function loadDatasets() {
  const sel = document.getElementById("datasetSelect");
  try {
    const data = await apiFetch("/api/data/datasets");
    if (!data.length) {
      sel.innerHTML = '<option value="">No datasets - upload first</option>';
      return;
    }
    sel.innerHTML = '<option value="">- Select dataset -</option>' +
      data.map(d => `<option value="${d.id}">${esc(d.filename)} (${d.row_count} rows)</option>`).join("");
  } catch (e) {
    sel.innerHTML = '<option value="">Error loading</option>';
  }
}

document.getElementById("datasetSelect").addEventListener("change", async () => {
  const id = document.getElementById("datasetSelect").value;
  if (!id) { showEmpty(); return; }
  await analyze(id);
});

function showEmpty() {
  document.getElementById("content").style.display = "none";
  document.getElementById("loading").style.display = "none";
  document.getElementById("empty").style.display = "block";
}

async function analyze(id) {
  document.getElementById("empty").style.display = "none";
  document.getElementById("content").style.display = "none";
  document.getElementById("loading").style.display = "block";

  try {
    const data = await apiFetch("/api/data/datasets/" + id + "/stats-analyze");
    render(data);
    document.getElementById("loading").style.display = "none";
    document.getElementById("content").style.display = "block";
  } catch (e) {
    document.getElementById("loading").style.display = "none";
    toast(e.message, "error");
    showEmpty();
  }
}

function render(data) {
  const cols = data.columns || [];
  const totalIssues = cols.reduce((s, c) => s + c.outliers_iqr.count, 0);
  const skewed = cols.filter(c => Math.abs(c.distribution.skewness || 0) > 1).length;
  const nonNormal = cols.filter(c => c.distribution.is_normal === false).length;

  document.getElementById("summary").innerHTML = `
    <div class="stat-card"><p class="stat-label">Numeric Columns</p><p class="stat-value">${cols.length}</p></div>
    <div class="stat-card"><p class="stat-label">Highly Skewed</p><p class="stat-value">${skewed}</p></div>
    <div class="stat-card"><p class="stat-label">Outliers (IQR)</p><p class="stat-value">${totalIssues}</p></div>
  `;

  if (!cols.length) {
    document.getElementById("columnCards").innerHTML =
      '<div class="card p-8 text-center text-sm text-stone-500">No numeric columns found.</div>';
    return;
  }

  document.getElementById("columnCards").innerHTML = cols.map(c => renderColumn(c)).join("");
}

function renderColumn(c) {
  const d = c.distribution;
  const skew = d.skewness || 0;
  const skewColor = Math.abs(skew) < 0.5 ? "badge-emerald" : Math.abs(skew) < 1 ? "badge-amber" : "badge-red";
  const normBadge = d.is_normal === true ? '<span class="badge badge-emerald">normal</span>'
    : d.is_normal === false ? '<span class="badge badge-red">not normal</span>'
    : '<span class="badge badge-stone">n/a</span>';

  return `
    <div class="card p-6">
      <div class="flex justify-between items-start mb-4 pb-4 border-b" style="border-color:#e7e5e4">
        <div>
          <h3 class="font-semibold text-stone-900 text-lg">${esc(c.name)}</h3>
          <p class="text-xs text-stone-500">n = ${d.n} · ${d.skew_interpretation || ''}</p>
        </div>
        <div class="flex gap-2">
          <span class="badge ${skewColor}">skew ${skew.toFixed(2)}</span>
          ${normBadge}
        </div>
      </div>

      <div class="grid grid-cols-4 gap-3 mb-4">
        <div><p class="stat-label">Mean</p><p class="text-sm font-medium">${d.mean ?? '—'}</p></div>
        <div><p class="stat-label">Median</p><p class="text-sm font-medium">${d.median ?? '—'}</p></div>
        <div><p class="stat-label">Std</p><p class="text-sm font-medium">${d.std ?? '—'}</p></div>
        <div><p class="stat-label">CV %</p><p class="text-sm font-medium">${d.cv_pct ?? '—'}</p></div>
      </div>

      <div class="grid grid-cols-4 gap-3 mb-4">
        <div><p class="stat-label">Min</p><p class="text-sm">${d.min ?? '—'}</p></div>
        <div><p class="stat-label">Q1</p><p class="text-sm">${d.q25 ?? '—'}</p></div>
        <div><p class="stat-label">Q3</p><p class="text-sm">${d.q75 ?? '—'}</p></div>
        <div><p class="stat-label">Max</p><p class="text-sm">${d.max ?? '—'}</p></div>
      </div>

      <h4 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2 mt-4">Outlier detection</h4>
      <div class="grid grid-cols-3 gap-3">
        ${renderOutlier("IQR (1.5x)", c.outliers_iqr)}
        ${renderOutlier("Z-score (3σ)", c.outliers_zscore)}
        ${renderOutlier("MAD (3.5)", c.outliers_mad)}
      </div>
    </div>
  `;
}

function renderOutlier(label, o) {
  const cnt = o.count || 0;
  const color = cnt === 0 ? "#047857" : cnt > 10 ? "#b91c1c" : "#b45309";
  return `
    <div class="p-3 rounded-md" style="background:#fafaf9;border:1px solid #e7e5e4">
      <p class="text-xs text-stone-500 mb-1">${label}</p>
      <p class="text-lg font-bold" style="color:${color}">${cnt}</p>
      ${o.pct != null ? `<p class="text-xs text-stone-500">${o.pct}%</p>` : ''}
    </div>
  `;
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

loadDatasets();
