requireAuth();
renderSidebar("forecast");

let allModels = [];
let chartInstance = null;

if (typeof Chart === "undefined") {
  setTimeout(() => {
    if (typeof Chart === "undefined") toast("Chart library failed to load.", "warning", 5000);
  }, 1500);
}

const datasetSelect = document.getElementById("datasetSelect");
const columnSelect = document.getElementById("columnSelect");
const columnHint = document.getElementById("columnHint");

// ---------- LOAD DATASETS ----------
async function loadDatasets() {
  try {
    const data = await apiFetch("/api/data/datasets");
    if (!data.length) {
      datasetSelect.innerHTML = '<option value="">No datasets — upload one first</option>';
      return;
    }
    datasetSelect.innerHTML = '<option value="">— Select dataset —</option>' +
      data.map(d => `<option value="${d.id}">${d.filename} (${d.row_count} rows)</option>`).join("");
  } catch (e) {
    datasetSelect.innerHTML = '<option value="">Error loading datasets</option>';
  }
}

// ---------- LOAD COLUMNS ON DATASET CHANGE ----------
datasetSelect.addEventListener("change", async () => {
  const dsId = datasetSelect.value;
  if (!dsId) {
    columnSelect.disabled = true;
    columnSelect.innerHTML = '<option value="">— Select dataset first —</option>';
    columnHint.textContent = "Numeric columns are recommended for forecasting.";
    columnHint.style.color = "#78716c";
    return;
  }

  columnSelect.disabled = true;
  columnSelect.innerHTML = '<option value="">Loading columns...</option>';

  try {
    // Get 1 row only — just need the column names
    const preview = await apiFetch(`/api/data/datasets/${dsId}/preview?limit=1`);
    const cols = preview.columns || [];

    if (!cols.length) {
      columnSelect.innerHTML = '<option value="">No columns found</option>';
      return;
    }

    // Sort: numeric columns first (recommended), then rest
    const NUMERIC = ["int", "float", "number", "double", "int64", "float64", "int32", "float32", "uint8", "int16"];
    const isNumeric = (dtype) => NUMERIC.some(t => String(dtype).toLowerCase().includes(t));

    const sorted = [...cols].sort((a, b) => {
      const aNum = isNumeric(a.dtype) ? 0 : 1;
      const bNum = isNumeric(b.dtype) ? 0 : 1;
      if (aNum !== bNum) return aNum - bNum;
      return a.name.localeCompare(b.name);
    });

    columnSelect.innerHTML = '<option value="">— Select column —</option>' +
      sorted.map(c => {
        const num = isNumeric(c.dtype);
        const icon = num ? "🔢" : "🔤";
        const note = num ? "" : " (non-numeric)";
        return `<option value="${c.name}">${icon} ${c.name}${note}</option>`;
      }).join("");

    columnSelect.disabled = false;

    const numericCount = cols.filter(c => isNumeric(c.dtype)).length;
    columnHint.textContent = `${cols.length} columns · ${numericCount} numeric`;
    columnHint.style.color = numericCount > 0 ? "#047857" : "#b45309";

  } catch (err) {
    columnSelect.innerHTML = '<option value="">Error loading columns</option>';
    columnHint.textContent = err.message;
    columnHint.style.color = "#b91c1c";
  }
});

// ---------- LOAD MODELS ----------
async function loadModels() {
  const list = document.getElementById("modelList");
  list.innerHTML = skeletonRows(2);
  try {
    allModels = await apiFetch("/api/forecast/models");
    if (!allModels.length) {
      list.innerHTML = `
        <div class="text-center py-10">
          <p class="text-4xl mb-2">📈</p>
          <p class="font-medium text-stone-700">No models yet</p>
          <p class="text-sm text-stone-500">Train your first model on the left.</p>
        </div>`;
      return;
    }
    const withMetrics = allModels.map(m => {
      let metrics = {};
      try { metrics = JSON.parse(m.metrics_json || "{}"); } catch(e) {}
      return { ...m, metrics };
    }).sort((a,b) => (a.metrics.rmse ?? 1e9) - (b.metrics.rmse ?? 1e9));

    const bestId = withMetrics[0].id;
    list.innerHTML = withMetrics.map(m => {
      const isBest = m.id === bestId;
      return `
        <div class="fade-in flex justify-between items-center border rounded-md px-4 py-3" style="border-color:#e7e5e4; ${isBest ? 'background:#ecfdf5;' : ''}">
          <div class="min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <p class="font-medium text-stone-900 truncate">${m.name}</p>
              ${isBest ? '<span class="badge badge-emerald">★ Best RMSE</span>' : ''}
            </div>
            <p class="text-xs text-stone-500 mt-0.5">${m.model_type} · target: ${m.target_column}</p>
          </div>
          <div class="flex items-center gap-4 shrink-0">
            <div class="text-right text-xs text-stone-600">
              <p>MAE <span class="font-medium text-stone-800">${m.metrics.mae ?? '—'}</span></p>
              <p>RMSE <span class="font-medium text-stone-800">${m.metrics.rmse ?? '—'}</span></p>
              <p>MAPE <span class="font-medium text-stone-800">${m.metrics.mape ?? '—'}%</span></p>
            </div>
            <button data-mid="${m.id}" class="use-model btn-secondary text-xs">Use</button>
          </div>
        </div>`;
    }).join("");

    list.querySelectorAll(".use-model").forEach(btn => {
      btn.addEventListener("click", () => selectModel(parseInt(btn.dataset.mid)));
    });
  } catch (err) {
    list.innerHTML = '<p class="text-sm text-red-600">' + err.message + '</p>';
  }
}

function selectModel(id) {
  const m = allModels.find(x => x.id === id);
  if (!m) return;
  const box = document.getElementById("predictBox");
  box.style.display = "block";
  box.dataset.modelId = id;
  document.getElementById("chartWrap").style.display = "none";
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function predict() {
  const box = document.getElementById("predictBox");
  const modelId = box.dataset.modelId;
  if (!modelId) return;
  const horizon = parseInt(document.getElementById("horizon").value) || 6;
  const btn = document.getElementById("predictBtn");
  btn.disabled = true;
  try {
    const data = await apiFetch(`/api/forecast/models/${modelId}/predict`, {
      method: "POST", body: { horizon },
    });
    renderChart(data.predictions, horizon);
    renderPredTable(data.predictions);
    document.getElementById("chartWrap").style.display = "block";
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
}

function renderChart(preds, horizon) {
  const canvas = document.getElementById("chart");
  const wrap = document.getElementById("chartWrap");
  if (typeof Chart === "undefined") {
    canvas.style.display = "none"; wrap.style.display = "block"; return;
  }
  canvas.style.display = "block";
  const ctx = canvas.getContext("2d");
  if (chartInstance) { try { chartInstance.destroy(); } catch(e){} chartInstance = null; }
  chartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: preds.map((_, i) => `+${i+1}`),
      datasets: [{
        label: "Predicted", data: preds,
        borderColor: "#047857", backgroundColor: "rgba(4, 120, 87, 0.08)",
        borderWidth: 2, pointRadius: 4, pointBackgroundColor: "#047857",
        tension: 0.25, fill: true,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: '#e7e5e4' }, ticks: { color: '#78716c' } },
        y: { grid: { color: '#e7e5e4' }, ticks: { color: '#78716c' } },
      }
    }
  });
}

function renderPredTable(preds) {
  document.getElementById("predTable").innerHTML = `
    <table class="w-full text-sm">
      <thead><tr class="text-left text-xs text-stone-500 uppercase tracking-wider">
        <th class="py-1">Step</th><th class="py-1 text-right">Predicted value</th>
      </tr></thead>
      <tbody>
        ${preds.map((v, i) => `<tr class="border-t" style="border-color:#e7e5e4"><td class="py-1.5 text-stone-600">+${i+1}</td><td class="py-1.5 text-right font-medium text-stone-900">${v}</td></tr>`).join("")}
      </tbody>
    </table>`;
}

document.getElementById("trainForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("trainBtn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="border-color:rgba(255,255,255,0.3);border-top-color:white"></span> Training...';

  const payload = {
    dataset_id: parseInt(datasetSelect.value),
    target_column: columnSelect.value,
    model_type: document.getElementById("modelType").value,
    name: document.getElementById("modelName").value.trim() || null,
  };

  if (!payload.dataset_id) {
    toast("Please select a dataset", "warning");
    btn.disabled = false; btn.textContent = "Train model"; return;
  }
  if (!payload.target_column) {
    toast("Please select a target column", "warning");
    btn.disabled = false; btn.textContent = "Train model"; return;
  }

  try {
    await apiFetch("/api/forecast/train", { method: "POST", body: payload });
    toast("Model trained successfully", "success");
    document.getElementById("modelName").value = "";
    loadModels();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false; btn.textContent = "Train model";
  }
});

document.getElementById("predictBtn").addEventListener("click", predict);

document.getElementById("exportBtn").addEventListener("click", async () => {
  const box = document.getElementById("predictBox");
  const modelId = box.dataset.modelId;
  if (!modelId) { toast("Select a model first", "warning"); return; }
  const horizon = parseInt(document.getElementById("horizon").value) || 6;
  const token = localStorage.getItem("neda_token");
  try {
    const res = await fetch(`${window.NEDA_API_BASE}/api/forecast/models/${modelId}/export-csv`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
      body: JSON.stringify({ horizon }),
    });
    if (!res.ok) throw new Error("Export failed");
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "forecast.csv";
    a.click();
    toast("Forecast exported", "success");
  } catch (err) {
    toast(err.message, "error");
  }
});

document.getElementById("reportBtn").addEventListener("click", async () => {
  const dsId = datasetSelect.value;
  if (!dsId) { toast("Select a dataset first", "warning"); return; }
  const token = localStorage.getItem("neda_token");
  try {
    const res = await fetch(`${window.NEDA_API_BASE}/api/forecast/report/${dsId}`, {
      headers: { Authorization: "Bearer " + token },
    });
    if (!res.ok) throw new Error("Report download failed");
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "model_comparison.csv";
    a.click();
    toast("Comparison report downloaded", "success");
  } catch (err) {
    toast(err.message, "error");
  }
});

loadDatasets();
loadModels();
