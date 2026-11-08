requireAuth();
renderSidebar("dataset");

const params = new URLSearchParams(window.location.search);
const datasetId = Number(params.get("id"));

if (!Number.isInteger(datasetId) || datasetId <= 0) {
  const box = document.getElementById("previewContent");
  if (box) {
    box.innerHTML = `
      <div class="text-center py-10">
        <p class="text-4xl mb-3">📂</p>
        <p class="font-semibold text-stone-700 text-lg">No dataset specified</p>
        <p class="text-sm text-stone-500 mb-5">Please select a dataset from the Dataset Hub to preview it.</p>
        <a href="../dashboard/dashboard.html" class="btn-primary" style="display:inline-block; text-decoration:none; padding: 10px 20px; border-radius: 8px;">← Go to Dataset Hub</a>
      </div>`;
  }
  document.getElementById("pageSub").textContent = "Select a dataset from the Dataset Hub to preview it.";
  document.querySelectorAll(".page-header-actions button").forEach(button => { button.disabled = true; });
  document.querySelector(".page-header-actions").style.display = "none";
  document.querySelector(".tab-btn").parentElement.style.display = "none";
}

let datasetMeta = null;

async function loadMeta() {
  document.getElementById("pageSub").textContent = "Loading dataset...";
  try {
    datasetMeta = await apiFetch("/api/data/datasets/" + datasetId);
    document.getElementById("pageTitle").textContent = datasetMeta.filename;
    document.getElementById("pageSub").textContent =
      `${datasetMeta.row_count} rows · ${datasetMeta.column_count} columns · uploaded by ${datasetMeta.user_email}`;
  } catch (err) {
    document.getElementById("pageSub").textContent = "Error loading dataset";
    if (typeof toast === "function") toast(err.message, "error");
  }
}

async function loadPreview() {
  const box = document.getElementById("previewContent");
  if (!box) return;
  
  box.innerHTML = '<div style="display:flex;align-items:center;gap:10px;color:#78716c"><span class="spinner"></span> Loading preview...</div>';
  try {
    const data = await apiFetch(`/api/data/datasets/${datasetId}/preview?limit=50`);
    if (!data.rows.length) {
      box.innerHTML = '<p class="text-sm text-stone-500">No rows to display.</p>';
      return;
    }
    const cols = data.columns;
    box.innerHTML = `
      <p class="text-xs text-stone-500 mb-3">Showing first ${data.preview_rows} of ${data.total_rows} rows</p>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:8px">
        <table class="data-table">
          <thead>
            <tr>${cols.map(c => `<th title="${c.dtype} · ${c.null_count} nulls · ${c.unique_count} unique">${c.name}</th>`).join("")}</tr>
          </thead>
          <tbody>
            ${data.rows.map(r => `
              <tr>
                ${cols.map(c => {
                  const v = r[c.name];
                  if (v === null || v === undefined) return '<td class="null-value">null</td>';
                  const s = String(v);
                  return `<td title="${s.replace(/"/g, '&quot;')}">${s.length > 60 ? s.slice(0, 60) + '…' : s}</td>`;
                }).join("")}
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
    box.innerHTML = '<p class="text-sm text-red-600">' + err.message + '</p>';
  }
}

async function loadStats() {
  const box = document.getElementById("statsContent");
  if (!box) return;
  
  box.innerHTML = '<div style="display:flex;align-items:center;gap:10px;color:#78716c"><span class="spinner"></span> Loading stats...</div>';
  try {
    const data = await apiFetch(`/api/data/datasets/${datasetId}/stats`);
    const numeric = data.numeric || {};
    const keys = Object.keys(numeric);
    if (!keys.length) {
      box.innerHTML = '<p class="text-sm text-stone-500">No numeric columns found in this dataset.</p>';
      return;
    }
    box.innerHTML = `
      <div class="grid grid-cols-2 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">Total Rows</p><p class="stat-value">${data.total_rows}</p></div>
        <div class="stat-card"><p class="stat-label">Total Columns</p><p class="stat-value">${data.total_columns}</p></div>
      </div>
      <h3 class="font-semibold text-stone-900 mb-3">Numeric column statistics</h3>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:8px">
        <table class="data-table">
          <thead><tr>
            <th>Column</th><th style="text-align:right">Count</th><th style="text-align:right">Mean</th>
            <th style="text-align:right">Std</th><th style="text-align:right">Min</th><th style="text-align:right">Q1</th>
            <th style="text-align:right">Median</th><th style="text-align:right">Q3</th><th style="text-align:right">Max</th>
          </tr></thead>
          <tbody>
            ${keys.map(k => {
              const s = numeric[k];
              return `<tr>
                <td><strong>${k}</strong></td>
                <td style="text-align:right">${s.count}</td>
                <td style="text-align:right">${s.mean}</td>
                <td style="text-align:right">${s.std}</td>
                <td style="text-align:right">${s.min}</td>
                <td style="text-align:right">${s.q1}</td>
                <td style="text-align:right">${s.median}</td>
                <td style="text-align:right">${s.q3}</td>
                <td style="text-align:right">${s.max}</td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
    box.innerHTML = '<p class="text-sm text-red-600">' + err.message + '</p>';
  }
}

async function loadReport() {
  const box = document.getElementById("reportContent");
  if (!box) return;
  
  box.innerHTML = '<div style="display:flex;align-items:center;gap:10px;color:#78716c"><span class="spinner"></span> Loading report...</div>';
  try {
    const r = await apiFetch(`/api/data/datasets/${datasetId}/report`);
    const before = r.stats_before || {};
    const after = r.stats_after || {};

    box.innerHTML = `
      <div class="mb-4">
        <span class="badge badge-emerald">Preset: ${r.preset}</span>
      </div>

      <div class="before-after">
        <div class="ba-card">
          <p class="ba-title">Before cleaning</p>
          <div class="ba-row"><span>Rows</span><span class="ba-val">${before.rows ?? '—'}</span></div>
          <div class="ba-row"><span>Columns</span><span class="ba-val">${before.columns ?? '—'}</span></div>
          <div class="ba-row"><span>Missing values</span><span class="ba-val">${before.missing ?? '—'}</span></div>
          <div class="ba-row"><span>Duplicates</span><span class="ba-val">${before.duplicates ?? '—'}</span></div>
          <div class="ba-row"><span>Empty rows</span><span class="ba-val">${before.empty_rows ?? '—'}</span></div>
        </div>
        <div class="ba-card after">
          <p class="ba-title">After cleaning</p>
          <div class="ba-row"><span>Rows</span><span class="ba-val">${after.rows ?? '—'}</span></div>
          <div class="ba-row"><span>Columns</span><span class="ba-val">${after.columns ?? '—'}</span></div>
          <div class="ba-row"><span>Missing values</span><span class="ba-val">${after.missing ?? '—'}</span></div>
          <div class="ba-row"><span>Duplicates</span><span class="ba-val">${after.duplicates ?? '—'}</span></div>
          <div class="ba-row"><span>Empty rows</span><span class="ba-val">${after.empty_rows ?? '—'}</span></div>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-3 mb-4">
        <div class="stat-card"><p class="stat-label">Rows removed</p><p class="stat-value">${r.rows_removed}</p></div>
        <div class="stat-card"><p class="stat-label">Columns removed</p><p class="stat-value">${r.columns_removed}</p></div>
        <div class="stat-card"><p class="stat-label">Missing filled</p><p class="stat-value">${r.missing_filled}</p></div>
      </div>

      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">Cleaning log</h3>
      <ul class="log-list">
        ${(r.log || []).map(l => `<li>${l}</li>`).join("")}
      </ul>
    `;
  } catch (err) {
    if (err.message.includes("No cleaning report")) {
      box.innerHTML = `
        <div class="text-center py-10">
          <p class="text-4xl mb-2">📋</p>
          <p class="font-medium text-stone-700">No cleaning report</p>
          <p class="text-sm text-stone-500">This dataset was uploaded before the advanced cleaning feature.</p>
        </div>`;
    } else {
      box.innerHTML = '<p class="text-sm text-red-600">' + err.message + '</p>';
    }
  }
}

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll(".tab-btn").forEach(b => {
      b.style.borderBottomColor = "transparent";
      b.style.color = "#78716c";
    });
    btn.style.borderBottomColor = "#047857";
    btn.style.color = "#047857";

    document.getElementById("tabPreview").style.display = tab === "preview" ? "block" : "none";
    document.getElementById("tabStats").style.display = tab === "stats" ? "block" : "none";
    document.getElementById("tabReport").style.display = tab === "report" ? "block" : "none";
  });
});

document.querySelector('[data-tab="preview"]').click();

// Export Buttons
function downloadFile(url, filename) {
  const token = localStorage.getItem("neda_token");
  if (typeof toast === "function") toast("Generating " + filename + "...", "info", 2500);
  fetch(url, { headers: { Authorization: "Bearer " + token } })
    .then(res => { if (!res.ok) throw new Error("Export failed"); return res.blob(); })
    .then(blob => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
      if (typeof toast === "function") toast("Downloaded", "success");
    })
    .catch(err => { if (typeof toast === "function") toast(err.message, "error"); });
}

const downloadBtn = document.getElementById("downloadBtn");
if (downloadBtn) {
  downloadBtn.addEventListener("click", () => {
    const token = localStorage.getItem("neda_token");
    const url = window.NEDA_API_BASE + "/api/data/datasets/" + datasetId + "/download";
    fetch(url, { headers: { Authorization: "Bearer " + token } })
      .then(res => {
        if (!res.ok) throw new Error("Download failed");
        return res.blob();
      })
      .then(blob => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "cleaned_" + (datasetMeta ? datasetMeta.filename.replace(/\.[^.]+$/, "") : "dataset") + ".csv";
        a.click();
        if (typeof toast === "function") toast("Download started", "success");
      })
      .catch(err => { if (typeof toast === "function") toast(err.message, "error"); });
  });
}

const exportExcelBtn = document.getElementById("exportExcelBtn");
if (exportExcelBtn) {
  exportExcelBtn.addEventListener("click", () => {
    downloadFile(window.NEDA_API_BASE + "/api/export/dataset/" + datasetId + "/excel", "dataset_" + datasetId + ".xlsx");
  });
}

const exportPdfBtn = document.getElementById("exportPdfBtn");
if (exportPdfBtn) {
  exportPdfBtn.addEventListener("click", () => {
    downloadFile(window.NEDA_API_BASE + "/api/export/dataset/" + datasetId + "/pdf", "dataset_" + datasetId + "_report.pdf");
  });
}

const exportWordBtn = document.getElementById("exportWordBtn");
if (exportWordBtn) {
  exportWordBtn.addEventListener("click", () => {
    downloadFile(window.NEDA_API_BASE + "/api/data/datasets/" + datasetId + "/export-word", "dataset_" + datasetId + "_report.docx");
  });
}

if (Number.isInteger(datasetId) && datasetId > 0) {
  loadMeta();
  loadPreview();
  loadStats();
  loadReport();
}