requireAuth();
renderSidebar("panel");

let currentDatasetId = null;

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
    const all = info.all_columns;
    const numeric = info.numeric_columns;

    ["entityCol", "timeCol"].forEach(elId => {
      const el = document.getElementById(elId);
      el.disabled = false;
      el.innerHTML = '<option value="">— Select —</option>' + all.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
    });

    const dep = document.getElementById("depVar");
    dep.disabled = false;
    dep.innerHTML = '<option value="">— Select Y —</option>' + numeric.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("");

    const list = document.getElementById("indepList");
    list.innerHTML = numeric.map(c => `
      <label class="flex items-center gap-2 text-sm py-0.5 cursor-pointer">
        <input type="checkbox" class="indep-check" value="${esc(c)}" style="accent-color:#047857" />
        <span class="text-stone-700">${esc(c)}</span>
      </label>
    `).join("");
  } catch (e) { toast(e.message, "error"); }
});

document.getElementById("trainBtn").addEventListener("click", () => run("train"));
document.getElementById("hausmanBtn").addEventListener("click", () => run("hausman"));
document.getElementById("ftestBtn").addEventListener("click", () => run("ftest"));
document.getElementById("bpLmBtn").addEventListener("click", () => run("bplm"));

async function run(action) {
  if (!currentDatasetId) { toast("Select dataset", "warning"); return; }
  const entity = document.getElementById("entityCol").value;
  const time = document.getElementById("timeCol").value;
  const dep = document.getElementById("depVar").value;
  if (!entity || !time || !dep) { toast("Fill entity, time, and dependent", "warning"); return; }
  const indep = Array.from(document.querySelectorAll(".indep-check:checked")).map(c => c.value);
  if (!indep.length) { toast("Select at least one independent variable", "warning"); return; }
  if (indep.includes(dep)) { toast("Y cannot be in X", "warning"); return; }

  document.getElementById("empty").style.display = "none";
  document.getElementById("results").style.display = "none";
  document.getElementById("loading").style.display = "block";

  const body = {
    dataset_id: currentDatasetId,
    entity_col: entity, time_col: time,
    dependent_var: dep, independent_vars: indep,
  };

  try {
    if (action === "hausman") {
      const res = await apiFetch("/api/econometrics/panel/hausman", { method: "POST", body });
      renderHausman(res, entity, time, dep);
    } else if (action === "ftest") {
      const res = await apiFetch("/api/econometrics/panel/ftest-poolability", { method: "POST", body });
      renderFtest(res, entity, time, dep);
    } else if (action === "bplm") {
      const res = await apiFetch("/api/econometrics/panel/bp-lm", { method: "POST", body });
      renderBpLm(res, entity, time, dep);
    } else {
      const modelType = document.getElementById("modelType").value;
      body.model_type = modelType;
      const res = await apiFetch("/api/econometrics/panel/train", { method: "POST", body });
      renderResult(res, entity, time, dep, modelType);
    }
    document.getElementById("loading").style.display = "none";
    document.getElementById("results").style.display = "block";
  } catch (e) {
    document.getElementById("loading").style.display = "none";
    document.getElementById("empty").style.display = "block";
    toast(e.message, "error");
  }
}

function renderResult(r, entity, time, dep, modelType) {
  document.getElementById("results").innerHTML = `
    <div class="card p-6 mb-6">
      <div class="flex justify-between items-start mb-4 flex-wrap gap-2">
        <div>
          <h2 class="font-semibold text-stone-900 text-lg">Panel ${modelType.toUpperCase()}</h2>
          <p class="text-xs text-stone-500 mt-1">${esc(dep)} ~ ${r.independent_vars.map(esc).join(" + ")}</p>
          <p class="text-xs text-stone-500">Entity: ${esc(entity)} · Time: ${esc(time)}</p>
        </div>
        <span class="badge badge-emerald">${r.n_entities} entities · ${r.n_periods} periods</span>
      </div>
      <div class="grid grid-cols-4 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">R²</p><p class="stat-value">${r.r_squared ?? '—'}</p></div>
        <div class="stat-card"><p class="stat-label">R² (within)</p><p class="stat-value">${r.r_squared_within ?? '—'}</p></div>
        <div class="stat-card"><p class="stat-label">R² (between)</p><p class="stat-value">${r.r_squared_between ?? '—'}</p></div>
        <div class="stat-card"><p class="stat-label">N observations</p><p class="stat-value">${r.n_obs}</p></div>
      </div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Coefficients</h3>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:8px">
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
                <td style="text-align:right">${c.coef ?? '—'}</td>
                <td style="text-align:right">${c.std_err ?? '—'}</td>
                <td style="text-align:right">${c.t_stat ?? '—'}</td>
                <td style="text-align:right">${c.p_value != null && c.p_value < 0.001 ? '&lt;0.001' : (c.p_value ?? '—')}</td>
                <td style="text-align:right">${c.ci_lower ?? '—'}</td>
                <td style="text-align:right">${c.ci_upper ?? '—'}</td>
                <td style="text-align:center;font-weight:700;color:#047857">${c.significance || '—'}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
      <p class="text-xs text-stone-500 mt-2">Significance: *** p&lt;0.001 · ** p&lt;0.01 · * p&lt;0.05 · . p&lt;0.1</p>
    </div>
  `;
}

function renderHausman(r, entity, time, dep) {
  const color = r.recommendation === "fixed" ? "#b45309" : "#047857";
  document.getElementById("results").innerHTML = `
    <div class="card p-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-2">Hausman Test (FE vs RE)</h2>
      <p class="text-xs text-stone-500 mb-4">${esc(dep)} ~ ${entity} × ${time}</p>
      <div class="grid grid-cols-3 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">Chi² statistic</p><p class="stat-value">${r.chi2_statistic}</p></div>
        <div class="stat-card"><p class="stat-label">Degrees of freedom</p><p class="stat-value">${r.df}</p></div>
        <div class="stat-card"><p class="stat-label">p-value</p><p class="stat-value">${r.p_value}</p></div>
      </div>
      <div class="p-4 rounded-md" style="background:${color === '#047857' ? '#ecfdf5' : '#fef3c7'};border:1px solid ${color}">
        <p class="font-medium" style="color:${color}">Recommendation: ${r.recommendation.toUpperCase()}</p>
        <p class="text-sm text-stone-700 mt-1">${esc(r.interpretation)}</p>
      </div>
    </div>
  `;
}

function renderFtest(r, entity, time, dep) {
  const color = r.recommendation === "fixed" ? "#b45309" : "#047857";
  document.getElementById("results").innerHTML = `
    <div class="card p-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-2">F-test for Poolability</h2>
      <p class="text-xs text-stone-500 mb-4">${esc(dep)} ~ ${entity} × ${time}</p>
      <div class="grid grid-cols-3 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">F-statistic</p><p class="stat-value">${r.f_statistic}</p></div>
        <div class="stat-card"><p class="stat-label">df (num, den)</p><p class="stat-value">${r.df_num}, ${r.df_den}</p></div>
        <div class="stat-card"><p class="stat-label">p-value</p><p class="stat-value">${r.p_value}</p></div>
      </div>
      <div class="grid grid-cols-2 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">R² Pooled OLS</p><p class="stat-value">${r.r_squared_pooled}</p></div>
        <div class="stat-card"><p class="stat-label">R² Fixed Effects</p><p class="stat-value">${r.r_squared_fe}</p></div>
      </div>
      <div class="p-4 rounded-md" style="background:${color === '#047857' ? '#ecfdf5' : '#fef3c7'};border:1px solid ${color}">
        <p class="font-medium" style="color:${color}">Recommendation: ${r.recommendation.toUpperCase()}</p>
        <p class="text-sm text-stone-700 mt-1">${esc(r.interpretation)}</p>
      </div>
    </div>
  `;
}

function renderBpLm(r, entity, time, dep) {
  const color = r.recommendation === "random" ? "#b45309" : "#047857";
  document.getElementById("results").innerHTML = `
    <div class="card p-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-2">Breusch-Pagan LM Test</h2>
      <p class="text-xs text-stone-500 mb-4">${esc(dep)} ~ ${entity} × ${time}</p>
      <div class="grid grid-cols-3 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">LM statistic</p><p class="stat-value">${r.lm_statistic}</p></div>
        <div class="stat-card"><p class="stat-label">df</p><p class="stat-value">${r.df}</p></div>
        <div class="stat-card"><p class="stat-label">p-value</p><p class="stat-value">${r.p_value}</p></div>
      </div>
      <div class="grid grid-cols-3 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">Entities</p><p class="stat-value">${r.n_entities}</p></div>
        <div class="stat-card"><p class="stat-label">Periods</p><p class="stat-value">${r.n_periods}</p></div>
        <div class="stat-card"><p class="stat-label">Observations</p><p class="stat-value">${r.n_obs}</p></div>
      </div>
      <div class="p-4 rounded-md" style="background:${color === '#047857' ? '#ecfdf5' : '#fef3c7'};border:1px solid ${color}">
        <p class="font-medium" style="color:${color}">Recommendation: ${r.recommendation.toUpperCase()}</p>
        <p class="text-sm text-stone-700 mt-1">${esc(r.interpretation)}</p>
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