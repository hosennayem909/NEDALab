requireAuth();
renderSidebar("hypothesis");

let activeTest = "ttest";
let currentDatasetId = null;
let columns = [];
let numericColumns = [];
let categoricalColumns = [];

async function loadDatasets() {
  const sel = document.getElementById("dsSelect");
  try {
    const data = await apiFetch("/api/data/datasets");
    if (!data.length) { sel.innerHTML = '<option value="">No datasets</option>'; return; }
    sel.innerHTML = '<option value="">— Select dataset —</option>' +
      data.map(d => `<option value="${d.id}">${esc(d.filename)} (${d.row_count} rows)</option>`).join("");
  } catch (e) { sel.innerHTML = '<option value="">Error</option>'; }
}

document.getElementById("dsSelect").addEventListener("change", async () => {
  const id = document.getElementById("dsSelect").value;
  if (!id) { currentDatasetId = null; return; }
  currentDatasetId = parseInt(id);
  try {
    const info = await apiFetch("/api/data/datasets/" + currentDatasetId + "/column-info");
    columns = info.all_columns;
    numericColumns = info.numeric_columns || [];
    categoricalColumns = columns.filter(c => !numericColumns.includes(c));
    renderTab();
  } catch (e) { toast(e.message, "error"); }
});

document.querySelectorAll(".hyp-tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".hyp-tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeTest = btn.dataset.test;
    renderTab();
  });
});

function opts(arr, selected) {
  return arr.map(c => `<option value="${esc(c)}"${c === selected ? " selected" : ""}>${esc(c)}</option>`).join("");
}

function renderTab() {
  const box = document.getElementById("tabContent");
  if (!currentDatasetId) {
    box.innerHTML = '<div class="card p-10 text-center"><p class="text-4xl mb-3">🧪</p><p class="font-medium text-stone-700">Select a dataset to begin</p></div>';
    return;
  }

  if (activeTest === "ttest") {
    box.innerHTML = `
      <div class="card p-6">
        <h2 class="font-semibold text-stone-900 mb-4">t-Test</h2>
        <div class="mb-4">
          <label class="label">Test variant</label>
          <select id="tvVariant" class="input" style="max-width:300px">
            <option value="one_sample">One-sample t-test</option>
            <option value="two_sample">Two-sample (independent)</option>
            <option value="paired">Paired t-test</option>
          </select>
        </div>
        <div id="tVariantConfig"></div>
        <button id="runBtn" class="btn-primary mt-4">Run Test</button>
      </div>
    `;
    document.getElementById("tvVariant").addEventListener("change", renderTVariant);
    renderTVariant();
  } else if (activeTest === "anova") {
    box.innerHTML = `
      <div class="card p-6">
        <h2 class="font-semibold text-stone-900 mb-4">One-way ANOVA</h2>
        <div class="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label class="label">Numeric column (Y)</label>
            <select id="aCol" class="input">${opts(numericColumns)}</select>
          </div>
          <div>
            <label class="label">Group column (categorical)</label>
            <select id="aGroup" class="input">${opts(categoricalColumns)}</select>
          </div>
        </div>
        <button id="runBtn" class="btn-primary">Run ANOVA</button>
      </div>
    `;
    document.getElementById("runBtn").addEventListener("click", () => runTest("/api/econometrics/hypothesis/anova", {
      dataset_id: currentDatasetId,
      column: document.getElementById("aCol").value,
      group_column: document.getElementById("aGroup").value,
    }, renderGeneral));
  } else if (activeTest === "chisquare") {
    box.innerHTML = `
      <div class="card p-6">
        <h2 class="font-semibold text-stone-900 mb-4">Chi-Square Test of Independence</h2>
        <div class="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label class="label">Column A (categorical)</label>
            <select id="cA" class="input">${opts(categoricalColumns)}</select>
          </div>
          <div>
            <label class="label">Column B (categorical)</label>
            <select id="cB" class="input">${opts(categoricalColumns)}</select>
          </div>
        </div>
        <button id="runBtn" class="btn-primary">Run Chi-Square</button>
      </div>
    `;
    document.getElementById("runBtn").addEventListener("click", () => runTest("/api/econometrics/hypothesis/chi-square", {
      dataset_id: currentDatasetId,
      column_a: document.getElementById("cA").value,
      column_b: document.getElementById("cB").value,
    }, renderGeneral));
  } else if (activeTest === "mannwhitney") {
    box.innerHTML = `
      <div class="card p-6">
        <h2 class="font-semibold text-stone-900 mb-4">Mann-Whitney U Test</h2>
        <p class="text-xs text-stone-500 mb-4">Non-parametric alternative to two-sample t-test. Group column must have exactly 2 values.</p>
        <div class="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label class="label">Numeric column</label>
            <select id="mCol" class="input">${opts(numericColumns)}</select>
          </div>
          <div>
            <label class="label">Group column (2 values)</label>
            <select id="mGroup" class="input">${opts(categoricalColumns)}</select>
          </div>
        </div>
        <button id="runBtn" class="btn-primary">Run Mann-Whitney</button>
      </div>
    `;
    document.getElementById("runBtn").addEventListener("click", () => runTest("/api/econometrics/hypothesis/mann-whitney", {
      dataset_id: currentDatasetId,
      column: document.getElementById("mCol").value,
      group_column: document.getElementById("mGroup").value,
    }, renderGeneral));
  } else if (activeTest === "kruskal") {
    box.innerHTML = `
      <div class="card p-6">
        <h2 class="font-semibold text-stone-900 mb-4">Kruskal-Wallis H Test</h2>
        <p class="text-xs text-stone-500 mb-4">Non-parametric alternative to one-way ANOVA. Compares 2+ groups.</p>
        <div class="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label class="label">Numeric column</label>
            <select id="kCol" class="input">${opts(numericColumns)}</select>
          </div>
          <div>
            <label class="label">Group column</label>
            <select id="kGroup" class="input">${opts(categoricalColumns)}</select>
          </div>
        </div>
        <button id="runBtn" class="btn-primary">Run Kruskal-Wallis</button>
      </div>
    `;
    document.getElementById("runBtn").addEventListener("click", () => runTest("/api/econometrics/hypothesis/kruskal-wallis", {
      dataset_id: currentDatasetId,
      column: document.getElementById("kCol").value,
      group_column: document.getElementById("kGroup").value,
    }, renderGeneral));
  } else if (activeTest === "shapiro") {
    box.innerHTML = `
      <div class="card p-6">
        <h2 class="font-semibold text-stone-900 mb-4">Shapiro-Wilk Normality Test</h2>
        <p class="text-xs text-stone-500 mb-4">Tests whether data follows a normal distribution.</p>
        <div class="mb-4">
          <label class="label">Numeric column</label>
          <select id="sCol" class="input" style="max-width:400px">${opts(numericColumns)}</select>
        </div>
        <button id="runBtn" class="btn-primary">Run Shapiro-Wilk</button>
      </div>
    `;
    document.getElementById("runBtn").addEventListener("click", () => runTest("/api/econometrics/hypothesis/shapiro", {
      dataset_id: currentDatasetId,
      column: document.getElementById("sCol").value,
    }, renderGeneral));
  } else if (activeTest === "levene") {
    box.innerHTML = `
      <div class="card p-6">
        <h2 class="font-semibold text-stone-900 mb-4">Levene's Test for Equal Variances</h2>
        <p class="text-xs text-stone-500 mb-4">Tests whether variances are equal across groups (assumption for ANOVA).</p>
        <div class="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label class="label">Numeric column</label>
            <select id="lCol" class="input">${opts(numericColumns)}</select>
          </div>
          <div>
            <label class="label">Group column</label>
            <select id="lGroup" class="input">${opts(categoricalColumns)}</select>
          </div>
        </div>
        <button id="runBtn" class="btn-primary">Run Levene's Test</button>
      </div>
    `;
    document.getElementById("runBtn").addEventListener("click", () => runTest("/api/econometrics/hypothesis/levene", {
      dataset_id: currentDatasetId,
      column: document.getElementById("lCol").value,
      group_column: document.getElementById("lGroup").value,
    }, renderGeneral));
  } else if (activeTest === "correlation") {
    box.innerHTML = `
      <div class="card p-6">
        <h2 class="font-semibold text-stone-900 mb-4">Correlation Analysis (Pearson / Spearman)</h2>
        <p class="text-xs text-stone-500 mb-4">Checks the strength and direction of the relationship between two numeric variables.</p>
        <div class="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label class="label">Numeric Column A (X)</label>
            <select id="corrA" class="input">${opts(numericColumns)}</select>
          </div>
          <div>
            <label class="label">Numeric Column B (Y)</label>
            <select id="corrB" class="input">${opts(numericColumns, numericColumns[1])}</select>
          </div>
        </div>
        <button id="runBtn" class="btn-primary">Run Correlation</button>
      </div>
    `;
    document.getElementById("runBtn").addEventListener("click", () => runTest("/api/econometrics/hypothesis/correlation", {
      dataset_id: currentDatasetId,
      column_a: document.getElementById("corrA").value,
      column_b: document.getElementById("corrB").value,
    }, renderGeneral));
  } else if (activeTest === "tukey") {
    box.innerHTML = `
      <div class="card p-6">
        <h2 class="font-semibold text-stone-900 mb-4">Tukey HSD (Post-hoc Test)</h2>
        <p class="text-xs text-stone-500 mb-4">Used after ANOVA to find exactly which groups differ from each other.</p>
        <div class="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label class="label">Numeric column (Y)</label>
            <select id="tukeyCol" class="input">${opts(numericColumns)}</select>
          </div>
          <div>
            <label class="label">Group column (categorical)</label>
            <select id="tukeyGroup" class="input">${opts(categoricalColumns)}</select>
          </div>
        </div>
        <button id="runBtn" class="btn-primary">Run Tukey HSD</button>
      </div>
    `;
    document.getElementById("runBtn").addEventListener("click", () => runTest("/api/econometrics/hypothesis/tukey-hsd", {
      dataset_id: currentDatasetId,
      column: document.getElementById("tukeyCol").value,
      group_column: document.getElementById("tukeyGroup").value,
    }, renderTukey));
  }
}

function renderTVariant() {
  const v = document.getElementById("tvVariant").value;
  const box = document.getElementById("tVariantConfig");
  if (v === "one_sample") {
    box.innerHTML = `
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="label">Numeric column</label>
          <select id="tCol" class="input">${opts(numericColumns)}</select>
        </div>
        <div>
          <label class="label">Population mean (null)</label>
          <input id="tPopmean" type="number" step="any" value="0" class="input" />
        </div>
      </div>
    `;
  } else if (v === "two_sample") {
    box.innerHTML = `
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="label">Numeric column</label>
          <select id="tCol" class="input">${opts(numericColumns)}</select>
        </div>
        <div>
          <label class="label">Group column (2 values)</label>
          <select id="tGroup" class="input">${opts(categoricalColumns)}</select>
        </div>
      </div>
    `;
  } else {
    box.innerHTML = `
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="label">Column A (numeric)</label>
          <select id="tColA" class="input">${opts(numericColumns)}</select>
        </div>
        <div>
          <label class="label">Column B (numeric)</label>
          <select id="tColB" class="input">${opts(numericColumns, numericColumns[1])}</select>
        </div>
      </div>
    `;
  }
}

document.addEventListener("click", (e) => {
  if (e.target.id !== "runBtn") return;
  if (activeTest === "ttest") {
    const v = document.getElementById("tvVariant").value;
    let body = { dataset_id: currentDatasetId, test_variant: v };
    if (v === "one_sample") {
      body.column = document.getElementById("tCol").value;
      body.popmean = parseFloat(document.getElementById("tPopmean").value);
    } else if (v === "two_sample") {
      body.column = document.getElementById("tCol").value;
      body.group_column = document.getElementById("tGroup").value;
    } else {
      body.column_a = document.getElementById("tColA").value;
      body.column_b = document.getElementById("tColB").value;
    }
    runTest("/api/econometrics/hypothesis/t-test", body, renderGeneral);
  }
});

async function runTest(url, body, renderer) {
  document.getElementById("result").innerHTML = "";
  document.getElementById("loading").style.display = "block";
  try {
    const res = await apiFetch(url, { method: "POST", body });
    document.getElementById("loading").style.display = "none";
    renderer(res);
  } catch (e) {
    document.getElementById("loading").style.display = "none";
    document.getElementById("result").innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

// ============================================================
// Effect Size Card Builder
// ============================================================
function buildEffectSizeSection(r) {
  const effects = [];

  // Cohen's d
  if (r.cohens_d !== undefined && r.cohens_d !== null) {
    effects.push({
      name: "Cohen's d",
      value: r.cohens_d,
      interpretation: r.cohens_d_interpretation,
    });
  }

  // Hedges' g
  if (r.hedges_g !== undefined && r.hedges_g !== null) {
    effects.push({
      name: "Hedges' g",
      value: r.hedges_g,
      interpretation: r.hedges_g_interpretation,
    });
  }

  // Eta-squared
  if (r.eta_squared !== undefined && r.eta_squared !== null) {
    effects.push({
      name: "Eta-squared (η²)",
      value: r.eta_squared,
      interpretation: r.eta_squared_interpretation,
    });
  }

  // Omega-squared
  if (r.omega_squared !== undefined && r.omega_squared !== null) {
    effects.push({
      name: "Omega-squared (ω²)",
      value: r.omega_squared,
      interpretation: r.omega_squared_interpretation,
    });
  }

  // Cramér's V
  if (r.cramers_v !== undefined && r.cramers_v !== null) {
    effects.push({
      name: "Cramér's V",
      value: r.cramers_v,
      interpretation: r.cramers_v_interpretation,
    });
  }

  // Odds Ratio
  if (r.odds_ratio !== undefined && r.odds_ratio !== null) {
    effects.push({
      name: "Odds Ratio",
      value: r.odds_ratio,
      interpretation: r.odds_ratio > 1 ? "Positive association" : (r.odds_ratio < 1 ? "Negative association" : "No association"),
    });
  }

  // Rank-Biserial
  if (r.rank_biserial !== undefined && r.rank_biserial !== null) {
    effects.push({
      name: "Rank-Biserial r",
      value: r.rank_biserial,
      interpretation: r.rank_biserial_interpretation,
    });
  }

  // Epsilon-squared
  if (r.epsilon_squared !== undefined && r.epsilon_squared !== null) {
    effects.push({
      name: "Epsilon-squared (ε²)",
      value: r.epsilon_squared,
      interpretation: r.epsilon_squared_interpretation,
    });
  }

  // R-squared
  if (r.r_squared !== undefined && r.r_squared !== null) {
    effects.push({
      name: "R-squared (r²)",
      value: r.r_squared,
      interpretation: r.r_squared_interpretation,
    });
  }

  if (!effects.length) return "";

  return `
    <div class="card p-6 mb-6" style="border-left: 4px solid #047857">
      <h3 class="font-semibold text-stone-900 mb-3">📏 Effect Size Measures</h3>
      <p class="text-xs text-stone-500 mb-4">Effect size tells you how <em>large</em> the difference or relationship is — not just whether it exists.</p>
      <div class="grid grid-cols-2 gap-3">
        ${effects.map(e => `
          <div class="p-3 rounded-md" style="background:#f0fdf4;border:1px solid #bbf7d0">
            <p class="text-xs text-stone-500 mb-1">${esc(e.name)}</p>
            <p class="text-xl font-bold text-stone-900">${e.value}</p>
            ${e.interpretation ? `<p class="text-xs mt-1" style="color:#047857;font-weight:600">${esc(e.interpretation)}</p>` : ''}
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

// ============================================================
// Main Renderer
// ============================================================
function renderGeneral(r) {
  const box = document.getElementById("result");
  if (r.error) {
    box.innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(r.error) + '</p></div>';
    return;
  }

  const reject = r.reject_null;
  const verdictClass = reject === true ? "reject" : "fail";
  const verdictIcon = reject === true ? "✓" : "⚠";
  const verdictText = reject === true ? "Reject Null Hypothesis" : "Fail to Reject Null Hypothesis";

  // Build metrics rows — skip meta fields and effect size fields
  const skip = [
    "test", "interpretation", "reject_null", "significance",
    "contingency_table", "group_stats",
    // Effect size fields (rendered separately)
    "cohens_d", "cohens_d_interpretation",
    "hedges_g", "hedges_g_interpretation",
    "eta_squared", "eta_squared_interpretation",
    "omega_squared", "omega_squared_interpretation",
    "cramers_v", "cramers_v_interpretation",
    "odds_ratio", "rank_biserial", "rank_biserial_interpretation",
    "epsilon_squared", "epsilon_squared_interpretation",
    "r_squared", "r_squared_interpretation",
  ];

  const rows = [];
  for (const [k, v] of Object.entries(r)) {
    if (skip.includes(k)) continue;
    if (v === null || v === undefined) continue;
    if (typeof v === "object") continue;
    const label = k.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    rows.push({ label, value: v });
  }

  box.innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-2">${esc(r.test)}</h2>
      <div class="verdict ${verdictClass} mb-6">
        <span style="font-size:24px">${verdictIcon}</span>
        <div>
          <p class="font-semibold">${verdictText}</p>
          <p class="text-xs mt-1">${esc(r.interpretation || '')}</p>
        </div>
      </div>
      ${r.p_value !== undefined ? `
        <div class="grid grid-cols-3 gap-3 mb-6">
          <div class="stat-card">
            <p class="stat-label">p-value</p>
            <p class="stat-value">${r.p_value} ${r.significance || ''}</p>
          </div>
          ${r.test_statistic !== undefined ? `<div class="stat-card"><p class="stat-label">Test Statistic</p><p class="stat-value">${r.test_statistic}</p></div>` : ''}
          ${r.t_statistic !== undefined ? `<div class="stat-card"><p class="stat-label">t-statistic</p><p class="stat-value">${r.t_statistic}</p></div>` : ''}
          ${r.f_statistic !== undefined ? `<div class="stat-card"><p class="stat-label">F-statistic</p><p class="stat-value">${r.f_statistic}</p></div>` : ''}
          ${r.chi2_statistic !== undefined ? `<div class="stat-card"><p class="stat-label">χ²</p><p class="stat-value">${r.chi2_statistic}</p></div>` : ''}
          ${r.u_statistic !== undefined ? `<div class="stat-card"><p class="stat-label">U-statistic</p><p class="stat-value">${r.u_statistic}</p></div>` : ''}
          ${r.h_statistic !== undefined ? `<div class="stat-card"><p class="stat-label">H-statistic</p><p class="stat-value">${r.h_statistic}</p></div>` : ''}
          ${r.w_statistic !== undefined ? `<div class="stat-card"><p class="stat-label">W-statistic</p><p class="stat-value">${r.w_statistic}</p></div>` : ''}
          ${r.pearson_r !== undefined ? `<div class="stat-card"><p class="stat-label">Pearson r</p><p class="stat-value">${r.pearson_r}</p></div>` : ''}
        </div>
      ` : ''}
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Details</h3>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:6px">
        <table class="data-table">
          <thead><tr><th>Metric</th><th style="text-align:right">Value</th></tr></thead>
          <tbody>
            ${rows.map(row => `<tr><td>${esc(row.label)}</td><td style="text-align:right">${esc(row.value)}</td></tr>`).join("")}
          </tbody>
        </table>
      </div>
    </div>
    ${buildEffectSizeSection(r)}
  `;
}

// ============================================================
// Tukey HSD Renderer
// ============================================================
function renderTukey(r) {
  const box = document.getElementById("result");
  if (r.error) {
    box.innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(r.error) + '</p></div>';
    return;
  }

  box.innerHTML = `
    <div class="card p-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-2">${esc(r.test)}</h2>
      <div class="verdict reject mb-6">
        <span style="font-size:24px">✓</span>
        <div>
          <p class="font-semibold">Tukey HSD Results</p>
          <p class="text-xs mt-1">${esc(r.interpretation || '')}</p>
        </div>
      </div>

      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Multiple Comparisons</h3>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:6px">
        <table class="data-table">
          <thead>
            <tr>
              <th>Group 1</th><th>Group 2</th><th style="text-align:right">Mean Diff</th>
              <th style="text-align:right">p-value (adj)</th><th style="text-align:center">Significant</th>
            </tr>
          </thead>
          <tbody>
            ${(r.comparisons || []).map(c => `
              <tr>
                <td>${esc(c.group1)}</td>
                <td>${esc(c.group2)}</td>
                <td style="text-align:right">${c.meandiff}</td>
                <td style="text-align:right">${c.p_adj}</td>
                <td style="text-align:center">${c.significant ? '✅ Yes' : '❌ No'}</td>
              </tr>
            `).join("")}
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

loadDatasets();
document.addEventListener("neda:dataset-uploaded", loadDatasets);