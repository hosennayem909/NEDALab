requireAuth();
renderSidebar("dashboard");

const fileInput = document.getElementById("fileInput");
const fileName = document.getElementById("fileName");
const dropZone = document.getElementById("dropZone");
const proceedBtn = document.getElementById("proceedBtn");
const resetBtn = document.getElementById("resetBtn");

const uploadStep = document.getElementById("uploadStep");
const cleaningStep = document.getElementById("cleaningStep");
const previewStep = document.getElementById("previewStep");
const advancedOptions = document.getElementById("advancedOptions");

const step1El = document.getElementById("step1");
const step2El = document.getElementById("step2");
const step3El = document.getElementById("step3");

const searchInput = document.getElementById("searchInput");
const statusFilter = document.getElementById("statusFilter");
const sortSelect = document.getElementById("sortSelect");
const clearFiltersBtn = document.getElementById("clearFilters");
const resultCount = document.getElementById("resultCount");
const customerDatasetSelect = document.getElementById("customerDatasetSelect");
const runCustomerAnalysisBtn = document.getElementById("runCustomerAnalysisBtn");

let currentPreset = "standard";
let previewReport = null;
let activityChart = null;
let distributionChart = null;
let growthChart = null;
let allDatasets = [];
let searchTimer = null;

// ========== FILE SELECT ==========
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) {
    fileName.textContent = "Selected: " + fileInput.files[0].name;
    fileName.classList.remove("hidden");
    proceedBtn.disabled = false;
    resetBtn.classList.remove("hidden");
  }
});

["dragenter","dragover"].forEach(ev => dropZone.addEventListener(ev, e => {
  e.preventDefault(); dropZone.style.borderColor = "#047857"; dropZone.style.background = "#ecfdf5";
}));
["dragleave","drop"].forEach(ev => dropZone.addEventListener(ev, e => {
  e.preventDefault(); dropZone.style.borderColor = "#d6d3d1"; dropZone.style.background = "#faf8f3";
}));

resetBtn.addEventListener("click", () => {
  fileInput.value = ""; fileName.classList.add("hidden");
  proceedBtn.disabled = true; resetBtn.classList.add("hidden");
});

function gotoStep(n) {
  uploadStep.style.display = n === 1 ? "block" : "none";
  cleaningStep.style.display = n === 2 ? "block" : "none";
  previewStep.style.display = n === 3 ? "block" : "none";
  [step1El, step2El, step3El].forEach((el, i) => {
    el.classList.remove("active", "done");
    if (i + 1 === n) el.classList.add("active");
    if (i + 1 < n) el.classList.add("done");
  });
}

proceedBtn.addEventListener("click", () => gotoStep(2));
document.getElementById("backToFile").addEventListener("click", () => gotoStep(1));
document.getElementById("backToClean").addEventListener("click", () => gotoStep(2));

document.querySelectorAll(".preset-card").forEach(card => {
  card.addEventListener("click", () => {
    document.querySelectorAll(".preset-card").forEach(c => c.classList.remove("active"));
    card.classList.add("active");
    currentPreset = card.dataset.preset;
    advancedOptions.style.display = currentPreset === "custom" ? "grid" : "none";
  });
});

function getCleanConfig() {
  if (currentPreset === "custom") {
    return {
      preset: "custom",
      drop_empty_rows: true,
      duplicates: document.getElementById("optDuplicates").value,
      missing: document.getElementById("optMissing").value,
      outliers: document.getElementById("optOutliers").value,
      strings: document.getElementById("optStrings").value,
    };
  }
  return { preset: currentPreset };
}

document.getElementById("previewBtn").addEventListener("click", async () => {
  const btn = document.getElementById("previewBtn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="border-color:rgba(255,255,255,0.3);border-top-color:white"></span> Analyzing...';
  const cfg = getCleanConfig();
  const fd = new FormData();
  fd.append("file", fileInput.files[0]);
  fd.append("preset", cfg.preset);
  fd.append("drop_empty_rows", cfg.drop_empty_rows ?? true);
  fd.append("duplicates", cfg.duplicates ?? "drop_all");
  fd.append("missing", cfg.missing ?? "auto");
  fd.append("outliers", cfg.outliers ?? "keep");
  fd.append("strings", cfg.strings ?? "trim");
  try {
    const token = localStorage.getItem("neda_token");
    const res = await fetch(window.NEDA_API_BASE + "/api/data/preview-clean", {
      method: "POST",
      headers: token ? { Authorization: "Bearer " + token } : {},
      body: fd,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Preview failed");
    previewReport = data.report;
    renderPreview(data.report);
    gotoStep(3);
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Preview cleaning";
  }
});

function renderPreview(report) {
  const before = report.stats_before;
  const after = report.stats_after;
  document.getElementById("beforeAfter").innerHTML = `
    <div class="ba-card">
      <p class="ba-title">Before</p>
      <div class="ba-row"><span>Rows</span><span class="ba-val">${before.rows}</span></div>
      <div class="ba-row"><span>Columns</span><span class="ba-val">${before.columns}</span></div>
      <div class="ba-row"><span>Missing</span><span class="ba-val">${before.missing}</span></div>
      <div class="ba-row"><span>Duplicates</span><span class="ba-val">${before.duplicates}</span></div>
    </div>
    <div class="ba-card after">
      <p class="ba-title">After</p>
      <div class="ba-row"><span>Rows</span><span class="ba-val">${after.rows}</span></div>
      <div class="ba-row"><span>Columns</span><span class="ba-val">${after.columns}</span></div>
      <div class="ba-row"><span>Missing</span><span class="ba-val">${after.missing}</span></div>
      <div class="ba-row"><span>Duplicates</span><span class="ba-val">${after.duplicates}</span></div>
    </div>
  `;
  document.getElementById("cleaningLog").innerHTML = (report.log || []).map(l => `<li>${l}</li>`).join("");
}

document.getElementById("saveBtn").addEventListener("click", async () => {
  const btn = document.getElementById("saveBtn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="border-color:rgba(255,255,255,0.3);border-top-color:white"></span> Saving...';
  const cfg = getCleanConfig();
  const fd = new FormData();
  fd.append("file", fileInput.files[0]);
  fd.append("preset", cfg.preset);
  fd.append("drop_empty_rows", cfg.drop_empty_rows ?? true);
  fd.append("duplicates", cfg.duplicates ?? "drop_all");
  fd.append("missing", cfg.missing ?? "auto");
  fd.append("outliers", cfg.outliers ?? "keep");
  fd.append("strings", cfg.strings ?? "trim");
  try {
    const token = localStorage.getItem("neda_token");
    const res = await fetch(window.NEDA_API_BASE + "/api/data/upload-with-config", {
      method: "POST",
      headers: token ? { Authorization: "Bearer " + token } : {},
      body: fd,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Save failed");
    toast(`Saved: ${data.row_count} rows · ${data.column_count} cols`, "success");
    fileInput.value = ""; fileName.classList.add("hidden");
    proceedBtn.disabled = true; resetBtn.classList.add("hidden");
    gotoStep(1);
    refreshDashboardData();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false; btn.textContent = "Save dataset";
  }
});

// ========== STATS ==========
async function loadStats(datasetsPromise = null) {
  try {
    const [datasets, models, workspaces] = await Promise.all([
      datasetsPromise || apiFetch("/api/data/datasets"),
      apiFetch("/api/forecast/models"),
      apiFetch("/api/workspace/list"),
    ]);
    const now = new Date();
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
    const addedThisMonth = datasets.filter(dataset => {
      const createdAt = new Date(dataset.created_at);
      return Number.isFinite(createdAt.getTime()) && createdAt >= monthStart;
    }).length;
    const totalRows = datasets.reduce((total, dataset) => total + (Number(dataset.row_count) || 0), 0);

    document.getElementById("statDs").textContent = datasets.length.toLocaleString();
    document.getElementById("statDsMeta").textContent = `${addedThisMonth.toLocaleString()} added this month`;
    document.getElementById("statRows").textContent = totalRows.toLocaleString();
    document.getElementById("statRowsMeta").textContent = `Across ${datasets.length.toLocaleString()} datasets`;
    document.getElementById("statModels").textContent = models.length;
    document.getElementById("statModelsMeta").textContent = "Saved forecast models";
    document.getElementById("statWs").textContent = workspaces.length.toLocaleString();
    document.getElementById("statWsMeta").textContent = "Accessible team spaces";
    document.getElementById("overviewUpdatedAt").textContent =
      `Updated ${now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
  } catch (error) {
    document.getElementById("overviewUpdatedAt").textContent = "Could not load metrics";
    console.error("Dashboard metrics load failed:", error);
  }
}

// ========== DATASETS (with search/filter/sort) ==========
async function loadDatasets(datasetsPromise = null) {
  const list = document.getElementById("datasetList");
  list.innerHTML = skeletonRows(2);
  try {
    allDatasets = await (datasetsPromise || apiFetch("/api/data/datasets"));
    applyFilters();
  } catch (err) {
    list.innerHTML = '<p class="text-sm text-red-600">' + err.message + '</p>';
  }
}

document.getElementById("datasetList").addEventListener("click", (event) => {
  const button = event.target.closest("[data-delete-dataset]");
  if (!button) return;
  const dataset = allDatasets.find(item => item.id === Number(button.dataset.deleteDataset));
  if (!dataset) return;

  pendingDeleteDatasetId = dataset.id;
  document.getElementById("deleteDatasetName").textContent = dataset.filename;
  document.getElementById("deleteDatasetDetails").textContent =
    `${dataset.row_count.toLocaleString()} rows · ${dataset.column_count} columns · ${dataset.status}`;
  document.getElementById("deleteDialogError").textContent = "";
  document.getElementById("deleteDatasetDialog").showModal();
});

let pendingDeleteDatasetId = null;

document.getElementById("cancelDeleteBtn").addEventListener("click", () => {
  document.getElementById("deleteDatasetDialog").close();
});

document.getElementById("deleteDatasetDialog").addEventListener("close", () => {
  pendingDeleteDatasetId = null;
});

document.getElementById("confirmDeleteBtn").addEventListener("click", async () => {
  if (pendingDeleteDatasetId === null) return;
  const datasetId = pendingDeleteDatasetId;
  const confirmButton = document.getElementById("confirmDeleteBtn");
  const errorMessage = document.getElementById("deleteDialogError");
  confirmButton.disabled = true;
  confirmButton.textContent = "Deleting...";
  errorMessage.textContent = "";
  try {
    await apiFetch(`/api/data/datasets/${datasetId}`, { method: "DELETE" });
    allDatasets = allDatasets.filter(item => item.id !== datasetId);
    document.getElementById("deleteDatasetDialog").close();
    applyFilters();
    await Promise.all([loadStats(), loadAnalytics()]);
    toast("Dataset deleted", "success");
  } catch (err) {
    errorMessage.textContent = err.message;
  } finally {
    confirmButton.disabled = false;
    confirmButton.textContent = "Delete dataset";
  }
});

function applyFilters() {
  const q = (searchInput.value || "").trim().toLowerCase();
  const status = statusFilter.value;
  const sort = sortSelect.value;

  // Filter
  let filtered = allDatasets.filter(ds => {
    if (status !== "all" && ds.status !== status) return false;
    if (q && !ds.filename.toLowerCase().includes(q)) return false;
    return true;
  });

  // Sort
  const sorters = {
    newest: (a, b) => new Date(b.created_at) - new Date(a.created_at),
    oldest: (a, b) => new Date(a.created_at) - new Date(b.created_at),
    name: (a, b) => a.filename.localeCompare(b.filename),
    rows_desc: (a, b) => b.row_count - a.row_count,
    rows_asc: (a, b) => a.row_count - b.row_count,
  };
  filtered.sort(sorters[sort] || sorters.newest);

  // Show/hide clear filters button
  const hasFilters = q || status !== "all" || sort !== "newest";
  clearFiltersBtn.classList.toggle("hidden", !hasFilters);

  // Result count
  if (allDatasets.length === 0) {
    resultCount.textContent = "";
  } else if (filtered.length === allDatasets.length) {
    resultCount.textContent = `${allDatasets.length} total`;
  } else {
    resultCount.textContent = `Showing ${filtered.length} of ${allDatasets.length}`;
  }

  renderDatasets(filtered, allDatasets.length === 0);
}

function renderDatasets(datasets, isEmpty) {
  const list = document.getElementById("datasetList");

  if (isEmpty) {
    list.innerHTML = `
      <div class="text-center py-10">
        <p class="text-4xl mb-2">📭</p>
        <p class="font-medium text-stone-700">No datasets yet</p>
        <p class="text-sm text-stone-500">Upload your first CSV above to begin.</p>
      </div>`;
    return;
  }

  if (datasets.length === 0) {
    list.innerHTML = `
      <div class="text-center py-10">
        <p class="text-4xl mb-2">🔍</p>
        <p class="font-medium text-stone-700">No matching datasets</p>
        <p class="text-sm text-stone-500">Try adjusting your search or filter.</p>
      </div>`;
    return;
  }

  list.innerHTML = datasets.map(ds => {
    const date = new Date(ds.created_at).toLocaleString();
    const isAgg = ds.status === "aggregated";
    const filename = highlightMatch(ds.filename, searchInput.value.trim());
    return `
      <div class="fade-in flex flex-wrap justify-between items-center gap-2 border rounded-md px-4 py-3" style="border-color:#e7e5e4">
        <div class="min-w-0 flex-1">
          <a href="../dataset/dataset.html?id=${ds.id}" class="font-medium text-stone-900 truncate hover:underline block" style="color:#047857">
            ${filename}
          </a>
          <p class="text-xs text-stone-500">${date} · ${ds.user_email}</p>
        </div>
        <div class="flex flex-wrap items-center justify-end gap-3">
          <span class="text-sm text-stone-700">${ds.row_count} rows · ${ds.column_count} cols</span>
          <span class="badge ${isAgg ? 'badge-amber' : 'badge-emerald'}">${ds.status}</span>
          <a href="../dataset/dataset.html?id=${ds.id}" class="btn-ghost">Preview →</a>
          <button type="button" data-delete-dataset="${ds.id}" class="text-xs font-medium text-red-700 hover:text-red-800 px-2 py-1 rounded-md border border-transparent hover:border-red-200" aria-label="Delete ${escapeHtml(ds.filename)}">Delete</button>
        </div>
      </div>`;
  }).join("");
}

// Highlight matching text in filename
function highlightMatch(text, query) {
  if (!query) return escapeHtml(text);
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx < 0) return escapeHtml(text);
  const before = text.slice(0, idx);
  const match = text.slice(idx, idx + query.length);
  const after = text.slice(idx + query.length);
  return escapeHtml(before) +
    '<mark style="background:#fef3c7;color:#78350f;padding:0 2px;border-radius:2px">' + escapeHtml(match) + '</mark>' +
    escapeHtml(after);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

// Live search with debounce
searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(applyFilters, 150);
});

statusFilter.addEventListener("change", applyFilters);
sortSelect.addEventListener("change", applyFilters);

clearFiltersBtn.addEventListener("click", () => {
  searchInput.value = "";
  statusFilter.value = "all";
  sortSelect.value = "newest";
  applyFilters();
});

customerDatasetSelect.addEventListener("change", loadCustomerAnalysisColumns);
runCustomerAnalysisBtn.addEventListener("click", runCustomerAnalysis);
["customerIdColumn", "customerDateColumn", "customerMonetaryColumn"].forEach(selectId => {
  document.getElementById(selectId).addEventListener("change", updateCustomerAnalysisAvailability);
});

function updateCustomerAnalysisAvailability() {
  runCustomerAnalysisBtn.disabled = !customerDatasetSelect.value
    || !document.getElementById("customerIdColumn").value
    || !document.getElementById("customerDateColumn").value
    || !document.getElementById("customerMonetaryColumn").value;
}

async function loadCustomerAnalysisDatasets(datasetsPromise = null) {
  try {
    const datasets = await (datasetsPromise || apiFetch("/api/data/datasets"));
    if (!datasets.length) {
      customerDatasetSelect.innerHTML = '<option value="">No datasets available</option>';
      document.getElementById("customerAnalysisStatus").textContent = "Upload a dataset to unlock cohort analysis and RFM insights.";
      document.getElementById("customerIdColumn").innerHTML = '<option value="">No dataset selected</option>';
      document.getElementById("customerDateColumn").innerHTML = '<option value="">No dataset selected</option>';
      document.getElementById("customerMonetaryColumn").innerHTML = '<option value="">No dataset selected</option>';
      document.getElementById("customerTransactionColumn").innerHTML = '<option value="">No dataset selected</option>';
      document.getElementById("customerIdColumn").disabled = true;
      document.getElementById("customerDateColumn").disabled = true;
      document.getElementById("customerMonetaryColumn").disabled = true;
      document.getElementById("customerTransactionColumn").disabled = true;
      runCustomerAnalysisBtn.disabled = true;
      return;
    }

    customerDatasetSelect.innerHTML = '<option value="">— Select dataset —</option>' +
      datasets.map(dataset => `<option value="${dataset.id}">${escapeHtml(dataset.filename)} (${Number(dataset.row_count).toLocaleString()} rows)</option>`).join("");
    document.getElementById("customerAnalysisStatus").textContent = "Select a dataset to map its fields.";
  } catch (error) {
    customerDatasetSelect.innerHTML = '<option value="">Could not load datasets</option>';
    document.getElementById("customerAnalysisStatus").textContent = error.message;
  }
}

function setCustomerColumnOptions(selectId, columns, placeholder, matcher, preferredPattern) {
  const select = document.getElementById(selectId);
  const available = columns.filter(matcher);
  select.innerHTML = `<option value="">${placeholder}</option>` +
    available.map(column => `<option value="${escapeHtml(column.name)}">${escapeHtml(column.name)}</option>`).join("");
  select.disabled = available.length === 0;
  if (preferredPattern) {
    const preferred = available.find(column => preferredPattern.test(column.name));
    if (preferred) select.value = preferred.name;
  }
}

async function loadCustomerAnalysisColumns() {
  const datasetId = customerDatasetSelect.value;
  const results = document.getElementById("customerAnalysisResults");
  results.hidden = true;
  runCustomerAnalysisBtn.disabled = true;
  if (!datasetId) {
    document.getElementById("customerAnalysisStatus").textContent = "Select a dataset to map its fields.";
    return;
  }

  document.getElementById("customerAnalysisStatus").textContent = "Loading dataset columns...";
  try {
    const preview = await apiFetch(`/api/data/datasets/${datasetId}/preview?limit=1`);
    const columns = preview.columns || [];
    setCustomerColumnOptions("customerIdColumn", columns, "Choose customer ID", () => true, /customer|client|buyer|member|account|consumer/i);
    setCustomerColumnOptions("customerDateColumn", columns, "Choose purchase date", () => true, /date|time|day|period/i);
    setCustomerColumnOptions("customerMonetaryColumn", columns, "Choose amount", column => /^(int|float|double|decimal|number)/i.test(column.dtype), /sales|revenue|amount|spend|total|value|price/i);
    setCustomerColumnOptions("customerTransactionColumn", columns, "Each row is a transaction", () => true, /invoice|order|transaction|receipt|bill/i);
    document.getElementById("customerAnalysisStatus").textContent = `${columns.length} columns loaded. Confirm the field mapping before running.`;
    updateCustomerAnalysisAvailability();
  } catch (error) {
    document.getElementById("customerAnalysisStatus").textContent = error.message;
  }
}

async function runCustomerAnalysis() {
  const datasetId = customerDatasetSelect.value;
  const customerColumn = document.getElementById("customerIdColumn").value;
  const dateColumn = document.getElementById("customerDateColumn").value;
  const monetaryColumn = document.getElementById("customerMonetaryColumn").value;
  const status = document.getElementById("customerAnalysisStatus");
  const results = document.getElementById("customerAnalysisResults");
  if (!datasetId || !customerColumn || !dateColumn || !monetaryColumn) {
    status.textContent = "Select a dataset, customer ID, purchase date, and sales/amount column.";
    return;
  }

  runCustomerAnalysisBtn.disabled = true;
  runCustomerAnalysisBtn.textContent = "Analyzing...";
  status.textContent = "Calculating monthly cohorts and customer segments...";
  results.hidden = true;
  try {
    const result = await apiFetch(`/api/data/datasets/${datasetId}/customer-insights`, {
      method: "POST",
      body: {
        customer_column: customerColumn,
        date_column: dateColumn,
        monetary_column: monetaryColumn,
        transaction_column: document.getElementById("customerTransactionColumn").value || null,
      },
    });
    renderCustomerAnalysis(result);
    results.hidden = false;
    status.textContent = `${result.dataset_filename} · ${Number(result.summary.rows_skipped).toLocaleString()} invalid rows skipped · as of ${result.summary.analysis_date}`;
  } catch (error) {
    status.textContent = error.message;
  } finally {
    runCustomerAnalysisBtn.disabled = false;
    runCustomerAnalysisBtn.textContent = "Run analysis";
  }
}

function formatInsightNumber(value) {
  return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function renderCustomerAnalysis(result) {
  const summary = result.summary;
  const cohortRows = result.cohort.rows || [];
  const periods = result.cohort.periods || [];
  const segments = result.rfm.segments || [];
  const customers = result.rfm.customers || [];
  const cohortTable = cohortRows.length ? `
    <div class="customer-analysis-table-wrap">
      <table class="data-table customer-analysis-table">
        <thead><tr><th>Cohort</th><th>Customers</th>${periods.map(period => `<th>${escapeHtml(period)}</th>`).join("")}</tr></thead>
        <tbody>${cohortRows.map(row => `
          <tr><td>${escapeHtml(row.month)}</td><td>${formatInsightNumber(row.customers)}</td>
            ${row.retention.map(value => value == null
              ? '<td class="text-stone-400">—</td>'
              : `<td style="background:rgba(4,120,87,${Math.min(0.48, Number(value) / 210)});color:${Number(value) > 68 ? "#fff" : "inherit"}">${Number(value).toFixed(0)}%</td>`).join("")}
          </tr>`).join("")}
        </tbody>
      </table>
    </div>` : '<p class="text-sm text-stone-500">No customer cohorts could be formed from these rows.</p>';
  const segmentTable = segments.length ? `
    <div class="customer-analysis-table-wrap">
      <table class="data-table customer-analysis-table">
        <thead><tr><th>Segment</th><th>Customers</th><th>Share</th><th>Monetary value</th></tr></thead>
        <tbody>${segments.map(segment => `<tr><td>${escapeHtml(segment.name)}</td><td>${formatInsightNumber(segment.customers)}</td><td>${Number(segment.share_pct).toFixed(1)}%</td><td>${formatInsightNumber(segment.monetary)}</td></tr>`).join("")}</tbody>
      </table>
    </div>` : '<p class="text-sm text-stone-500">No RFM segments available.</p>';
  const customerTable = customers.length ? `
    <div class="customer-analysis-table-wrap">
      <table class="data-table customer-analysis-table">
        <thead><tr><th>Customer</th><th>RFM</th><th>Segment</th><th>Recency (days)</th><th>Frequency</th><th>Monetary value</th></tr></thead>
        <tbody>${customers.map(customer => `<tr><td>${escapeHtml(customer.customer)}</td><td>${escapeHtml(customer.score)}</td><td>${escapeHtml(customer.segment)}</td><td>${formatInsightNumber(customer.recency_days)}</td><td>${formatInsightNumber(customer.frequency)}</td><td>${formatInsightNumber(customer.monetary)}</td></tr>`).join("")}</tbody>
      </table>
    </div>` : '<p class="text-sm text-stone-500">No customers available.</p>';

  document.getElementById("customerAnalysisResults").innerHTML = `
    <div class="customer-analysis-results-grid">
      <div class="stat-card"><p class="stat-label">Customers</p><p class="stat-value">${formatInsightNumber(summary.customers)}</p><p class="kpi-meta">Unique customer IDs</p></div>
      <div class="stat-card"><p class="stat-label">Transactions</p><p class="stat-value">${formatInsightNumber(summary.transactions)}</p><p class="kpi-meta">${formatInsightNumber(summary.rows_used)} valid rows</p></div>
      <div class="stat-card"><p class="stat-label">Monetary value</p><p class="stat-value">${formatInsightNumber(summary.monetary_total)}</p><p class="kpi-meta">Dataset currency / units</p></div>
      <div class="stat-card"><p class="stat-label">Average transaction</p><p class="stat-value">${formatInsightNumber(summary.average_transaction_value)}</p><p class="kpi-meta">${escapeHtml(summary.date_from)} to ${escapeHtml(summary.date_to)}</p></div>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
      <section class="customer-analysis-section"><h3>Cohort retention</h3><p class="text-xs text-stone-500 mb-3">Monthly repeat-customer rate by first purchase month. The latest 24 cohorts are shown.</p>${cohortTable}</section>
      <section class="customer-analysis-section"><h3>RFM segments</h3><p class="text-xs text-stone-500 mb-3">Recency uses the day after the latest purchase in this dataset; frequency counts unique orders when mapped.</p>${segmentTable}</section>
    </div>
    <section class="customer-analysis-section"><h3>Top customers by monetary value</h3>${customerTable}</section>`;
}

// ========== ANALYTICS CHARTS ==========
async function loadAnalytics() {
  try {
    const data = await apiFetch("/api/data/analytics");
    renderActivityChart(data.activity);
    renderDistributionChart(data.model_distribution);
    renderGrowthChart(data.growth);
  } catch (err) {
    console.error("Analytics load failed:", err);
  }
}

function getTheme() {
  const dark = document.body.classList.contains("dark");
  return {
    text: dark ? "#a8a29e" : "#57534e",
    grid: dark ? "#262932" : "#e7e5e4",
    emerald: "#10b981",
    amber: "#f59e0b",
    purple: "#a855f7",
    cyan: "#06b6d4",
    bg: dark ? "#181c24" : "#ffffff",
  };
}

function renderActivityChart(activity) {
  const canvas = document.getElementById("activityChart");
  if (!canvas || typeof Chart === "undefined") return;
  if (activityChart) activityChart.destroy();
  const t = getTheme();
  activityChart = new Chart(canvas.getContext("2d"), {
    type: "bar",
    data: {
      labels: activity.map(a => a.month),
      datasets: [
        { label: "Datasets", data: activity.map(a => a.datasets), backgroundColor: t.emerald, borderRadius: 4 },
        { label: "Models", data: activity.map(a => a.models), backgroundColor: t.amber, borderRadius: 4 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: t.text, font: { family: "IBM Plex Sans", size: 11 } } } },
      scales: {
        x: { grid: { color: t.grid }, ticks: { color: t.text } },
        y: { grid: { color: t.grid }, ticks: { color: t.text }, beginAtZero: true },
      },
    },
  });
}

function renderDistributionChart(dist) {
  const canvas = document.getElementById("distributionChart");
  if (!canvas || typeof Chart === "undefined") return;
  if (distributionChart) distributionChart.destroy();
  const t = getTheme();
  if (!dist.length) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = t.text; ctx.font = "13px IBM Plex Sans"; ctx.textAlign = "center";
    ctx.fillText("No models trained yet", canvas.width / 2, 60);
    return;
  }
  const palette = [t.emerald, t.amber, t.purple, t.cyan, "#ec4899", "#84cc16"];
  distributionChart = new Chart(canvas.getContext("2d"), {
    type: "doughnut",
    data: {
      labels: dist.map(d => d.type),
      datasets: [{ data: dist.map(d => d.count), backgroundColor: palette.slice(0, dist.length), borderWidth: 2, borderColor: t.bg }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: "65%",
      plugins: { legend: { position: "bottom", labels: { color: t.text, font: { family: "IBM Plex Sans", size: 11 } } } },
    },
  });
}

function renderGrowthChart(growth) {
  const canvas = document.getElementById("growthChart");
  if (!canvas || typeof Chart === "undefined") return;
  if (growthChart) growthChart.destroy();
  const t = getTheme();
  if (!growth.length) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = t.text; ctx.font = "13px IBM Plex Sans"; ctx.textAlign = "center";
    ctx.fillText("No datasets uploaded yet", canvas.width / 2, 60);
    return;
  }
  growthChart = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      labels: growth.map(g => g.date),
      datasets: [{
        label: "Cumulative datasets",
        data: growth.map(g => g.cumulative),
        borderColor: t.emerald,
        backgroundColor: "rgba(16, 185, 129, 0.1)",
        borderWidth: 2, tension: 0.3, fill: true,
        pointRadius: 3, pointBackgroundColor: t.emerald,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: t.grid }, ticks: { color: t.text } },
        y: { grid: { color: t.grid }, ticks: { color: t.text }, beginAtZero: true },
      },
    },
  });
}

document.addEventListener("click", (e) => {
  if (e.target.id === "darkModeToggle") setTimeout(loadAnalytics, 200);
});

function refreshDashboardData() {
  const datasetsPromise = apiFetch("/api/data/datasets");
  loadDatasets(datasetsPromise);
  loadStats(datasetsPromise);
  loadAnalytics();
  loadCustomerAnalysisDatasets(datasetsPromise);
}

refreshDashboardData();
