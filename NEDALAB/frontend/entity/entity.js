requireAuth();
renderSidebar("entity");

let allRules = [];
let editingId = null;

const ruleFormCard = document.getElementById("ruleFormCard");
const ruleForm = document.getElementById("ruleForm");
const ruleIdEl = document.getElementById("ruleId");
const ruleName = document.getElementById("ruleName");
const ruleStd = document.getElementById("ruleStd");
const ruleKeywords = document.getElementById("ruleKeywords");
const ruleMatchType = document.getElementById("ruleMatchType");
const ruleThreshold = document.getElementById("ruleThreshold");
const ruleColumnHint = document.getElementById("ruleColumnHint");
const threshVal = document.getElementById("threshVal");

ruleThreshold.addEventListener("input", () => threshVal.textContent = ruleThreshold.value);

async function loadRules() {
  const list = document.getElementById("ruleList");
  list.innerHTML = '<div class="text-sm text-stone-500">Loading...</div>';
  try {
    allRules = await apiFetch("/api/entity/rules");
    if (!allRules.length) {
      list.innerHTML = '<p class="text-sm text-stone-500">No rules yet. Click "+ New Rule".</p>';
      return;
    }
    list.innerHTML = allRules.map(r => `
      <div class="border rounded-md p-3" style="border-color:#e7e5e4; ${r.active ? '' : 'opacity:0.5'}">
        <div class="flex justify-between items-start mb-1">
          <p class="font-medium text-stone-900 text-sm">${escapeHtml(r.name)}</p>
          <span class="text-xs ${r.active ? 'badge badge-emerald' : 'badge badge-stone'}">${r.active ? 'active' : 'off'}</span>
        </div>
        <p class="text-xs text-stone-600 mb-1">→ ${escapeHtml(r.standard_value)}</p>
        <p class="text-xs text-stone-500 mb-2">${r.keywords.length} kw · ${r.match_type} · ${r.match_threshold}%</p>
        <div class="flex gap-2 text-xs">
          <button data-id="${r.id}" data-act="edit" class="text-xs text-indigo-700 hover:underline">Edit</button>
          <button data-id="${r.id}" data-act="toggle" class="text-xs text-stone-600 hover:underline">${r.active ? 'Disable' : 'Enable'}</button>
          <button data-id="${r.id}" data-act="del" class="text-xs text-red-700 hover:underline">Delete</button>
        </div>
      </div>
    `).join("");
    list.querySelectorAll("button[data-act]").forEach(b => {
      b.addEventListener("click", () => handleAction(b.dataset.act, parseInt(b.dataset.id)));
    });
  } catch (e) {
    list.innerHTML = '<p class="text-sm text-red-600">' + e.message + '</p>';
  }
}

async function handleAction(act, id) {
  const r = allRules.find(x => x.id === id);
  if (!r) return;
  if (act === "edit") openEdit(r);
  if (act === "toggle") {
    try {
      await apiFetch("/api/entity/rules/" + id, { method: "PUT", body: { active: !r.active } });
      toast("Rule " + (r.active ? "disabled" : "enabled"), "success");
      loadRules();
    } catch (e) { toast(e.message, "error"); }
  }
  if (act === "del") {
    if (!confirm("Delete this rule?")) return;
    try {
      await apiFetch("/api/entity/rules/" + id, { method: "DELETE" });
      toast("Rule deleted", "success");
      loadRules();
    } catch (e) { toast(e.message, "error"); }
  }
}

document.getElementById("newRuleBtn").addEventListener("click", () => {
  editingId = null;
  ruleForm.reset();
  ruleThreshold.value = 80; threshVal.textContent = 80;
  document.getElementById("formTitle").textContent = "New Entity Rule";
  ruleFormCard.style.display = "block";
});

document.getElementById("cancelFormBtn").addEventListener("click", () => {
  ruleFormCard.style.display = "none";
});

function openEdit(r) {
  editingId = r.id;
  document.getElementById("formTitle").textContent = "Edit Rule";
  ruleName.value = r.name;
  ruleStd.value = r.standard_value;
  ruleKeywords.value = r.keywords.join(", ");
  ruleMatchType.value = r.match_type;
  ruleThreshold.value = r.match_threshold; threshVal.textContent = r.match_threshold;
  ruleColumnHint.value = r.column_hint || "";
  ruleFormCard.style.display = "block";
}

ruleForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const keywords = ruleKeywords.value.split(",").map(k => k.trim()).filter(k => k);
  const payload = {
    name: ruleName.value.trim(),
    standard_value: ruleStd.value.trim(),
    keywords: keywords,
    match_threshold: parseInt(ruleThreshold.value),
    match_type: ruleMatchType.value,
    column_hint: ruleColumnHint.value.trim() || null,
    active: true,
  };
  try {
    if (editingId) {
      await apiFetch("/api/entity/rules/" + editingId, { method: "PUT", body: payload });
      toast("Rule updated", "success");
    } else {
      await apiFetch("/api/entity/rules", { method: "POST", body: payload });
      toast("Rule created", "success");
    }
    ruleFormCard.style.display = "none";
    loadRules();
  } catch (err) { toast(err.message, "error"); }
});

document.getElementById("testBtn").addEventListener("click", async () => {
  const raw = document.getElementById("testValues").value;
  const values = raw.split("\n").map(v => v.trim()).filter(v => v);
  if (!values.length) { toast("Enter some values", "warning"); return; }
  const box = document.getElementById("testResult");
  box.innerHTML = '<div class="text-sm text-stone-500">Testing...</div>';
  try {
    const res = await apiFetch("/api/entity/test", { method: "POST", body: { values } });
    box.innerHTML = `
      <div class="text-sm mb-2">
        <span class="font-semibold">${res.matched_count} / ${res.total}</span> matched
      </div>
      <table class="data-table">
        <thead><tr><th>Original</th><th>Matched</th><th>Score</th></tr></thead>
        <tbody>
          ${res.results.map(r => `
            <tr>
              <td>${escapeHtml(r.original)}</td>
              <td>${r.matched ? escapeHtml(r.standard_value) : '<span class="null-value">(no match)</span>'}</td>
              <td>${r.matched ? r.score.toFixed(1) : '—'}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  } catch (e) {
    box.innerHTML = '<p class="text-sm text-red-600">' + e.message + '</p>';
  }
});

async function loadDatasets() {
  const sel = document.getElementById("applyDataset");
  try {
    const data = await apiFetch("/api/data/datasets");
    sel.innerHTML = '<option value="">— Select dataset —</option>' +
      data.filter(d => d.status !== "mapped").map(d => `<option value="${d.id}">${escapeHtml(d.filename)}</option>`).join("");
  } catch (e) { sel.innerHTML = '<option value="">Error</option>'; }
}

document.getElementById("applyDataset").addEventListener("change", async () => {
  const dsId = document.getElementById("applyDataset").value;
  const colSel = document.getElementById("applyColumn");
  if (!dsId) { colSel.disabled = true; colSel.innerHTML = '<option value="">—</option>'; return; }
  colSel.disabled = true;
  colSel.innerHTML = '<option>Loading...</option>';
  try {
    const info = await apiFetch(`/api/data/datasets/${dsId}/column-info`);
    colSel.innerHTML = '<option value="">— Select column —</option>' +
      info.all_columns.map(c => `<option value="${c}">${escapeHtml(c)}</option>`).join("");
    colSel.disabled = false;
  } catch (e) {
    colSel.innerHTML = '<option value="">Error</option>';
  }
});

document.getElementById("applyBtn").addEventListener("click", async () => {
  const dsId = document.getElementById("applyDataset").value;
  const col = document.getElementById("applyColumn").value;
  const box = document.getElementById("applyResult");
  if (!dsId || !col) { toast("Select dataset and column", "warning"); return; }
  const btn = document.getElementById("applyBtn");
  btn.disabled = true;
  box.innerHTML = '<div class="text-sm text-stone-500">Applying rules...</div>';
  try {
    const res = await apiFetch("/api/entity/apply", {
      method: "POST",
      body: { dataset_id: parseInt(dsId), column: col, save_as_new: true },
    });
    box.innerHTML = `
      <div class="border rounded-md p-4" style="border-color:#047857;background:#ecfdf5">
        <p class="font-medium text-stone-900 mb-2">✓ Applied successfully</p>
        <p class="text-sm text-stone-700 mb-2"><strong>${res.changed_rows}</strong> of <strong>${res.total_rows}</strong> rows changed</p>
        <div class="text-xs text-stone-600 mb-2">
          ${res.mapping_summary.map(s => `<div>• ${escapeHtml(s.rule)}: ${s.rows_changed} rows</div>`).join("")}
        </div>
        <a href="../dataset/dataset.html?id=${res.output_dataset_id}" class="text-sm font-medium" style="color:#047857">View new dataset →</a>
      </div>
    `;
    toast("Applied " + res.changed_rows + " changes", "success");
  } catch (e) {
    box.innerHTML = '<p class="text-sm text-red-600">' + e.message + '</p>';
    toast(e.message, "error");
  } finally {
    btn.disabled = false;
  }
});

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

loadRules();
loadDatasets();
