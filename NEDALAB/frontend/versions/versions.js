requireAuth();
renderSidebar("versions");

let currentDatasetId = null;
let allVersions = [];
let selectedForCompare = [];

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
  if (!id) {
    currentDatasetId = null;
    document.getElementById("empty").style.display = "block";
    document.getElementById("content").style.display = "none";
    document.getElementById("snapshotBtn").disabled = true;
    return;
  }
  currentDatasetId = parseInt(id);
  document.getElementById("snapshotBtn").disabled = false;
  await loadVersions();
});

document.getElementById("snapshotBtn").addEventListener("click", async () => {
  if (!currentDatasetId) return;
  const desc = prompt("Change description (optional):", "");
  if (desc === null) return; // cancelled
  try {
    await apiFetch("/api/versions/create", {
      method: "POST",
      body: {
        dataset_id: currentDatasetId,
        change_type: "manual_snapshot",
        change_description: desc || "Manual snapshot",
      },
    });
    toast("Snapshot created", "success");
    loadVersions();
  } catch (e) { toast(e.message, "error"); }
});

async function loadVersions() {
  document.getElementById("empty").style.display = "none";
  document.getElementById("content").style.display = "none";
  document.getElementById("loading").style.display = "block";

  try {
    allVersions = await apiFetch("/api/versions/dataset/" + currentDatasetId + "/list");
    render();
    document.getElementById("loading").style.display = "none";
    document.getElementById("content").style.display = "block";
  } catch (e) {
    document.getElementById("loading").style.display = "none";
    document.getElementById("empty").style.display = "block";
    toast(e.message, "error");
  }
}

function render() {
  const box = document.getElementById("content");
  selectedForCompare = [];

  if (!allVersions.length) {
    box.innerHTML = `
      <div class="card p-10 text-center">
        <p class="text-4xl mb-3">📸</p>
        <p class="font-medium text-stone-700">No versions yet</p>
        <p class="text-sm text-stone-500 mt-1">Click "Create Snapshot" to save the current state.</p>
      </div>
    `;
    return;
  }

  box.innerHTML = `
    <div class="card p-6 mb-6">
      <div class="flex justify-between items-center mb-4 flex-wrap gap-2">
        <h2 class="font-semibold text-stone-900">${allVersions.length} version(s)</h2>
        <div class="flex gap-2">
          <button id="compareBtn" class="btn-secondary" disabled>Compare (select 2)</button>
        </div>
      </div>
      <div class="space-y-2">
        ${allVersions.map((v, idx) => renderRow(v, idx === 0)).join("")}
      </div>
    </div>
    <div id="compareSection"></div>
  `;

  // Attach handlers
  box.querySelectorAll(".version-row").forEach(row => {
    const id = parseInt(row.dataset.vid);

    row.querySelector(".v-select").addEventListener("click", (e) => {
      e.stopPropagation();
      toggleSelect(id, row);
    });
    row.querySelector(".v-download").addEventListener("click", (e) => {
      e.stopPropagation();
      downloadVersion(id, row.dataset.vnum);
    });
    row.querySelector(".v-restore").addEventListener("click", (e) => {
      e.stopPropagation();
      restoreVersion(id, row.dataset.vnum);
    });
    row.querySelector(".v-delete").addEventListener("click", (e) => {
      e.stopPropagation();
      deleteVersion(id, row.dataset.vnum);
    });
  });

  document.getElementById("compareBtn").addEventListener("click", runCompare);
}

function renderRow(v, isLatest) {
  const date = new Date(v.created_at).toLocaleString();
  const typeBadge = v.change_type === "restore" ? "v-badge-amber" : "v-badge-emerald";
  return `
    <div class="version-row ${isLatest ? 'current' : ''}" data-vid="${v.id}" data-vnum="${v.version_number}">
      <div class="flex justify-between items-start flex-wrap gap-2">
        <div class="flex items-start gap-3">
          <button class="v-select" style="margin-top:2px;width:18px;height:18px;border:2px solid #a8a29e;border-radius:4px;background:white;cursor:pointer;font-size:11px;padding:0">+</button>
          <div>
            <div class="flex items-center gap-2 flex-wrap">
              <span class="v-badge v-badge-emerald">v${v.version_number}</span>
              ${isLatest ? '<span class="v-badge v-badge-emerald">latest</span>' : ''}
              <span class="v-badge ${typeBadge}">${esc(v.change_type)}</span>
            </div>
            <p class="text-sm text-stone-700 mt-1.5">${esc(v.change_description || '(no description)')}</p>
            <p class="text-xs text-stone-500 mt-1">${date} · ${esc(v.created_by)}</p>
            <p class="text-xs text-stone-500">${v.row_count} rows × ${v.column_count} cols</p>
          </div>
        </div>
        <div class="flex gap-2 shrink-0">
          <button class="v-download btn-ghost">⬇ Download</button>
          <button class="v-restore btn-ghost" style="color:#b45309">↩ Restore</button>
          <button class="v-delete btn-ghost" style="color:#b91c1c">🗑</button>
        </div>
      </div>
    </div>
  `;
}

function toggleSelect(id, row) {
  const btn = row.querySelector(".v-select");
  const idx = selectedForCompare.indexOf(id);
  if (idx >= 0) {
    selectedForCompare.splice(idx, 1);
    btn.style.background = "white";
    btn.style.color = "";
    btn.textContent = "+";
  } else {
    if (selectedForCompare.length >= 2) {
      toast("Max 2 versions for comparison", "warning");
      return;
    }
    selectedForCompare.push(id);
    btn.style.background = "#047857";
    btn.style.color = "white";
    btn.style.borderColor = "#047857";
    btn.textContent = "✓";
  }
  const cmp = document.getElementById("compareBtn");
  if (cmp) cmp.disabled = selectedForCompare.length !== 2;
}

async function downloadVersion(id, vnum) {
  try {
    const token = localStorage.getItem("neda_token");
    const res = await fetch(`${window.NEDA_API_BASE}/api/versions/${id}/download`, {
      headers: { Authorization: "Bearer " + token },
    });
    if (!res.ok) throw new Error("Download failed");
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `version_${vnum}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
    toast("Version downloaded", "success");
  } catch (e) { toast(e.message, "error"); }
}

async function restoreVersion(id, vnum) {
  if (!confirm(`Restore dataset to version v${vnum}?\n\nCurrent state will be saved as a new version.`)) return;
  try {
    await apiFetch("/api/versions/restore", {
      method: "POST",
      body: { version_id: id, change_description: `Restored from v${vnum}` },
    });
    toast("Restored to v" + vnum, "success");
    loadVersions();
  } catch (e) { toast(e.message, "error"); }
}

async function deleteVersion(id, vnum) {
  if (!confirm(`Delete version v${vnum}?`)) return;
  try {
    await apiFetch("/api/versions/" + id, { method: "DELETE" });
    toast("Version deleted", "success");
    loadVersions();
  } catch (e) { toast(e.message, "error"); }
}

async function runCompare() {
  if (selectedForCompare.length !== 2) return;
  const box = document.getElementById("compareSection");
  box.innerHTML = '<div class="card p-8 text-center"><span class="spinner"></span><p class="text-sm mt-2">Comparing...</p></div>';

  try {
    const [a, b] = selectedForCompare;
    const res = await apiFetch(`/api/versions/compare?version_a_id=${a}&version_b_id=${b}`);

    const va = res.version_a;
    const vb = res.version_b;

    box.innerHTML = `
      <div class="card p-6">
        <h2 class="font-semibold text-stone-900 text-lg mb-1">Comparison</h2>
        <p class="text-xs text-stone-500 mb-4">v${va.version_number} ↔ v${vb.version_number}</p>

        <div class="grid grid-cols-4 gap-3 mb-6">
          <div class="stat-card"><p class="stat-label">Rows changed (first 50)</p><p class="stat-value">${res.rows_changed}</p></div>
          <div class="stat-card"><p class="stat-label">Columns added</p><p class="stat-value">${res.columns_added.length}</p></div>
          <div class="stat-card"><p class="stat-label">Columns removed</p><p class="stat-value">${res.columns_removed.length}</p></div>
          <div class="stat-card"><p class="stat-label">Common columns</p><p class="stat-value">${res.columns_common.length}</p></div>
        </div>

        ${res.columns_added.length ? `
          <div class="mb-4">
            <h3 class="text-xs font-semibold text-stone-500 uppercase mb-2">Columns added</h3>
            <div class="flex gap-2 flex-wrap">
              ${res.columns_added.map(c => `<span class="v-badge v-badge-emerald">${esc(c)}</span>`).join("")}
            </div>
          </div>
        ` : ''}

        ${res.columns_removed.length ? `
          <div class="mb-4">
            <h3 class="text-xs font-semibold text-stone-500 uppercase mb-2">Columns removed</h3>
            <div class="flex gap-2 flex-wrap">
              ${res.columns_removed.map(c => `<span class="v-badge v-badge-red">${esc(c)}</span>`).join("")}
            </div>
          </div>
        ` : ''}

        ${res.diff_preview.length ? `
          <h3 class="text-xs font-semibold text-stone-500 uppercase mb-3 mt-6">Row differences (${res.diff_preview.length} shown)</h3>
          <div class="space-y-3">
            ${res.diff_preview.map(d => `
              <div class="p-3 rounded-md" style="border:1px solid #e7e5e4">
                <p class="text-xs text-stone-500 mb-2">Row ${d.row} — changed: ${d.changed_columns.map(esc).join(", ")}</p>
                <div class="diff-grid">
                  ${d.changed_columns.slice(0, 5).map(col => `
                    <div style="font-size:11px;color:#78716c;padding-top:6px">${esc(col)}</div>
                    <div class="diff-cell diff-before">${esc(d.before[col] ?? '')}</div>
                    <div class="diff-cell diff-after">${esc(d.after[col] ?? '')}</div>
                  `).join("")}
                </div>
              </div>
            `).join("")}
          </div>
        ` : '<p class="text-sm text-stone-500">No row differences detected in the first 50 rows.</p>'}
      </div>
    `;
  } catch (e) {
    box.innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

loadDatasets();
document.addEventListener("neda:dataset-uploaded", () => loadDatasets());
