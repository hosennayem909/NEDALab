requireAuth();
renderSidebar("econ-adv");

let activeTab = "iv";
let currentDatasetId = null;
let columns = [];
let numericColumns = [];

// Roles: for each column → assign role
// IV tab: { y: "", endog: [], inst: [], exog: [] }
// Johansen/VECM: just a list of vars
const roles = {
  iv: { y: null, endog: [], inst: [], exog: [] },
  did: { y: null, treat: null, time: null },
  johansen: { vars: [] },
  vecm: { vars: [] },
};

async function loadDatasets() {
  const el = document.getElementById("dsSelect");
  try {
    const data = await apiFetch("/api/data/datasets");
    el.innerHTML = '<option value="">— Select dataset —</option>' +
      data.map(d => `<option value="${d.id}">${esc(d.filename)} (${d.row_count} rows)</option>`).join("");
  } catch (e) { el.innerHTML = '<option value="">Error</option>'; }
}

document.getElementById("dsSelect").addEventListener("change", async () => {
  const id = document.getElementById("dsSelect").value;
  if (!id) { currentDatasetId = null; return; }
  currentDatasetId = parseInt(id);
  try {
    const info = await apiFetch("/api/data/datasets/" + currentDatasetId + "/column-info");
    columns = info.all_columns;
    numericColumns = info.numeric_columns || [];
    document.getElementById("colCount").textContent =
      columns.length + " columns · " + numericColumns.length + " numeric";
    // Reset
    roles.iv = { y: null, endog: [], inst: [], exog: [] };
    roles.did = { y: null, treat: null, time: null };
    roles.johansen = { vars: [] };
    roles.vecm = { vars: [] };
    renderTab();
  } catch (e) { toast(e.message, "error"); }
});

document.querySelectorAll(".adv-tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".adv-tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeTab = btn.dataset.tab;
    renderTab();
  });
});

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function renderTab() {
  const box = document.getElementById("tabContent");
  if (!currentDatasetId) {
    box.innerHTML = '<div class="card p-10 text-center"><p class="text-4xl mb-3">🎓</p><p class="font-medium text-stone-700">Select a dataset to begin</p></div>';
    return;
  }

  if (activeTab === "iv") renderIVTab(box);
  else if (activeTab === "did") renderDiDTab(box);
  else if (activeTab === "johansen") renderJohansenTab(box);
  else if (activeTab === "vecm") renderVecmTab(box);
}

// ============================================================
// IV Tab — Stata-style role table
// ============================================================
function renderIVTab(box) {
  const rows = columns.map(c => {
    const isY = roles.iv.y === c;
    const isEndog = roles.iv.endog.includes(c);
    const isInst = roles.iv.inst.includes(c);
    const isExog = roles.iv.exog.includes(c);
    // Prevent same column in multiple roles: any column with a role other than Y disables Y radio
    const hasOtherRole = isEndog || isInst || isExog;

    return `
      <tr data-col="${esc(c)}">
        <td class="col-name">${esc(c)}</td>
        <td class="center">
          <input type="radio" name="iv-y" value="${esc(c)}" ${isY ? "checked" : ""} ${hasOtherRole ? "disabled" : ""} data-role="y" />
        </td>
        <td class="center">
          <input type="checkbox" ${isEndog ? "checked" : ""} ${isY ? "disabled" : ""} data-role="endog" />
        </td>
        <td class="center">
          <input type="checkbox" ${isInst ? "checked" : ""} ${isY ? "disabled" : ""} data-role="inst" />
        </td>
        <td class="center">
          <input type="checkbox" ${isExog ? "checked" : ""} ${isY ? "disabled" : ""} data-role="exog" />
        </td>
      </tr>
    `;
  }).join("");

  box.innerHTML = `
    <div class="card p-6 mb-4">
      <div class="flex justify-between items-center mb-4 flex-wrap gap-3">
        <div>
          <h2 class="font-semibold text-stone-900">Assign roles for IV (2SLS)</h2>
          <p class="text-xs text-stone-500 mt-1">
            Pick <b>1 Y</b> (radio) · <b>1+ endogenous</b> · <b>1+ instruments</b> · optionally exogenous controls.
          </p>
        </div>
        <input id="ivSearch" type="text" class="search-input" placeholder="🔍 Filter columns..." />
      </div>

      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:8px;max-height:420px">
        <table class="role-table" id="ivTable">
          <thead>
            <tr>
              <th>Column</th>
              <th class="center" style="width:80px">
                Y
                <p class="role-hint">Dependent</p>
              </th>
              <th class="center" style="width:120px">
                Endogenous
                <p class="role-hint">Correlated with error</p>
              </th>
              <th class="center" style="width:120px">
                Instrument
                <p class="role-hint">Excluded Z</p>
              </th>
              <th class="center" style="width:120px">
                Exogenous
                <p class="role-hint">Included controls</p>
              </th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>

      <div class="selected-summary mt-4" id="ivSummary"></div>

      <button id="runIvBtn" class="btn-primary mt-4">⚙️ Run IV Regression</button>
    </div>
  `;

  // Attach handlers
  document.querySelectorAll("#ivTable input[data-role]").forEach(inp => {
    inp.addEventListener("change", handleIVChange);
  });

  document.getElementById("ivSearch").addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    document.querySelectorAll("#ivTable tbody tr").forEach(tr => {
      const name = tr.dataset.col.toLowerCase();
      tr.style.display = !q || name.includes(q) ? "" : "none";
    });
  });

  document.getElementById("runIvBtn").addEventListener("click", runIV);
  updateIVSummary();
}

function handleIVChange(e) {
  const inp = e.target;
  const row = inp.closest("tr");
  const col = row.dataset.col;
  const role = inp.dataset.role;
  const isChecked = inp.checked;

  if (role === "y") {
    if (isChecked) {
      // Remove col from all multi-roles
      roles.iv.endog = roles.iv.endog.filter(c => c !== col);
      roles.iv.inst = roles.iv.inst.filter(c => c !== col);
      roles.iv.exog = roles.iv.exog.filter(c => c !== col);
      roles.iv.y = col;
    } else {
      roles.iv.y = null;
    }
  } else {
    if (isChecked) {
      // If this column was Y, unset Y
      if (roles.iv.y === col) roles.iv.y = null;
      // Add to the role list
      if (!roles.iv[role].includes(col)) roles.iv[role].push(col);
    } else {
      roles.iv[role] = roles.iv[role].filter(c => c !== col);
    }
  }
  renderIVTab(document.getElementById("tabContent"));
}

function updateIVSummary() {
  const s = document.getElementById("ivSummary");
  if (!s) return;
  const y = roles.iv.y;
  const endog = roles.iv.endog;
  const inst = roles.iv.inst;
  const exog = roles.iv.exog;
  const any = y || endog.length || inst.length || exog.length;
  if (!any) {
    s.innerHTML = '<span class="text-xs text-stone-500">No roles assigned yet. Click radio/checkboxes above.</span>';
    return;
  }
  s.innerHTML = `
    <div><span class="summary-label">Y</span><span class="summary-item">${y ? esc(y) : '—'}</span></div>
    <div><span class="summary-label">Endog</span>${endog.length ? endog.map(c => `<span class="summary-item">${esc(c)}</span>`).join(" ") : '<span class="summary-item" style="opacity:0.5">none</span>'}</div>
    <div><span class="summary-label">Inst</span>${inst.length ? inst.map(c => `<span class="summary-item">${esc(c)}</span>`).join(" ") : '<span class="summary-item" style="opacity:0.5">none</span>'}</div>
    <div><span class="summary-label">Exog</span>${exog.length ? exog.map(c => `<span class="summary-item">${esc(c)}</span>`).join(" ") : '<span class="summary-item" style="opacity:0.5">none</span>'}</div>
  `;
}

// ============================================================
// DiD Tab
// ============================================================
function renderDiDTab(box) {
  box.innerHTML = `
    <div class="card p-6">
      <h2 class="font-semibold text-stone-900 mb-2">Difference-in-Differences</h2>
      <p class="text-xs text-stone-500 mb-6">Estimates causal effect using treatment × post interaction.</p>
      <div class="grid grid-cols-3 gap-5 mb-5">
        <div>
          <label class="label">Outcome (Y)</label>
          <select id="didY" class="input">
            <option value="">— Select —</option>
            ${columns.map(c => `<option value="${esc(c)}"${roles.did.y === c ? " selected" : ""}>${esc(c)}</option>`).join("")}
          </select>
        </div>
        <div>
          <label class="label">Treatment column</label>
          <select id="didTreat" class="input">
            <option value="">— Select —</option>
            ${columns.map(c => `<option value="${esc(c)}"${roles.did.treat === c ? " selected" : ""}>${esc(c)}</option>`).join("")}
          </select>
          <p class="text-xs text-stone-500 mt-1">Categorical with exactly 2 values</p>
        </div>
        <div>
          <label class="label">Time column</label>
          <select id="didTime" class="input">
            <option value="">— Select —</option>
            ${columns.map(c => `<option value="${esc(c)}"${roles.did.time === c ? " selected" : ""}>${esc(c)}</option>`).join("")}
          </select>
          <p class="text-xs text-stone-500 mt-1">Date column for pre/post split</p>
        </div>
      </div>
      <div class="mb-5">
        <label class="label">Post period (optional — auto median if empty)</label>
        <input id="didPost" class="input" placeholder="YYYY-MM-DD" style="max-width:280px" />
      </div>
      <button id="runDidBtn" class="btn-primary">📊 Run DiD</button>
    </div>
  `;
  document.getElementById("didY").addEventListener("change", (e) => roles.did.y = e.target.value || null);
  document.getElementById("didTreat").addEventListener("change", (e) => roles.did.treat = e.target.value || null);
  document.getElementById("didTime").addEventListener("change", (e) => roles.did.time = e.target.value || null);
  document.getElementById("runDidBtn").addEventListener("click", runDiD);
}

// ============================================================
// Johansen Tab
// ============================================================
function renderJohansenTab(box) {
  renderMultiCheckTab(box, "johansen", "Johansen Cointegration Test",
    "Pick 2 or more numeric variables to test for long-run cointegrating relationships.",
    "🔗 Run Johansen");
}

function renderVecmTab(box) {
  renderMultiCheckTab(box, "vecm", "VECM (Vector Error Correction)",
    "Fit a VECM on cointegrated variables. Cointegration rank typically equals the number of significant relationships.",
    "🔄 Fit VECM");
}

function renderMultiCheckTab(box, mod, title, subtitle, runLabel) {
  const numCols = numericColumns.length ? numericColumns : columns;
  const rows = numCols.map(c => {
    const isSel = roles[mod].vars.includes(c);
    return `
      <tr data-col="${esc(c)}">
        <td class="col-name">${esc(c)}</td>
        <td class="center">
          <input type="checkbox" ${isSel ? "checked" : ""} data-role="vars" />
        </td>
      </tr>
    `;
  }).join("");

  const extra = mod === "johansen" ? `
    <div class="grid grid-cols-2 gap-4 mb-5">
      <div>
        <label class="label">Deterministic terms</label>
        <select id="joDet" class="input">
          <option value="0">0 — No deterministic</option>
          <option value="-1">-1 — Constant outside</option>
          <option value="1">1 — Constant inside</option>
        </select>
      </div>
      <div>
        <label class="label">Lag order (k_ar_diff)</label>
        <input id="joLag" type="number" min="1" max="10" value="1" class="input" />
      </div>
    </div>
  ` : `
    <div class="grid grid-cols-2 gap-4 mb-5">
      <div>
        <label class="label">Cointegration rank</label>
        <input id="vecmRank" type="number" min="1" value="1" class="input" />
      </div>
      <div>
        <label class="label">Lag order</label>
        <input id="vecmLag" type="number" min="1" max="10" value="1" class="input" />
      </div>
    </div>
  `;

  box.innerHTML = `
    <div class="card p-6">
      <div class="flex justify-between items-center mb-4 flex-wrap gap-3">
        <div>
          <h2 class="font-semibold text-stone-900">${title}</h2>
          <p class="text-xs text-stone-500 mt-1">${subtitle}</p>
        </div>
        <input id="${mod}Search" type="text" class="search-input" placeholder="🔍 Filter columns..." />
      </div>

      <div class="overflow-auto mb-5" style="border:1px solid #e7e5e4;border-radius:8px;max-height:360px">
        <table class="role-table" id="${mod}Table">
          <thead>
            <tr>
              <th>Column</th>
              <th class="center" style="width:100px">Include</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>

      ${extra}

      <div class="selected-summary mb-4" id="${mod}Summary"></div>

      <button id="run${mod}Btn" class="btn-primary">${runLabel}</button>
    </div>
  `;

  document.querySelectorAll(`#${mod}Table input[data-role="vars"]`).forEach(inp => {
    inp.addEventListener("change", () => {
      const col = inp.closest("tr").dataset.col;
      if (inp.checked) {
        if (!roles[mod].vars.includes(col)) roles[mod].vars.push(col);
      } else {
        roles[mod].vars = roles[mod].vars.filter(c => c !== col);
      }
      updateMultiSummary(mod);
    });
  });

  document.getElementById(`${mod}Search`).addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    document.querySelectorAll(`#${mod}Table tbody tr`).forEach(tr => {
      const name = tr.dataset.col.toLowerCase();
      tr.style.display = !q || name.includes(q) ? "" : "none";
    });
  });

  updateMultiSummary(mod);

  if (mod === "johansen") {
    document.getElementById("runjohansenBtn").addEventListener("click", runJohansen);
  } else {
    document.getElementById("runvecmBtn").addEventListener("click", runVECM);
  }
}

function updateMultiSummary(mod) {
  const s = document.getElementById(`${mod}Summary`);
  if (!s) return;
  const vars = roles[mod].vars;
  if (!vars.length) {
    s.innerHTML = '<span class="text-xs text-stone-500">No variables selected yet.</span>';
    return;
  }
  s.innerHTML = `
    <div><span class="summary-label">Selected (${vars.length})</span>
      ${vars.map(c => `<span class="summary-item">${esc(c)}</span>`).join(" ")}
    </div>
  `;
}

// ============================================================
// Runners
// ============================================================
async function runIV() {
  if (!roles.iv.y) { toast("Pick a Y variable (radio)", "warning"); return; }
  if (!roles.iv.endog.length) { toast("Pick at least 1 endogenous variable", "warning"); return; }
  if (!roles.iv.inst.length) { toast("Pick at least 1 instrument", "warning"); return; }
  await runRequest("/api/econometrics/iv", {
    dataset_id: currentDatasetId,
    dependent: roles.iv.y,
    endogenous: roles.iv.endog,
    instruments: roles.iv.inst,
    exogenous: roles.iv.exog.length ? roles.iv.exog : null,
  }, renderIV);
}

async function runDiD() {
  if (!roles.did.y || !roles.did.treat || !roles.did.time) {
    toast("Fill outcome, treatment, and time", "warning"); return;
  }
  const post = document.getElementById("didPost").value.trim() || null;
  await runRequest("/api/econometrics/did", {
    dataset_id: currentDatasetId,
    outcome: roles.did.y,
    treatment_col: roles.did.treat,
    time_col: roles.did.time,
    post_period: post,
  }, renderDiD);
}

async function runJohansen() {
  if (roles.johansen.vars.length < 2) { toast("Pick 2+ variables", "warning"); return; }
  await runRequest("/api/econometrics/johansen", {
    dataset_id: currentDatasetId,
    variables: roles.johansen.vars,
    det_order: parseInt(document.getElementById("joDet").value),
    k_ar_diff: parseInt(document.getElementById("joLag").value),
  }, renderJohansen);
}

async function runVECM() {
  if (roles.vecm.vars.length < 2) { toast("Pick 2+ variables", "warning"); return; }
  await runRequest("/api/econometrics/vecm", {
    dataset_id: currentDatasetId,
    variables: roles.vecm.vars,
    coint_rank: parseInt(document.getElementById("vecmRank").value),
    k_ar_diff: parseInt(document.getElementById("vecmLag").value),
  }, renderVECM);
}

async function runRequest(url, body, onSuccess) {
  document.getElementById("result").innerHTML = "";
  document.getElementById("loading").style.display = "block";
  try {
    const res = await apiFetch(url, { method: "POST", body });
    document.getElementById("loading").style.display = "none";
    onSuccess(res);
  } catch (e) {
    document.getElementById("loading").style.display = "none";
    document.getElementById("result").innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

// ============================================================
// Renderers
// ============================================================
function coefTable(coefs) {
  return `
    <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:6px">
      <table class="data-table">
        <thead><tr>
          <th>Variable</th><th style="text-align:right">Coef</th><th style="text-align:right">Std Err</th>
          <th style="text-align:right">t</th><th style="text-align:right">p&gt;|t|</th><th style="text-align:right">CI Lower</th>
          <th style="text-align:right">CI Upper</th><th style="text-align:center">Sig</th>
        </tr></thead>
        <tbody>
          ${coefs.map(c => `<tr>
            <td><strong>${esc(c.variable)}</strong></td>
            <td style="text-align:right">${c.coef ?? '—'}</td>
            <td style="text-align:right">${c.std_err ?? '—'}</td>
            <td style="text-align:right">${c.t_stat ?? '—'}</td>
            <td style="text-align:right">${c.p_value ?? '—'}</td>
            <td style="text-align:right">${c.ci_lower ?? '—'}</td>
            <td style="text-align:right">${c.ci_upper ?? '—'}</td>
            <td style="text-align:center;color:#047857;font-weight:700">${c.significance || '—'}</td>
          </tr>`).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderIV(r) {
  document.getElementById("result").innerHTML = `
    <div class="card p-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-1">IV (2SLS) Result</h2>
      <p class="text-xs text-stone-500 mb-4">n = ${r.n_obs} · R² = ${r.r_squared}</p>
      <div class="grid grid-cols-3 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">First-stage F</p><p class="stat-value">${r.diagnostics.first_stage_f_stat ?? '—'}</p></div>
        <div class="stat-card"><p class="stat-label">Sargan p</p><p class="stat-value">${r.diagnostics.sargan_pvalue ?? '—'}</p></div>
        <div class="stat-card"><p class="stat-label">R²</p><p class="stat-value">${r.r_squared}</p></div>
      </div>
      <p class="text-sm mb-4">${esc(r.interpretation.weak_instrument_note)}</p>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">Coefficients</h3>
      ${coefTable(r.coefficients)}
    </div>
  `;
}

function renderDiD(r) {
  const gm = r.group_means;
  document.getElementById("result").innerHTML = `
    <div class="card p-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-1">Difference-in-Differences</h2>
      <p class="text-xs text-stone-500 mb-4">n = ${r.n_obs} · R² = ${r.r_squared}</p>
      <div class="grid grid-cols-4 gap-3 mb-6">
        <div class="stat-card"><p class="stat-label">Control Pre</p><p class="stat-value">${gm.Control_Pre ?? '—'}</p></div>
        <div class="stat-card"><p class="stat-label">Control Post</p><p class="stat-value">${gm.Control_Post ?? '—'}</p></div>
        <div class="stat-card"><p class="stat-label">Treated Pre</p><p class="stat-value">${gm.Treated_Pre ?? '—'}</p></div>
        <div class="stat-card"><p class="stat-label">Treated Post</p><p class="stat-value">${gm.Treated_Post ?? '—'}</p></div>
      </div>
      <div class="p-4 rounded-md mb-6" style="background:#ecfdf5;border:1px solid #047857">
        <p class="text-sm font-medium">DiD Effect: <span style="font-size:20px;color:#047857">${r.did_effect ?? '—'}</span></p>
        <p class="text-xs text-stone-600 mt-1">${esc(r.interpretation.did_note)}</p>
      </div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">Regression Table</h3>
      ${coefTable(r.coefficients)}
    </div>
  `;
}

function renderJohansen(r) {
  document.getElementById("result").innerHTML = `
    <div class="card p-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-1">Johansen Cointegration Test</h2>
      <p class="text-xs text-stone-500 mb-4">n = ${r.n_obs} · Variables: ${r.variables.map(esc).join(", ")}</p>
      <div class="p-4 rounded-md mb-6" style="background:${r.cointegration_rank > 0 ? '#ecfdf5' : '#fef3c7'};border:1px solid ${r.cointegration_rank > 0 ? '#047857' : '#b45309'}">
        <p class="text-sm font-medium">Cointegration rank: <span style="font-size:22px">${r.cointegration_rank}</span></p>
        <p class="text-xs text-stone-600 mt-1">${esc(r.interpretation.cointegration_note)}</p>
      </div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">Trace Statistic</h3>
      <div class="overflow-auto mb-4" style="border:1px solid #e7e5e4;border-radius:6px">
        <table class="data-table">
          <thead><tr><th>H0</th><th style="text-align:right">Trace Stat</th><th style="text-align:right">Crit 90%</th><th style="text-align:right">Crit 95%</th><th style="text-align:right">Crit 99%</th><th>Reject 5%?</th></tr></thead>
          <tbody>
            ${r.trace_results.map(t => `<tr>
              <td>${esc(t.H0)}</td>
              <td style="text-align:right">${t.trace_stat}</td>
              <td style="text-align:right">${t.crit_90}</td>
              <td style="text-align:right">${t.crit_95}</td>
              <td style="text-align:right">${t.crit_99}</td>
              <td>${t.reject_5pct ? '<span class="badge badge-emerald">yes</span>' : '<span class="badge badge-stone">no</span>'}</td>
            </tr>`).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderVECM(r) {
  document.getElementById("result").innerHTML = `
    <div class="card p-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-1">VECM Result</h2>
      <p class="text-xs text-stone-500 mb-4">n = ${r.n_obs} · Rank = ${r.coint_rank} · Lag = ${r.k_ar_diff}</p>
      <div class="grid grid-cols-4 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">Log-Likelihood</p><p class="stat-value">${r.log_likelihood}</p></div>
        <div class="stat-card"><p class="stat-label">AIC</p><p class="stat-value">${r.aic}</p></div>
        <div class="stat-card"><p class="stat-label">BIC</p><p class="stat-value">${r.bic}</p></div>
        <div class="stat-card"><p class="stat-label">HQIC</p><p class="stat-value">${r.hqic}</p></div>
      </div>
    </div>
  `;
}

loadDatasets();
