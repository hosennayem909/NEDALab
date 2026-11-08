requireAuth();
renderSidebar("ml-predict");

let allModels = [];
let selectedModel = null;
let currentMode = "single";

async function loadModels() {
  const box = document.getElementById("modelList");
  try {
    allModels = await apiFetch("/api/ml/models");
    if (!allModels.length) {
      box.innerHTML = '<p class="text-sm text-stone-500 col-span-2">No trained models. Train one from ML page first.</p>';
      return;
    }
    // Only show models with model_path set (indicating they can predict)
    const usable = allModels.filter(m => m.model_path);
    if (!usable.length) {
      box.innerHTML = '<p class="text-sm text-stone-500 col-span-2">No saved models yet. Re-train on the ML page to enable predictions.</p>';
      return;
    }
    box.innerHTML = usable.map(m => `
      <div class="model-card" data-mid="${m.id}">
        <div class="flex justify-between items-start mb-1">
          <p class="font-medium text-stone-900 text-sm">${esc(m.name)}</p>
          <span class="badge badge-emerald">${esc(m.task_type)}</span>
        </div>
        <p class="text-xs text-stone-500">${esc(m.algorithm)} · target: ${esc(m.target_column)}</p>
        <p class="text-xs text-stone-500 mt-1">${new Date(m.created_at).toLocaleString()}</p>
      </div>
    `).join("");
    box.querySelectorAll(".model-card").forEach(card => {
      card.addEventListener("click", () => selectModel(parseInt(card.dataset.mid)));
    });
  } catch (e) {
    box.innerHTML = '<p class="text-sm text-red-600">' + esc(e.message) + '</p>';
  }
}

async function selectModel(id) {
  document.querySelectorAll(".model-card").forEach(c => {
    c.classList.toggle("selected", parseInt(c.dataset.mid) === id);
  });
  try {
    const res = await apiFetch(`/api/ml/models/${id}/features`);
    selectedModel = res;
    document.getElementById("empty").style.display = "none";
    document.getElementById("configArea").style.display = "block";
    buildFeatureForm(res.feature_columns);
    document.getElementById("singleResult").innerHTML = "";
    document.getElementById("batchResult").innerHTML = "";
  } catch (e) {
    toast(e.message, "error");
  }
}

function buildFeatureForm(features) {
  const box = document.getElementById("featureForm");
  box.innerHTML = features.map(f => `
    <div>
      <label class="label">${esc(f)}</label>
      <input class="input feature-input" data-feature="${esc(f)}" type="text" placeholder="Enter value" />
    </div>
  `).join("");
}

document.querySelectorAll(".pred-tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".pred-tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentMode = btn.dataset.mode;
    document.getElementById("singleMode").style.display = currentMode === "single" ? "block" : "none";
    document.getElementById("batchMode").style.display = currentMode === "batch" ? "block" : "none";
  });
});

document.getElementById("predictBtn").addEventListener("click", async () => {
  if (!selectedModel) { toast("Select a model first", "warning"); return; }
  const input = {};
  document.querySelectorAll(".feature-input").forEach(inp => {
    const raw = inp.value.trim();
    if (raw === "") { input[inp.dataset.feature] = null; return; }
    const num = Number(raw);
    input[inp.dataset.feature] = isNaN(num) ? raw : num;
  });

  const btn = document.getElementById("predictBtn");
  btn.disabled = true; btn.textContent = "Predicting...";

  try {
    const res = await apiFetch(`/api/ml/models/${selectedModel.model_id}/predict`, {
      method: "POST",
      body: { input_data: input },
    });
    renderSingleResult(res);
  } catch (e) {
    toast(e.message, "error");
  } finally {
    btn.disabled = false; btn.textContent = "🔮 Predict";
  }
});

function renderSingleResult(r) {
  const box = document.getElementById("singleResult");
  let mainValue;
  if (r.task_type === "classification") {
    mainValue = r.label ?? r.raw_prediction;
  } else {
    mainValue = r.prediction ?? r.raw_prediction;
  }

  box.innerHTML = `
    <div class="card p-6">
      <h3 class="font-semibold text-stone-900 mb-4">Prediction</h3>
      <div class="grid grid-cols-2 gap-4 mb-4">
        <div class="stat-card">
          <p class="stat-label">Task</p>
          <p class="stat-value" style="font-size:16px">${esc(r.task_type)}</p>
        </div>
        <div class="stat-card">
          <p class="stat-label">Predicted Value</p>
          <p class="stat-value">${typeof mainValue === "number" ? mainValue.toFixed(4) : esc(mainValue)}</p>
        </div>
      </div>
      ${r.probabilities ? `
        <h4 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">Class Probabilities</h4>
        <div class="space-y-2">
          ${r.probabilities.map((p, i) => `
            <div>
              <div class="flex justify-between text-xs text-stone-600 mb-1">
                <span>Class ${i}</span>
                <span>${(p * 100).toFixed(2)}%</span>
              </div>
              <div class="prob-bar"><div class="prob-fill" style="width:${(p * 100).toFixed(1)}%"></div></div>
            </div>
          `).join("")}
        </div>
      ` : ''}
    </div>
  `;
}

document.getElementById("batchBtn").addEventListener("click", async () => {
  if (!selectedModel) { toast("Select a model first", "warning"); return; }
  const fileInput = document.getElementById("batchFile");
  if (!fileInput.files.length) { toast("Select a CSV file", "warning"); return; }

  const btn = document.getElementById("batchBtn");
  btn.disabled = true; btn.textContent = "Predicting...";

  const fd = new FormData();
  fd.append("file", fileInput.files[0]);

  try {
    const token = localStorage.getItem("neda_token");
    const res = await fetch(`${window.NEDA_API_BASE}/api/ml/models/${selectedModel.model_id}/predict-batch`, {
      method: "POST",
      headers: { Authorization: "Bearer " + token },
      body: fd,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Batch predict failed");
    renderBatchResult(data);
    toast(`${data.n_rows} rows predicted`, "success");
  } catch (e) {
    toast(e.message, "error");
  } finally {
    btn.disabled = false; btn.textContent = "📦 Predict Batch";
  }
});

function renderBatchResult(r) {
  const box = document.getElementById("batchResult");
  const stats = r.stats;
  const preview = r.preview || [];
  const cols = preview.length ? Object.keys(preview[0]) : [];

  const statsHtml = stats.task_type === "regression" ? `
    <div class="grid grid-cols-4 gap-3 mb-4">
      <div class="stat-card"><p class="stat-label">Rows</p><p class="stat-value">${stats.n_rows}</p></div>
      <div class="stat-card"><p class="stat-label">Mean Pred</p><p class="stat-value">${stats.mean?.toFixed(2) ?? '—'}</p></div>
      <div class="stat-card"><p class="stat-label">Min</p><p class="stat-value">${stats.min?.toFixed(2) ?? '—'}</p></div>
      <div class="stat-card"><p class="stat-label">Max</p><p class="stat-value">${stats.max?.toFixed(2) ?? '—'}</p></div>
    </div>
  ` : `
    <div class="grid grid-cols-4 gap-3 mb-4">
      <div class="stat-card"><p class="stat-label">Rows</p><p class="stat-value">${stats.n_rows}</p></div>
      ${(stats.class_distribution || []).slice(0, 3).map(c => `
        <div class="stat-card"><p class="stat-label">Class ${c.class}</p><p class="stat-value">${c.count}</p></div>
      `).join("")}
    </div>
  `;

  box.innerHTML = `
    <div class="card p-6 mb-4">
      <h3 class="font-semibold text-stone-900 mb-1">Batch Prediction Results</h3>
      <p class="text-xs text-stone-500 mb-4">${stats.task_type} · ${stats.n_rows} rows</p>
      ${statsHtml}
      <a href="${window.NEDA_API_BASE}/api/ml/predictions/${encodeURIComponent(r.download_filename)}"
         class="btn-primary inline-block"
         onclick="downloadPredictions(event, '${r.download_filename}')">
        ⬇ Download Predictions CSV
      </a>
    </div>
    <div class="card p-6">
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Preview (first ${preview.length} rows)</h3>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:6px;max-height:400px">
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

async function downloadPredictions(e, filename) {
  e.preventDefault();
  try {
    const token = localStorage.getItem("neda_token");
    const res = await fetch(`${window.NEDA_API_BASE}/api/ml/predictions/${encodeURIComponent(filename)}`, {
      headers: { Authorization: "Bearer " + token },
    });
    if (!res.ok) throw new Error("Download failed");
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
    toast("Downloaded", "success");
  } catch (err) {
    toast(err.message, "error");
  }
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

loadModels();
document.addEventListener("neda:dataset-uploaded", loadModels);
