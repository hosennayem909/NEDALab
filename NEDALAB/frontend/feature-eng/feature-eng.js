requireAuth();
renderSidebar("feature-eng");

let currentDatasetId = null;
let numericColumns = [];
let categoricalColumns = [];
let dateColumns = [];
let suggestions = null;

const MODULES = [
    { id: "lag", title: "⏱ Lag Features", desc: "Previous values (X_lag1, X_lag2, ...)" },
    { id: "rolling", title: "📊 Rolling Statistics", desc: "Moving mean, std, min, max" },
    { id: "diff", title: "📉 Difference Features", desc: "First difference, % change" },
    { id: "interaction", title: "🔗 Interaction Terms", desc: "X1×X2, X1/X2, X1+X2" },
    { id: "polynomial", title: "📐 Polynomial Features", desc: "X², X³" },
    { id: "date", title: "📅 Date Features", desc: "Year, month, weekday, quarter" },
    { id: "binning", title: "🗂 Binning", desc: "Equal-width or equal-frequency bins" },
    { id: "onehot", title: "🔢 One-Hot Encoding", desc: "Category → binary columns" },
];

let moduleOrder = MODULES.map(m => m.id);

let moduleConfig = {};

function getOrderedModules() {
  return moduleOrder
    .map(id => MODULES.find(m => m.id === id))
    .filter(Boolean);
}

function moveModule(modId, direction) {
  const index = moduleOrder.indexOf(modId);
  const nextIndex = index + direction;
  if (index === -1 || nextIndex < 0 || nextIndex >= moduleOrder.length) return;
  [moduleOrder[index], moduleOrder[nextIndex]] = [moduleOrder[nextIndex], moduleOrder[index]];
  renderModules();
}

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
  if (!id) { currentDatasetId = null; document.getElementById("modulesArea").style.display = "none"; return; }
  currentDatasetId = parseInt(id);
  await loadSuggestions();
});

document.getElementById("autoSuggestBtn").addEventListener("click", async () => {
  if (!currentDatasetId) return;
  await loadSuggestions();
  // Auto-enable modules with suggestions
  if (suggestions) {
    Object.keys(suggestions.suggestions || {}).forEach(key => {
      if (suggestions.suggestions[key].columns?.length) {
        moduleConfig[key] = { ...moduleConfig[key], enabled: true };
      }
    });
    renderModules();
    toast("Auto-suggestions applied", "success");
  }
});

async function loadSuggestions() {
  try {
    suggestions = await apiFetch("/api/feature-eng/suggest/" + currentDatasetId);
    numericColumns = suggestions.numeric_columns || [];
    categoricalColumns = suggestions.categorical_columns || [];
    dateColumns = suggestions.date_columns || [];

    // Init module configs (all disabled by default)
    moduleConfig = {};
    MODULES.forEach(m => {
      const defaults = { enabled: false };
      if (m.id === "rolling") defaults.stats = ["mean"];
      if (m.id === "date") defaults.features = ["year", "month", "day", "weekday", "quarter"];
      moduleConfig[m.id] = defaults;
    });

    document.getElementById("autoSuggestBtn").disabled = false;
    document.getElementById("modulesArea").style.display = "block";
    renderModules();
  } catch (e) {
    toast(e.message, "error");
  }
}

function renderModules() {
  const box = document.getElementById("modulesList");
  box.innerHTML = getOrderedModules().map(m => renderModule(m)).join("");

  box.querySelectorAll(".fe-order-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const { mod, direction } = btn.dataset;
      moveModule(mod, Number(direction));
    });
  });

  // Toggle handlers
  box.querySelectorAll(".fe-module-header").forEach(header => {
    header.addEventListener("click", (e) => {
      if (e.target.closest(".toggle-switch")) return;
      const modId = header.dataset.mod;
      moduleConfig[modId].enabled = !moduleConfig[modId].enabled;
      renderModules();
    });
  });

  box.querySelectorAll(".toggle-switch").forEach(t => {
    t.addEventListener("click", (e) => {
      e.stopPropagation();
      const modId = t.dataset.mod;
      moduleConfig[modId].enabled = !moduleConfig[modId].enabled;
      renderModules();
    });
  });

  // Chip selections
  box.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const modId = chip.dataset.mod;
      const col = chip.dataset.col;
      const field = chip.dataset.field; // e.g., "columns", "pairs"
      const arr = moduleConfig[modId][field] || [];
      const idx = arr.indexOf(col);
      if (idx >= 0) arr.splice(idx, 1);
      else arr.push(col);
      moduleConfig[modId][field] = arr;
      renderModules();
    });
  });

  // Number inputs
  box.querySelectorAll("input[data-mod]").forEach(inp => {
    inp.addEventListener("input", () => {
      const modId = inp.dataset.mod;
      const field = inp.dataset.field;
      const val = inp.type === "number" ? parseInt(inp.value) : inp.value;
      moduleConfig[modId][field] = val;
    });
  });
}

function renderModule(m) {
  const cfg = moduleConfig[m.id] || {};
  const enabled = cfg.enabled;
  const index = moduleOrder.indexOf(m.id);
  const canMoveUp = index > 0;
  const canMoveDown = index < moduleOrder.length - 1;

  let body = "";

  if (m.id === "lag") {
    const cols = cfg.columns || [];
    const lags = cfg.lags || [1];
    body = `
      <div class="mb-3">
        <label class="label">Columns</label>
        <div class="chip-container">
          ${numericColumns.map(c => `<span class="chip${cols.includes(c) ? ' selected' : ''}" data-mod="lag" data-col="${esc(c)}" data-field="columns">${esc(c)}</span>`).join("")}
        </div>
      </div>
      <div>
        <label class="label">Lags (comma-separated)</label>
        <input type="text" class="input" value="${lags.join(', ')}" data-mod="lag" data-field="lagsText" placeholder="1, 2, 3" />
      </div>
    `;
  } else if (m.id === "rolling") {
    const cols = cfg.columns || [];
    const windows = cfg.windows || [3];
    const stats = cfg.stats || ["mean"];
    const allStats = ["mean", "std", "min", "max"];
    body = `
      <div class="mb-3">
        <label class="label">Columns</label>
        <div class="chip-container">
          ${numericColumns.map(c => `<span class="chip${cols.includes(c) ? ' selected' : ''}" data-mod="rolling" data-col="${esc(c)}" data-field="columns">${esc(c)}</span>`).join("")}
        </div>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="label">Windows (comma-sep)</label>
          <input type="text" class="input" value="${windows.join(', ')}" data-mod="rolling" data-field="windowsText" placeholder="3, 7" />
        </div>
        <div>
          <label class="label">Statistics (click to toggle)</label>
          <div style="padding-top: 6px">
            ${allStats.map(s => `<span class="chip${stats.includes(s) ? ' selected' : ''}" data-mod="rolling" data-col="${s}" data-field="stats">${s}</span>`).join("")}
          </div>
        </div>
      </div>
    `;
  } else if (m.id === "diff") {
    const cols = cfg.columns || [];
    body = `
      <div class="mb-3">
        <label class="label">Columns</label>
        <div class="chip-container">
          ${numericColumns.map(c => `<span class="chip${cols.includes(c) ? ' selected' : ''}" data-mod="diff" data-col="${esc(c)}" data-field="columns">${esc(c)}</span>`).join("")}
        </div>
      </div>
      <div>
        <label class="label">Order</label>
        <input type="number" min="1" max="3" value="${cfg.order || 1}" class="input" data-mod="diff" data-field="order" style="max-width:120px" />
      </div>
    `;
  } else if (m.id === "interaction") {
    body = `
      <p class="text-xs text-stone-500 mb-3">Enter column pairs below (e.g., "Amount, Quantity" → creates Amount_x_Quantity).</p>
      <div>
        <label class="label">Pairs (one per line: "col_a, col_b")</label>
        <textarea id="pairInput_interaction" class="input" rows="3" placeholder="Amount, Quantity"></textarea>
      </div>
      <div class="mt-2">
        <label class="label">Operations</label>
        <label class="text-sm"><input type="checkbox" value="multiply" checked /> Multiply (X×Y)</label>
        <label class="text-sm ml-3"><input type="checkbox" value="divide" /> Divide (X/Y)</label>
        <label class="text-sm ml-3"><input type="checkbox" value="add" /> Add (X+Y)</label>
        <label class="text-sm ml-3"><input type="checkbox" value="subtract" /> Subtract (X−Y)</label>
      </div>
    `;
  } else if (m.id === "polynomial") {
    const cols = cfg.columns || [];
    body = `
      <div class="mb-3">
        <label class="label">Columns</label>
        <div class="chip-container">
          ${numericColumns.map(c => `<span class="chip${cols.includes(c) ? ' selected' : ''}" data-mod="polynomial" data-col="${esc(c)}" data-field="columns">${esc(c)}</span>`).join("")}
        </div>
      </div>
      <div>
        <label class="label">Degrees (comma-sep)</label>
        <input type="text" class="input" value="${(cfg.degrees || [2]).join(', ')}" data-mod="polynomial" data-field="degreesText" placeholder="2, 3" />
      </div>
    `;
  } else if (m.id === "date") {
    const cols = cfg.columns || [];
    const feats = cfg.features || ["year", "month", "day", "weekday", "quarter"];
    const allFeats = ["year", "month", "day", "weekday", "quarter", "dayofyear", "week", "hour", "minute"];
    body = `
      <div class="mb-3">
        <label class="label">Date Columns</label>
        <div class="chip-container">
          ${dateColumns.length ? dateColumns.map(c => `<span class="chip${cols.includes(c) ? ' selected' : ''}" data-mod="date" data-col="${esc(c)}" data-field="columns">${esc(c)}</span>`).join("") : '<p class="text-xs text-stone-500">No date columns auto-detected.</p>'}
        </div>
      </div>
      <div>
        <label class="label">Features (click to toggle)</label>
        <div style="padding-top: 4px">
          ${allFeats.map(f => `<span class="chip${feats.includes(f) ? ' selected' : ''}" data-mod="date" data-col="${f}" data-field="features">${f}</span>`).join("")}
        </div>
      </div>
    `;
  } else if (m.id === "binning") {
    const cols = cfg.columns || [];
    body = `
      <div class="mb-3">
        <label class="label">Columns</label>
        <div class="chip-container">
          ${numericColumns.map(c => `<span class="chip${cols.includes(c) ? ' selected' : ''}" data-mod="binning" data-col="${esc(c)}" data-field="columns">${esc(c)}</span>`).join("")}
        </div>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="label">Number of bins</label>
          <input type="number" min="2" max="50" value="${cfg.n_bins || 5}" class="input" data-mod="binning" data-field="n_bins" />
        </div>
        <div>
          <label class="label">Strategy</label>
          <select class="input" data-mod="binning" data-field="strategy">
            <option value="equal_width"${cfg.strategy !== "equal_frequency" ? " selected" : ""}>Equal Width</option>
            <option value="equal_frequency"${cfg.strategy === "equal_frequency" ? " selected" : ""}>Equal Frequency</option>
          </select>
        </div>
      </div>
    `;
  } else if (m.id === "onehot") {
    const cols = cfg.columns || [];
    body = `
      <div class="mb-3">
        <label class="label">Categorical Columns</label>
        <div class="chip-container">
          ${categoricalColumns.length ? categoricalColumns.map(c => `<span class="chip${cols.includes(c) ? ' selected' : ''}" data-mod="onehot" data-col="${esc(c)}" data-field="columns">${esc(c)}</span>`).join("") : '<p class="text-xs text-stone-500">No categorical columns found.</p>'}
        </div>
      </div>
      <div>
        <label class="label">Max categories</label>
        <input type="number" min="2" max="100" value="${cfg.max_categories || 20}" class="input" data-mod="onehot" data-field="max_categories" style="max-width:120px" />
      </div>
    `;
  }

  return `
    <div class="fe-module ${enabled ? 'enabled' : ''}">
      <div class="fe-module-header" data-mod="${m.id}">
        <div>
          <div class="fe-module-title">${esc(m.title)}</div>
          <div class="text-xs text-stone-500 mt-0.5">${esc(m.desc)}</div>
        </div>
        <div class="fe-module-controls">
          <button type="button" class="fe-order-btn" data-mod="${m.id}" data-direction="-1" title="Move up" ${canMoveUp ? "" : "disabled"} aria-label="Move ${esc(m.title)} up">↑</button>
          <button type="button" class="fe-order-btn" data-mod="${m.id}" data-direction="1" title="Move down" ${canMoveDown ? "" : "disabled"} aria-label="Move ${esc(m.title)} down">↓</button>
          <div class="toggle-switch ${enabled ? 'on' : ''}" data-mod="${m.id}"></div>
        </div>
      </div>
      <div class="fe-module-body">${body}</div>
    </div>
  `;
}

// ============ Build payload ============
function buildConfig() {
  const cfg = {};
  getOrderedModules().forEach(m => {
    const c = moduleConfig[m.id] || {};
    cfg[m.id] = { enabled: !!c.enabled };

    if (m.id === "lag") {
      cfg.lag.columns = c.columns || [];
      const t = document.querySelector('input[data-mod="lag"][data-field="lagsText"]');
      cfg.lag.lags = t ? t.value.split(",").map(v => parseInt(v.trim())).filter(v => !isNaN(v)) : [1];
    } else if (m.id === "rolling") {
      cfg.rolling.columns = c.columns || [];
      const wt = document.querySelector('input[data-mod="rolling"][data-field="windowsText"]');
      cfg.rolling.windows = wt ? wt.value.split(",").map(v => parseInt(v.trim())).filter(v => !isNaN(v)) : [3];
      cfg.rolling.stats = moduleConfig.rolling.stats || ["mean"];
    } else if (m.id === "diff") {
      cfg.diff.columns = c.columns || [];
      const oi = document.querySelector('input[data-mod="diff"][data-field="order"]');
      cfg.diff.order = oi ? parseInt(oi.value) : 1;
    } else if (m.id === "interaction") {
      cfg.interaction.pairs = [];
      const ta = document.getElementById("pairInput_interaction");
      if (ta && ta.value.trim()) {
        ta.value.split("\n").forEach(line => {
          const parts = line.split(",").map(p => p.trim()).filter(p => p);
          if (parts.length === 2) cfg.interaction.pairs.push(parts);
        });
      }
      const ops = [];
      document.querySelectorAll('.fe-module.enabled input[type="checkbox"]:checked').forEach(cb => ops.push(cb.value));
      cfg.interaction.operations = ops.length ? ops : ["multiply"];
    } else if (m.id === "polynomial") {
      cfg.polynomial.columns = c.columns || [];
      const dt = document.querySelector('input[data-mod="polynomial"][data-field="degreesText"]');
      cfg.polynomial.degrees = dt ? dt.value.split(",").map(v => parseInt(v.trim())).filter(v => !isNaN(v)) : [2];
    } else if (m.id === "date") {
      cfg.date.columns = c.columns || [];
      cfg.date.features = moduleConfig.date.features || ["year", "month", "day"];
    } else if (m.id === "binning") {
      cfg.binning.columns = c.columns || [];
      const nb = document.querySelector('input[data-mod="binning"][data-field="n_bins"]');
      cfg.binning.n_bins = nb ? parseInt(nb.value) : 5;
      const st = document.querySelector('select[data-mod="binning"][data-field="strategy"]');
      cfg.binning.strategy = st ? st.value : "equal_width";
    } else if (m.id === "onehot") {
      cfg.onehot.columns = c.columns || [];
      const mc = document.querySelector('input[data-mod="onehot"][data-field="max_categories"]');
      cfg.onehot.max_categories = mc ? parseInt(mc.value) : 20;
    }
  });
  cfg.dataset_id = currentDatasetId;
  cfg.save_as_new = true;
  return cfg;
}

document.getElementById("previewBtn").addEventListener("click", async () => {
  const cfg = buildConfig();
  document.getElementById("result").innerHTML = "";
  document.getElementById("loading").style.display = "block";
  try {
    const res = await apiFetch("/api/feature-eng/preview", { method: "POST", body: cfg });
    document.getElementById("loading").style.display = "none";
    renderPreview(res);
  } catch (e) {
    document.getElementById("loading").style.display = "none";
    document.getElementById("result").innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
});

document.getElementById("applyBtn").addEventListener("click", async () => {
  const cfg = buildConfig();
  document.getElementById("result").innerHTML = "";
  document.getElementById("loading").style.display = "block";
  try {
    const res = await apiFetch("/api/feature-eng/apply", { method: "POST", body: cfg });
    document.getElementById("loading").style.display = "none";
    toast("Saved: " + res.output_filename, "success", 5000);
    document.getElementById("result").innerHTML = `
      <div class="card p-6">
        <div class="p-4 rounded-md mb-4" style="background:#ecfdf5;border:1px solid #047857">
          <p class="font-medium">✓ Saved as new dataset</p>
          <p class="text-sm text-stone-700 mt-1">${esc(res.output_filename)}</p>
          <p class="text-xs text-stone-600 mt-2">Original: ${res.report.original_shape[0]}×${res.report.original_shape[1]} → Final: ${res.report.final_shape[0]}×${res.report.final_shape[1]}</p>
          <p class="text-xs text-stone-600">${res.report.total_new_columns} new columns created</p>
        </div>
        <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">Operations Applied</h3>
        ${res.report.operations.map(o => `
          <div class="p-3 rounded-md mb-2" style="background:#fafaf9;border:1px solid #e7e5e4">
            <p class="text-sm font-medium">${esc(o.method)}</p>
            <p class="text-xs text-stone-600">${o.n_new} new columns: ${(o.created_columns || []).slice(0, 8).map(esc).join(", ")}${o.created_columns?.length > 8 ? "..." : ""}</p>
          </div>
        `).join("")}
      </div>
    `;
    loadDatasets();
  } catch (e) {
    document.getElementById("loading").style.display = "none";
    document.getElementById("result").innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
});

function renderPreview(res) {
  const rep = res.report;
  const preview = res.preview || [];
  const cols = Object.keys(preview[0] || {});

  document.getElementById("result").innerHTML = `
    <div class="card p-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-4">Preview</h2>
      <div class="grid grid-cols-4 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">Original</p><p class="stat-value" style="font-size:16px">${rep.original_shape[0]}×${rep.original_shape[1]}</p></div>
        <div class="stat-card"><p class="stat-label">Final</p><p class="stat-value" style="font-size:16px">${rep.final_shape[0]}×${rep.final_shape[1]}</p></div>
        <div class="stat-card"><p class="stat-label">New Columns</p><p class="stat-value">${rep.total_new_columns}</p></div>
        <div class="stat-card"><p class="stat-label">Operations</p><p class="stat-value">${rep.operations.length}</p></div>
      </div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">Sample (first 20 rows)</h3>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:6px;max-height:500px">
        <table class="data-table">
          <thead><tr>${cols.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>
          <tbody>
            ${preview.map(row => `<tr>${cols.map(c => `<td>${esc(row[c] ?? '')}</td>`).join("")}</tr>`).join("")}
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
