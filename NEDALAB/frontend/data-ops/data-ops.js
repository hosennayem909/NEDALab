requireAuth();
renderSidebar("data-ops");

let activeTab = "formula";
let formulaDatasetId = null;
let formulaColumns = [];

// Tab switching
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeTab = btn.dataset.tab;
    renderTab();
  });
});

async function renderTab() {
  if (activeTab === "formula") return renderFormula();
  if (activeTab === "join") return renderJoin();
}

// ============ FORMULA ============
async function renderFormula() {
  const box = document.getElementById("tabContent");
  box.innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 mb-4">Create new column with formula</h2>
      <div class="space-y-4">
        <div>
          <label class="label">Dataset</label>
          <select id="formulaDataset" class="input" style="max-width:400px">
            <option value="">Loading...</option>
          </select>
        </div>

        <div id="formulaEditor" style="display:none">
          <label class="label">Available columns (click to insert)</label>
          <div id="columnChips" class="mb-3"></div>

          <label class="label">Formula</label>
          <input id="formulaInput" type="text" class="formula-input"
            placeholder="e.g. Quantity * Net Rate" />

          <label class="label mt-3">New column name</label>
          <input id="newColumnName" type="text" class="input" placeholder="e.g. computed_value" />

          <div class="flex gap-2 mt-4">
            <button id="previewFormulaBtn" class="btn-primary">Preview</button>
            <button id="applyFormulaBtn" class="btn-secondary">Apply & Save</button>
          </div>
          <p class="text-xs text-stone-500 mt-2">
            Supports: +  -  *  /  abs()  round()  sqrt()  log()  exp()  min()  max()  where()
          </p>
        </div>

        <div id="formulaResult"></div>
      </div>
    </div>
  `;

  await loadFormulaDatasets();

  document.getElementById("formulaDataset").addEventListener("change", async () => {
    const id = document.getElementById("formulaDataset").value;
    if (!id) { document.getElementById("formulaEditor").style.display = "none"; return; }
    formulaDatasetId = parseInt(id);
    await loadFormulaColumns();
  });

  document.getElementById("previewFormulaBtn").addEventListener("click", () => runFormula(false));
  document.getElementById("applyFormulaBtn").addEventListener("click", () => runFormula(true));
}

async function loadFormulaDatasets() {
  const sel = document.getElementById("formulaDataset");
  try {
    const data = await apiFetch("/api/data/datasets");
    if (!data.length) { sel.innerHTML = '<option value="">No datasets</option>'; return; }
    sel.innerHTML = '<option value="">— Select dataset —</option>' +
      data.map(d => `<option value="${d.id}">${esc(d.filename)} (${d.row_count} rows)</option>`).join("");
  } catch (e) { sel.innerHTML = '<option value="">Error</option>'; }
}

async function loadFormulaColumns() {
  try {
    const info = await apiFetch("/api/data/datasets/" + formulaDatasetId + "/column-info");
    formulaColumns = info.all_columns;
    document.getElementById("columnChips").innerHTML = formulaColumns
      .map(c => `<span class="col-chip" data-col="${esc(c)}">${esc(c)}</span>`).join("");
    document.querySelectorAll(".col-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const inp = document.getElementById("formulaInput");
        const col = chip.dataset.col;
        inp.value = (inp.value + " " + col).trim();
        inp.focus();
      });
    });
    document.getElementById("formulaEditor").style.display = "block";
  } catch (e) { toast(e.message, "error"); }
}

async function runFormula(save) {
  const formula = document.getElementById("formulaInput").value.trim();
  const newCol = document.getElementById("newColumnName").value.trim();
  if (!formula) { toast("Enter a formula", "warning"); return; }
  if (!newCol) { toast("Enter new column name", "warning"); return; }

  const box = document.getElementById("formulaResult");
  box.innerHTML = '<div class="p-4 text-sm text-stone-500"><span class="spinner"></span> Evaluating...</div>';

  try {
    const endpoint = save ? "/api/data/formula/apply" : "/api/data/formula/preview";
    const res = await apiFetch(endpoint, {
      method: "POST",
      body: { dataset_id: formulaDatasetId, formula, new_column: newCol, save_as_new: true },
    });
    renderFormulaResult(res, save);
    if (save) {
      toast("Formula applied · " + res.output_filename, "success");
    }
  } catch (e) {
    box.innerHTML = '<p class="text-sm text-red-600">' + esc(e.message) + '</p>';
  }
}

function renderFormulaResult(res, saved) {
  const box = document.getElementById("formulaResult");
  const stats = res.stats;
  const preview = res.preview || [];
  const cols = res.columns || [];

  const statCards = stats ? `
    <div class="grid grid-cols-4 gap-3 mb-4">
      <div class="stat-card"><p class="stat-label">Total Rows</p><p class="stat-value">${stats.total_rows}</p></div>
      <div class="stat-card"><p class="stat-label">Valid Values</p><p class="stat-value">${stats.valid_values}</p></div>
      <div class="stat-card"><p class="stat-label">NaN Count</p><p class="stat-value">${stats.nan_count ?? 0}</p></div>
      <div class="stat-card"><p class="stat-label">Mean</p><p class="stat-value">${stats.mean ?? '—'}</p></div>
    </div>
  ` : '';

  box.innerHTML = `
    <div class="p-4 rounded-md mb-4" style="background:${saved ? '#ecfdf5' : '#fef3c7'};border:1px solid ${saved ? '#047857' : '#b45309'}">
      <p class="font-medium">${saved ? '✓ Saved as new dataset' : '⚠ Preview only (not saved)'}</p>
      ${saved && res.output_filename ? `<p class="text-xs text-stone-600 mt-1">${esc(res.output_filename)}</p>` : ''}
    </div>
    ${statCards}
    ${preview.length ? `
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">Preview (first ${preview.length} rows)</h3>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:6px;max-height:400px">
        <table class="data-table">
          <thead><tr>${cols.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>
          <tbody>
            ${preview.map(row => `
              <tr>${cols.map(c => `<td>${esc(row[c] ?? '')}</td>`).join("")}</tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    ` : ''}
  `;
}

// ============ JOIN ============
async function renderJoin() {
  const box = document.getElementById("tabContent");
  box.innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 mb-4">Join two datasets</h2>
      <div class="grid grid-cols-2 gap-6">
        <div>
          <label class="label">Left dataset</label>
          <select id="leftDataset" class="input"><option value="">Loading...</option></select>
          <label class="label mt-3">Left key column</label>
          <select id="leftKey" class="input" disabled><option value="">—</option></select>
        </div>
        <div>
          <label class="label">Right dataset</label>
          <select id="rightDataset" class="input"><option value="">Loading...</option></select>
          <label class="label mt-3">Right key column</label>
          <select id="rightKey" class="input" disabled><option value="">—</option></select>
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4 mt-4">
        <div>
          <label class="label">Join type</label>
          <select id="joinType" class="input">
            <option value="inner">Inner (only matching)</option>
            <option value="left">Left (all left + matched right)</option>
            <option value="right">Right (all right + matched left)</option>
            <option value="outer">Outer (all rows from both)</option>
          </select>
        </div>
        <div>
          <label class="label">Output name (optional)</label>
          <input id="joinOutputName" class="input" placeholder="e.g. merged_data" />
        </div>
      </div>
      <div class="flex gap-2 mt-4">
        <button id="previewJoinBtn" class="btn-primary">Preview Join</button>
        <button id="applyJoinBtn" class="btn-secondary">Apply & Save</button>
      </div>
    </div>
    <div id="joinResult"></div>
  `;

  await loadJoinDatasets();

  document.getElementById("leftDataset").addEventListener("change", async () => {
    const id = document.getElementById("leftDataset").value;
    if (!id) return;
    await loadKeysFor("leftKey", parseInt(id));
  });
  document.getElementById("rightDataset").addEventListener("change", async () => {
    const id = document.getElementById("rightDataset").value;
    if (!id) return;
    await loadKeysFor("rightKey", parseInt(id));
  });

  document.getElementById("previewJoinBtn").addEventListener("click", () => runJoin(false));
  document.getElementById("applyJoinBtn").addEventListener("click", () => runJoin(true));
}

async function loadJoinDatasets() {
  try {
    const data = await apiFetch("/api/data/datasets");
    const opts = '<option value="">— Select —</option>' +
      data.map(d => `<option value="${d.id}">${esc(d.filename)} (${d.row_count} rows)</option>`).join("");
    document.getElementById("leftDataset").innerHTML = opts;
    document.getElementById("rightDataset").innerHTML = opts;
  } catch (e) { toast(e.message, "error"); }
}

async function loadKeysFor(selectId, datasetId) {
  const sel = document.getElementById(selectId);
  sel.disabled = true;
  sel.innerHTML = '<option>Loading...</option>';
  try {
    const info = await apiFetch("/api/data/datasets/" + datasetId + "/column-info");
    sel.innerHTML = '<option value="">— Select —</option>' +
      info.all_columns.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
    sel.disabled = false;
  } catch (e) {
    sel.innerHTML = '<option value="">Error</option>';
  }
}

async function runJoin(save) {
  const leftId = document.getElementById("leftDataset").value;
  const rightId = document.getElementById("rightDataset").value;
  const leftKey = document.getElementById("leftKey").value;
  const rightKey = document.getElementById("rightKey").value;
  const joinType = document.getElementById("joinType").value;
  const outputName = document.getElementById("joinOutputName").value.trim() || null;

  if (!leftId || !rightId) { toast("Select both datasets", "warning"); return; }
  if (leftId === rightId) { toast("Datasets must be different", "warning"); return; }
  if (!leftKey || !rightKey) { toast("Select both key columns", "warning"); return; }

  const box = document.getElementById("joinResult");
  box.innerHTML = '<div class="p-4 text-sm text-stone-500"><span class="spinner"></span> Joining...</div>';

  try {
    const endpoint = save ? "/api/data/join/apply" : "/api/data/join/preview";
    const res = await apiFetch(endpoint, {
      method: "POST",
      body: {
        left_dataset_id: parseInt(leftId),
        right_dataset_id: parseInt(rightId),
        left_key: leftKey,
        right_key: rightKey,
        join_type: joinType,
        output_name: outputName,
      },
    });
    renderJoinResult(res, save);
    if (save) toast("Join applied · " + res.output_filename, "success");
  } catch (e) {
    box.innerHTML = '<p class="text-sm text-red-600">' + esc(e.message) + '</p>';
  }
}

function renderJoinResult(res, saved) {
  const box = document.getElementById("joinResult");
  const stats = res.stats;
  const preview = res.preview || [];

  const statCards = stats ? `
    <div class="grid grid-cols-4 gap-3 mb-4">
      <div class="stat-card"><p class="stat-label">Left rows</p><p class="stat-value">${stats.left_rows}</p></div>
      <div class="stat-card"><p class="stat-label">Right rows</p><p class="stat-value">${stats.right_rows}</p></div>
      <div class="stat-card"><p class="stat-label">Result rows</p><p class="stat-value">${stats.result_rows}</p></div>
      <div class="stat-card"><p class="stat-label">Match rate</p><p class="stat-value">${stats.match_rate_left}%</p></div>
    </div>
  ` : '';

  const cols = preview.length ? Object.keys(preview[0]) : [];

  box.innerHTML = `
    <div class="p-4 rounded-md mb-4" style="background:${saved ? '#ecfdf5' : '#fef3c7'};border:1px solid ${saved ? '#047857' : '#b45309'}">
      <p class="font-medium">${saved ? '✓ Saved as new dataset' : '⚠ Preview only'}</p>
      ${saved && res.output_filename ? `<p class="text-xs text-stone-600 mt-1">${esc(res.output_filename)}</p>` : ''}
    </div>
    ${statCards}
    ${preview.length ? `
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">Preview (first ${preview.length} rows)</h3>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:6px;max-height:400px">
        <table class="data-table">
          <thead><tr>${cols.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>
          <tbody>
            ${preview.map(row => `<tr>${cols.map(c => `<td>${esc(row[c] ?? '')}</td>`).join("")}</tr>`).join("")}
          </tbody>
        </table>
      </div>
    ` : ''}
  `;
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

renderTab();
document.addEventListener("neda:dataset-uploaded", () => renderTab());
