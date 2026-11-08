requireAuth();
renderSidebar("econometrics");

let currentDatasetId = null;
let numericColumns = [];

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

    const dep = document.getElementById("depSelect");
    dep.disabled = false;
    dep.innerHTML = '<option value="">— Select Y —</option>' +
      numericColumns.map(c => `<option value="${c}">${esc(c)}</option>`).join("");

    const list = document.getElementById("indepList");
    if (!numericColumns.length) {
      list.innerHTML = '<p class="text-xs text-stone-500">No numeric columns</p>';
      return;
    }
    list.innerHTML = numericColumns.map(c => `
      <label class="flex items-center gap-2 text-sm py-1 cursor-pointer">
        <input type="checkbox" class="indep-check" value="${esc(c)}" style="accent-color:#047857" />
        <span class="text-stone-700">${esc(c)}</span>
      </label>
    `).join("");
  } catch (e) {
    toast(e.message, "error");
  }
}

function resetColumns() {
  currentDatasetId = null;
  numericColumns = [];
  document.getElementById("depSelect").innerHTML = '<option value="">— Select dataset first —</option>';
  document.getElementById("depSelect").disabled = true;
  document.getElementById("indepList").innerHTML = '<p class="text-xs text-stone-500">Select dataset first</p>';
}

document.getElementById("trainBtn").addEventListener("click", async () => {
  if (!currentDatasetId) { toast("Select a dataset", "warning"); return; }
  const dep = document.getElementById("depSelect").value;
  if (!dep) { toast("Select dependent variable", "warning"); return; }

  const indep = Array.from(document.querySelectorAll(".indep-check:checked")).map(c => c.value);
  if (!indep.length) { toast("Select at least one independent variable", "warning"); return; }
  if (indep.includes(dep)) { toast("Y and X cannot be the same", "warning"); return; }

  const name = document.getElementById("modelName").value.trim() || null;

  document.getElementById("empty").style.display = "none";
  document.getElementById("results").style.display = "none";
  document.getElementById("loading").style.display = "block";

  try {
    const res = await apiFetch("/api/econometrics/ols/train", {
      method: "POST",
      body: {
        dataset_id: currentDatasetId,
        dependent_var: dep,
        independent_vars: indep,
        name: name,
        add_constant: true,
      },
    });
    renderResults(res);
    document.getElementById("loading").style.display = "none";
    document.getElementById("results").style.display = "block";
  } catch (e) {
    document.getElementById("loading").style.display = "none";
    document.getElementById("empty").style.display = "block";
    toast(e.message, "error");
  }
});

function renderResults(r) {
  const sigColor = (s) => s === "***" ? "#047857" : s === "**" ? "#047857" : s === "*" ? "#047857" : s === "." ? "#b45309" : "#a8a29e";
  const interp = r.interpretation || {};
  const resid = r.residual_stats || {};
  const vifData = resid.vif || [];
  const robustSE = interp.robust_se || [];

  document.getElementById("results").innerHTML = `
    <!-- Main Results -->
    <div class="card p-6 mb-6">
      <div class="flex justify-between items-start mb-4 flex-wrap gap-3">
        <div>
          <h2 class="font-semibold text-stone-900 text-lg">${esc(r.dependent_var)} = f(${r.independent_vars.map(esc).join(", ")})</h2>
          <p class="text-xs text-stone-500 mt-1">n = ${r.n_obs} observations</p>
        </div>
        <span class="badge badge-emerald">${esc(interp.r_squared_note || '')}</span>
      </div>

      <div class="grid grid-cols-4 gap-3 mb-6">
        <div class="stat-card"><p class="stat-label">R²</p><p class="stat-value">${r.r_squared.toFixed(4)}</p></div>
        <div class="stat-card"><p class="stat-label">Adj R²</p><p class="stat-value">${r.adj_r_squared.toFixed(4)}</p></div>
        <div class="stat-card"><p class="stat-label">F-stat</p><p class="stat-value">${r.f_statistic != null ? r.f_statistic.toFixed(2) : '—'}</p></div>
        <div class="stat-card"><p class="stat-label">DW</p><p class="stat-value">${r.durbin_watson != null ? r.durbin_watson.toFixed(2) : '—'}</p></div>
      </div>

      <!-- Standard Coefficients -->
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Standard Coefficients</h3>
      <div class="overflow-auto mb-6" style="border:1px solid #e7e5e4;border-radius:8px">
        <table class="data-table">
          <thead><tr>
            <th>Variable</th><th style="text-align:right">Coef</th><th style="text-align:right">Std Err</th>
            <th style="text-align:right">t</th><th style="text-align:right">p&gt;|t|</th>
            <th style="text-align:right">[0.025</th><th style="text-align:right">0.975]</th>
            <th style="text-align:center">Sig</th>
          </tr></thead>
          <tbody>
            ${r.coefficients.map(c => `
              <tr>
                <td><strong>${esc(c.variable)}</strong></td>
                <td style="text-align:right">${c.coef.toFixed(4)}</td>
                <td style="text-align:right">${c.std_err.toFixed(4)}</td>
                <td style="text-align:right">${c.t_stat.toFixed(3)}</td>
                <td style="text-align:right">${c.p_value < 0.001 ? '&lt;0.001' : c.p_value.toFixed(4)}</td>
                <td style="text-align:right">${c.ci_lower.toFixed(4)}</td>
                <td style="text-align:right">${c.ci_upper.toFixed(4)}</td>
                <td style="text-align:center;font-weight:700;color:${sigColor(c.significance)}">${c.significance || '—'}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
      <p class="text-xs text-stone-500">Significance: *** p&lt;0.001 · ** p&lt;0.01 · * p&lt;0.05 · . p&lt;0.1</p>
    </div>

    <!-- Robust Standard Errors -->
    ${robustSE.length ? `
    <div class="card p-6 mb-6">
      <h3 class="font-semibold text-stone-900 mb-3">Robust Standard Errors (HC1)</h3>
      <p class="text-xs text-stone-500 mb-3">Use these when heteroskedasticity is detected.</p>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:8px">
        <table class="data-table">
          <thead><tr>
            <th>Variable</th><th style="text-align:right">Robust SE</th><th style="text-align:right">Robust t</th>
            <th style="text-align:right">Robust p</th><th style="text-align:center">Sig</th>
          </tr></thead>
          <tbody>
            ${robustSE.map(c => `
              <tr>
                <td><strong>${esc(c.variable)}</strong></td>
                <td style="text-align:right">${c.robust_std_err != null ? c.robust_std_err.toFixed(4) : '—'}</td>
                <td style="text-align:right">${c.robust_t_stat != null ? c.robust_t_stat.toFixed(3) : '—'}</td>
                <td style="text-align:right">${c.robust_p_value != null ? (c.robust_p_value < 0.001 ? '&lt;0.001' : c.robust_p_value.toFixed(4)) : '—'}</td>
                <td style="text-align:center;font-weight:700;color:${sigColor(c.robust_significance)}">${c.robust_significance || '—'}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
    ` : ''}

    <!-- VIF / Multicollinearity -->
    ${vifData.length ? `
    <div class="card p-6 mb-6">
      <h3 class="font-semibold text-stone-900 mb-3">Multicollinearity (VIF)</h3>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:8px">
        <table class="data-table">
          <thead><tr>
            <th>Variable</th><th style="text-align:right">VIF</th><th>Warning</th>
          </tr></thead>
          <tbody>
            ${vifData.map(v => `
              <tr>
                <td><strong>${esc(v.variable)}</strong></td>
                <td style="text-align:right">${v.vif != null ? v.vif.toFixed(2) : '—'}</td>
                <td>${v.warning ? `<span style="color:#b45309;font-weight:600">${esc(v.warning)}</span>` : '<span style="color:#047857">OK</span>'}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
      <p class="text-xs text-stone-500 mt-2">VIF > 10 indicates severe multicollinearity.</p>
    </div>
    ` : ''}

    <!-- Model Interpretation -->
    <div class="card p-6 mb-6">
      <h3 class="font-semibold text-stone-900 mb-3">Model Interpretation</h3>
      <div class="space-y-2 text-sm">
        <p class="text-stone-700">📊 ${esc(interp.f_test_note || '')}</p>
        <p class="text-stone-700">📈 ${esc(interp.normality_note || '')}</p>
        <p class="text-stone-700">📉 ${esc(interp.heteroskedasticity_note || '')}</p>
        <p class="text-stone-700">🔄 ${esc(interp.autocorrelation_note || '')}</p>
        ${interp.breusch_godfrey_note ? `<p class="text-stone-700">🧪 ${esc(interp.breusch_godfrey_note)}</p>` : ''}
        ${interp.multicollinearity_note ? `<p class="text-stone-700">🔗 ${esc(interp.multicollinearity_note)}</p>` : ''}
      </div>
      ${(interp.significant_vars || []).length ? `
        <p class="text-xs text-stone-500 mt-4">Significant variables (p&lt;0.05): <strong class="text-stone-800">${interp.significant_vars.map(esc).join(", ")}</strong></p>
      ` : ''}
    </div>

    <!-- Residual Diagnostics -->
    <div class="card p-6">
      <h3 class="font-semibold text-stone-900 mb-3">Residual Diagnostics</h3>
      <div class="grid grid-cols-3 gap-3">
        <div class="p-3 rounded-md" style="background:#fafaf9;border:1px solid #e7e5e4">
          <p class="text-xs text-stone-500 mb-1">Skewness</p>
          <p class="text-lg font-bold text-stone-900">${resid.skewness ?? '—'}</p>
        </div>
        <div class="p-3 rounded-md" style="background:#fafaf9;border:1px solid #e7e5e4">
          <p class="text-xs text-stone-500 mb-1">Kurtosis</p>
          <p class="text-lg font-bold text-stone-900">${resid.kurtosis ?? '—'}</p>
        </div>
        <div class="p-3 rounded-md" style="background:#fafaf9;border:1px solid #e7e5e4">
          <p class="text-xs text-stone-500 mb-1">Jarque-Bera p</p>
          <p class="text-lg font-bold text-stone-900">${resid.jarque_bera_p ?? '—'}</p>
        </div>
        <div class="p-3 rounded-md" style="background:#fafaf9;border:1px solid #e7e5e4">
          <p class="text-xs text-stone-500 mb-1">Breusch-Pagan p</p>
          <p class="text-lg font-bold text-stone-900">${resid.bp_lm_p ?? '—'}</p>
        </div>
        <div class="p-3 rounded-md" style="background:#fafaf9;border:1px solid #e7e5e4">
          <p class="text-xs text-stone-500 mb-1">Breusch-Godfrey p</p>
          <p class="text-lg font-bold text-stone-900">${resid.bg_lm_p ?? '—'}</p>
        </div>
        <div class="p-3 rounded-md" style="background:#fafaf9;border:1px solid #e7e5e4">
          <p class="text-xs text-stone-500 mb-1">Resid Mean</p>
          <p class="text-lg font-bold text-stone-900">${resid.mean ?? '—'}</p>
        </div>
        <div class="p-3 rounded-md" style="background:#fafaf9;border:1px solid #e7e5e4">
          <p class="text-xs text-stone-500 mb-1">Resid Std</p>
          <p class="text-lg font-bold text-stone-900">${resid.std ?? '—'}</p>
        </div>
      </div>
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