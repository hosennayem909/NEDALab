requireAuth();
renderSidebar("var");

let currentDatasetId = null;
let irfChart = null;

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
  if (!id) return;
  currentDatasetId = parseInt(id);
  try {
    const info = await apiFetch("/api/data/datasets/" + currentDatasetId + "/column-info");
    const num = info.numeric_columns || [];
    const box = document.getElementById("varList");
    box.innerHTML = num.map(c => `
      <label class="flex items-center gap-1.5 text-sm cursor-pointer">
        <input type="checkbox" class="var-check" value="${esc(c)}" style="accent-color:#047857" />
        <span class="text-stone-700">${esc(c)}</span>
      </label>
    `).join("");
  } catch (e) { toast(e.message, "error"); }
});

function getVars() {
  return Array.from(document.querySelectorAll(".var-check:checked")).map(c => c.value);
}
function getOpts() {
  return {
    dataset_id: currentDatasetId,
    variables: getVars(),
    max_lags: parseInt(document.getElementById("maxLags").value) || 5,
    lag_order: document.getElementById("lagOrder").value ? parseInt(document.getElementById("lagOrder").value) : null,
  };
}

document.getElementById("trainBtn").addEventListener("click", async () => {
  if (!currentDatasetId) { toast("Select dataset", "warning"); return; }
  const vars = getVars();
  if (vars.length < 2) { toast("Select 2 or more variables", "warning"); return; }
  showLoading();
  try {
    const res = await apiFetch("/api/econometrics/var/train", { method: "POST", body: getOpts() });
    renderTrain(res);
    showResults();
  } catch (e) { toast(e.message, "error"); showEmpty(); }
});

document.getElementById("irfBtn").addEventListener("click", async () => {
  if (!currentDatasetId) { toast("Select dataset", "warning"); return; }
  const vars = getVars();
  if (vars.length < 2) { toast("Select 2+ vars", "warning"); return; }
  showLoading();
  try {
    const opts = getOpts();
    opts.periods = parseInt(document.getElementById("irfPeriods").value) || 10;
    const res = await apiFetch("/api/econometrics/var/irf", { method: "POST", body: opts });
    renderIRF(res);
    showResults();
  } catch (e) { toast(e.message, "error"); showEmpty(); }
});

document.getElementById("fevdBtn").addEventListener("click", async () => {
  if (!currentDatasetId) { toast("Select dataset", "warning"); return; }
  const vars = getVars();
  if (vars.length < 2) { toast("Select 2+ vars", "warning"); return; }
  showLoading();
  try {
    const opts = getOpts();
    opts.periods = parseInt(document.getElementById("irfPeriods").value) || 10;
    const res = await apiFetch("/api/econometrics/var/fevd", { method: "POST", body: opts });
    renderFEVD(res);
    showResults();
  } catch (e) { toast(e.message, "error"); showEmpty(); }
});

function showLoading() {
  document.getElementById("empty").style.display = "none";
  document.getElementById("results").style.display = "none";
  document.getElementById("loading").style.display = "block";
}
function showResults() {
  document.getElementById("loading").style.display = "none";
  document.getElementById("results").style.display = "block";
}
function showEmpty() {
  document.getElementById("loading").style.display = "none";
  document.getElementById("empty").style.display = "block";
}

function renderTrain(r) {
  document.getElementById("results").innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-1">VAR(${r.lag_order}) Model</h2>
      <p class="text-xs text-stone-500">n = ${r.n_obs} · AIC: ${r.aic} · BIC: ${r.bic}</p>
      <div class="grid grid-cols-4 gap-3 my-4">
        <div class="stat-card"><p class="stat-label">Lag order</p><p class="stat-value">${r.lag_order}</p></div>
        <div class="stat-card"><p class="stat-label">AIC</p><p class="stat-value">${r.aic ?? '—'}</p></div>
        <div class="stat-card"><p class="stat-label">BIC</p><p class="stat-value">${r.bic ?? '—'}</p></div>
        <div class="stat-card"><p class="stat-label">Suggested lag (AIC)</p><p class="stat-value">${r.lag_selection?.aic ?? '—'}</p></div>
      </div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2 mt-4">Stationarity (ADF per variable)</h3>
      <div class="grid grid-cols-${Math.min(r.stationarity.length, 4)} gap-2 mb-4">
        ${r.stationarity.map(s => `
          <div class="p-3 rounded-md" style="background:${s.is_stationary ? '#ecfdf5' : '#fef3c7'};border:1px solid ${s.is_stationary ? '#047857' : '#b45309'}">
            <p class="text-xs text-stone-600">${esc(s.variable)}</p>
            <p class="font-medium text-sm">${s.is_stationary ? '✓ Stationary' : '⚠ Non-stationary'}</p>
            <p class="text-xs text-stone-500">p = ${s.p_value ?? '—'}</p>
          </div>
        `).join("")}
      </div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2 mt-6">Equations</h3>
      ${r.equations.map(eq => `
        <details class="mb-3" style="border:1px solid #e7e5e4;border-radius:6px">
          <summary class="p-3 cursor-pointer font-medium text-sm" style="background:#fafaf9">
            ${esc(eq.equation)} — R² = ${eq.r_squared}
          </summary>
          <div class="p-3">
            <table class="data-table">
              <thead><tr><th>Term</th><th style="text-align:right">Coef</th><th style="text-align:right">Std Err</th><th style="text-align:right">t</th><th style="text-align:right">p</th></tr></thead>
              <tbody>
                ${eq.params.map(p => `
                  <tr>
                    <td><strong>${esc(p.term)}</strong></td>
                    <td style="text-align:right">${p.coef ?? '—'}</td>
                    <td style="text-align:right">${p.std_err ?? '—'}</td>
                    <td style="text-align:right">${p.t_stat ?? '—'}</td>
                    <td style="text-align:right">${p.p_value ?? '—'}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </details>
      `).join("")}
    </div>
  `;
}

function renderIRF(r) {
  const shockKeys = Object.keys(r.irf);
  document.getElementById("results").innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-1">Impulse Response Functions</h2>
      <p class="text-xs text-stone-500">VAR(${r.lag_order}) · ${r.periods.length} periods</p>
      ${shockKeys.map(shock => `
        <div class="mt-6">
          <h3 class="text-sm font-medium mb-3">Shock to <span style="color:#047857">${esc(shock)}</span></h3>
          <div style="height:280px"><canvas id="irfChart-${shock.replace(/[^a-zA-Z0-9]/g, '_')}"></canvas></div>
        </div>
      `).join("")}
    </div>
  `;
  // Render each shock chart
  shockKeys.forEach(shock => {
    const canvasId = "irfChart-" + shock.replace(/[^a-zA-Z0-9]/g, "_");
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const datasets = r.irf[shock].map((resp, i) => {
      const colors = ["#047857", "#b45309", "#a855f7", "#06b6d4", "#ec4899", "#84cc16"];
      return {
        label: resp.response_var,
        data: resp.values,
        borderColor: colors[i % colors.length],
        backgroundColor: "transparent",
        borderWidth: 2,
        tension: 0.3,
        pointRadius: 2,
      };
    });
    new Chart(ctx, {
      type: "line",
      data: { labels: r.periods, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } },
        scales: {
          x: { title: { display: true, text: "Periods" }, grid: { color: "#e7e5e4" } },
          y: { grid: { color: "#e7e5e4" } },
        },
      },
    });
  });
}

function renderFEVD(r) {
  document.getElementById("results").innerHTML = `
    <div class="card p-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-1">Forecast Error Variance Decomposition</h2>
      <p class="text-xs text-stone-500">VAR(${r.lag_order}) · ${r.periods.length} periods</p>
      ${r.fevd.map(f => `
        <div class="mt-6">
          <h3 class="text-sm font-medium mb-3">Response: <span style="color:#047857">${esc(f.variable)}</span></h3>
          <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:6px">
            <table class="data-table">
              <thead><tr>
                <th>Period</th>
                ${r.variables.map(v => `<th style="text-align:right">${esc(v)}</th>`).join("")}
              </tr></thead>
              <tbody>
                ${f.decomposition.map(row => `
                  <tr>
                    <td>${row.period}</td>
                    ${r.variables.map(v => `<td style="text-align:right">${row[v] ?? '—'}%</td>`).join("")}
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>
      `).join("")}
    </div>
  `;
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

loadDatasets();
document.addEventListener("neda:dataset-uploaded", () => loadDatasets());
