"""Frontend: Plotly Visualization Studio"""
from pathlib import Path

FRONTEND = Path(r"C:\Users\DFIT\Desktop\NEDALab\NEDALAB\frontend")

VIZ_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>NEDA LAB — Visualization Studio</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../shared/theme.css">
<link rel="stylesheet" href="../shared/dark-mode.css">
<link rel="stylesheet" href="../shared/notifications.css">
<link rel="stylesheet" href="../shared/upload-widget.css">
<style>
.viz-tab { padding:8px 14px; border-radius:6px; font-size:12px; font-weight:500;
  cursor:pointer; background:white; border:1px solid #e7e5e4; color:#57534e;
  transition:all 0.15s; display:flex; align-items:center; gap:6px; }
.viz-tab:hover { border-color:#047857; color:#047857; }
.viz-tab.active { background:#047857; color:white; border-color:#047857; }
body.dark .viz-tab { background:#1c2028; border-color:#353a45; color:#d6d3d1; }
body.dark .viz-tab.active { background:#10b981; color:#062017; border-color:#10b981; }
.chip-container { display:flex; flex-wrap:wrap; gap:6px; padding:8px; min-height:44px;
  border:1px solid #d6d3d1; border-radius:8px; background:#fafaf9; max-height:140px; overflow-y:auto; }
body.dark .chip-container { border-color:#353a45; background:#1a1d24; }
.chip { padding:5px 12px; border-radius:999px; background:white; border:1.5px solid #d6d3d1;
  font-size:12px; cursor:pointer; font-family:'IBM Plex Mono',monospace;
  transition:all 0.12s; user-select:none; color:#57534e; }
.chip:hover { border-color:#047857; }
.chip.selected { background:#047857; color:white; border-color:#047857; font-weight:500; }
body.dark .chip { background:#1c2028; border-color:#353a45; color:#d6d3d1; }
body.dark .chip.selected { background:#10b981; color:#062017; border-color:#10b981; }
.chart-box { min-height: 480px; background: white; border-radius: 8px;
  border: 1px solid #e7e5e4; padding: 8px; }
body.dark .chart-box { background: #181c24; border-color: #262932; }
.modebar { background: transparent !important; }
</style>
</head>
<body class="min-h-screen">
<div class="flex">
  <div id="sidebarOverlay" class="sidebar-overlay"></div>
  <aside class="app-sidebar w-64 border-r flex flex-col min-h-screen" style="background:#f4f1ea;border-color:#e7e5e4">
    <div class="p-5">
      <a href="../dashboard/dashboard.html" class="flex items-center gap-2 no-underline">
        <div class="w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-xs" style="background:#047857">N</div>
        <span class="font-bold text-stone-900">NEDA LAB</span>
      </a>
    </div>
    <nav class="px-3 space-y-1 flex-1 overflow-y-auto">
      <a href="../dashboard/dashboard.html" data-page="dashboard" class="sidebar-link">📊 Dashboard</a>
      <a href="../workspace/workspace.html" data-page="workspace" class="sidebar-link">🗂 Workspaces</a>
      <a href="../forecast/forecast.html" data-page="forecast" class="sidebar-link">📈 Forecast</a>
      <a href="../entity/entity.html" data-page="entity" class="sidebar-link">🔗 Entity Mapping</a>
      <a href="../stats/stats.html" data-page="stats" class="sidebar-link">📐 Statistical Clean</a>
      <a href="../adv-stats/adv-stats.html" data-page="adv-stats" class="sidebar-link">⚗️ Advanced Cleaning</a>
      <a href="../data-ops/data-ops.html" data-page="data-ops" class="sidebar-link">🧮 Data Operations</a>
      <a href="../feature-eng/feature-eng.html" data-page="feature-eng" class="sidebar-link">⚡ Feature Engineering</a>
      <a href="../quality/quality.html" data-page="quality" class="sidebar-link">✅ Data Quality</a>
      <a href="../viz/viz.html" data-page="viz" class="sidebar-link">📊 Visualization</a>
      <a href="../versions/versions.html" data-page="versions" class="sidebar-link">📚 Version History</a>
      <a href="../scheduler/scheduler.html" data-page="scheduler" class="sidebar-link">⏰ Scheduler</a>
      <a href="../econometrics/econometrics.html" data-page="econometrics" class="sidebar-link">📉 Regression</a>
      <a href="../econometrics/stats-tests.html" data-page="stats-tests" class="sidebar-link">🔬 Statistical Tests</a>
      <a href="../econometrics/panel.html" data-page="panel" class="sidebar-link">📊 Panel Data</a>
      <a href="../econometrics/var.html" data-page="var" class="sidebar-link">🔄 VAR</a>
      <a href="../econometrics/advanced.html" data-page="econ-adv" class="sidebar-link">🎓 Advanced Econ</a>
      <a href="../econometrics/hypothesis.html" data-page="hypothesis" class="sidebar-link">🧪 Hypothesis Tests</a>
      <a href="../ml/ml.html" data-page="ml" class="sidebar-link">🤖 Machine Learning</a>
      <a href="../ml/tuning.html" data-page="ml-tune" class="sidebar-link">🎛️ ML Tuning & SHAP</a>
      <a href="../automl/automl.html" data-page="automl" class="sidebar-link">✨ AutoML Studio</a>
      <a href="../profile/profile.html" data-page="profile" class="sidebar-link">👤 Profile</a>
    </nav>
    <div class="p-5 border-t" style="border-color:#e7e5e4">
      <p id="sideUserName" class="text-sm font-medium text-stone-800">—</p>
      <p id="sideUserEmail" class="text-xs text-stone-500 truncate">—</p>
      <button id="logoutBtn" class="mt-3 text-xs font-medium text-red-700 hover:text-red-800">Sign out →</button>
    </div>
  </aside>

  <main class="app-main flex-1 p-8">
    <div class="max-w-7xl">
      <div class="flex items-center gap-3 mb-6">
        <button id="mobileMenuBtn" class="mobile-menu-btn">☰</button>
        <div>
          <h1 class="text-2xl font-bold text-stone-900">Visualization Studio</h1>
          <p class="text-sm text-stone-500">Interactive charts with zoom, pan, hover, and export.</p>
        </div>
      </div>

      <div class="card p-5 mb-6">
        <div class="grid grid-cols-3 gap-4">
          <div class="col-span-2">
            <label class="label">Dataset</label>
            <select id="dsSelect" class="input"><option value="">Loading...</option></select>
          </div>
          <div>
            <label class="label">Chart type</label>
            <select id="chartType" class="input">
              <option value="line">📈 Line Chart</option>
              <option value="bar">📊 Bar Chart</option>
              <option value="scatter">⚫ Scatter Plot</option>
              <option value="histogram">📊 Histogram</option>
              <option value="box">📦 Box Plot</option>
              <option value="pie">🥧 Pie Chart</option>
              <option value="heatmap">🔥 Correlation Heatmap</option>
            </select>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="lg:col-span-1">
          <div class="card p-5 sticky top-6">
            <h2 class="font-semibold text-stone-900 mb-4">Configure</h2>
            <div id="configPanel">
              <p class="text-sm text-stone-500">Select a dataset to begin</p>
            </div>
            <button id="renderBtn" class="btn-primary w-full mt-4" disabled>📊 Render Chart</button>
          </div>
        </div>

        <div class="lg:col-span-2">
          <div id="empty" class="card p-10 text-center">
            <p class="text-4xl mb-3">📊</p>
            <p class="font-medium text-stone-700">Configure and render a chart</p>
            <p class="text-sm text-stone-500 mt-1">Interactive Plotly chart will appear here.</p>
          </div>
          <div id="loading" style="display:none" class="card p-8 text-center">
            <span class="spinner"></span>
            <p class="text-sm text-stone-600 mt-2">Generating chart...</p>
          </div>
          <div id="chartBox" class="chart-box" style="display:none">
            <div id="plotlyChart" style="width:100%;height:520px"></div>
          </div>
        </div>
      </div>
    </div>
  </main>
</div>

<script src="../shared/api.js"></script>
<script src="../shared/auth.js"></script>
<script src="../shared/ui.js"></script>
<script src="viz.js"></script>
<script src="../shared/dark-mode.js"></script>
<script src="../shared/notifications.js"></script>
<script src="../shared/upload-widget.js"></script>
</body>
</html>
'''

VIZ_JS = '''requireAuth();
renderSidebar("viz");

let currentDatasetId = null;
let colInfo = { all_columns: [], numeric_columns: [], categorical_columns: [], date_columns: [] };
let selectedMulti = {};

// ============ Load datasets ============
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
  if (!id) {
    currentDatasetId = null;
    document.getElementById("configPanel").innerHTML = '<p class="text-sm text-stone-500">Select a dataset to begin</p>';
    document.getElementById("renderBtn").disabled = true;
    return;
  }
  currentDatasetId = parseInt(id);
  try {
    colInfo = await apiFetch("/api/viz/columns/" + currentDatasetId);
    document.getElementById("renderBtn").disabled = false;
    renderConfig();
  } catch (e) { toast(e.message, "error"); }
});

document.getElementById("chartType").addEventListener("change", () => {
  selectedMulti = {};
  renderConfig();
});

// ============ Config panel per chart type ============
function renderConfig() {
  const type = document.getElementById("chartType").value;
  const panel = document.getElementById("configPanel");
  const all = colInfo.all_columns;
  const nums = colInfo.numeric_columns;
  const cats = colInfo.categorical_columns;
  const dates = colInfo.date_columns;

  if (type === "line") {
    const xOpts = [...dates, ...all.filter(c => !dates.includes(c))];
    panel.innerHTML = `
      <div class="space-y-3">
        <div>
          <label class="label">X-axis (time or category)</label>
          <select id="vLineX" class="input">${xOpts.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")}</select>
        </div>
        <div>
          <label class="label">Y-axis columns (multiple)</label>
          <div class="chip-container" id="vLineY">
            ${nums.map(c => `<span class="chip" data-col="${esc(c)}">${esc(c)}</span>`).join("")}
          </div>
          <p class="text-xs text-stone-500 mt-1">Click to select numeric columns</p>
        </div>
        <div>
          <label class="label">Aggregation</label>
          <select id="vLineAgg" class="input">
            <option value="sum">Sum</option>
            <option value="mean">Mean</option>
            <option value="count">Count</option>
            <option value="max">Max</option>
            <option value="min">Min</option>
            <option value="median">Median</option>
          </select>
        </div>
      </div>
    `;
    bindChips("vLineY", "lineY");
  } else if (type === "bar") {
    panel.innerHTML = `
      <div class="space-y-3">
        <div>
          <label class="label">Category column (X)</label>
          <select id="vBarX" class="input">${cats.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")}</select>
        </div>
        <div>
          <label class="label">Value column (Y)</label>
          <select id="vBarY" class="input">${nums.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")}</select>
        </div>
        <div>
          <label class="label">Aggregation</label>
          <select id="vBarAgg" class="input">
            <option value="sum">Sum</option>
            <option value="mean">Mean</option>
            <option value="count">Count</option>
            <option value="max">Max</option>
            <option value="min">Min</option>
          </select>
        </div>
        <div>
          <label class="label">Top N (blank = all)</label>
          <input id="vBarTop" type="number" min="2" max="100" class="input" placeholder="e.g. 15" />
        </div>
      </div>
    `;
  } else if (type === "scatter") {
    panel.innerHTML = `
      <div class="space-y-3">
        <div>
          <label class="label">X-axis (numeric)</label>
          <select id="vScX" class="input">${nums.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")}</select>
        </div>
        <div>
          <label class="label">Y-axis (numeric)</label>
          <select id="vScY" class="input">${nums.map((c, i) => `<option value="${esc(c)}"${i === 1 ? " selected" : ""}>${esc(c)}</option>`).join("")}</select>
        </div>
        <div>
          <label class="label">Color by (optional)</label>
          <select id="vScColor" class="input"><option value="">— None —</option>${cats.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")}</select>
        </div>
      </div>
    `;
  } else if (type === "histogram") {
    panel.innerHTML = `
      <div class="space-y-3">
        <div>
          <label class="label">Numeric column</label>
          <select id="vHistCol" class="input">${nums.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")}</select>
        </div>
        <div>
          <label class="label">Bins</label>
          <input id="vHistBins" type="number" min="5" max="200" value="30" class="input" />
        </div>
      </div>
    `;
  } else if (type === "box") {
    panel.innerHTML = `
      <div class="space-y-3">
        <div>
          <label class="label">Numeric column</label>
          <select id="vBoxCol" class="input">${nums.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")}</select>
        </div>
        <div>
          <label class="label">Group by (optional)</label>
          <select id="vBoxGroup" class="input"><option value="">— None —</option>${cats.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")}</select>
        </div>
      </div>
    `;
  } else if (type === "pie") {
    panel.innerHTML = `
      <div class="space-y-3">
        <div>
          <label class="label">Category column</label>
          <select id="vPieCat" class="input">${cats.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")}</select>
        </div>
        <div>
          <label class="label">Value column (optional)</label>
          <select id="vPieVal" class="input"><option value="">Count rows</option>${nums.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")}</select>
        </div>
        <div>
          <label class="label">Top N categories</label>
          <input id="vPieTop" type="number" min="2" max="50" value="10" class="input" />
        </div>
      </div>
    `;
  } else if (type === "heatmap") {
    panel.innerHTML = `
      <div class="space-y-3">
        <div>
          <label class="label">Numeric columns (2+)</label>
          <div class="chip-container" id="vHmCols">
            ${nums.map(c => `<span class="chip" data-col="${esc(c)}">${esc(c)}</span>`).join("")}
          </div>
          <p class="text-xs text-stone-500 mt-1">Click to select columns for correlation</p>
        </div>
      </div>
    `;
    bindChips("vHmCols", "heatmapCols");
  }
}

function bindChips(containerId, groupKey) {
  if (!selectedMulti[groupKey]) selectedMulti[groupKey] = [];
  const container = document.getElementById(containerId);
  if (!container) return;
  container.querySelectorAll(".chip").forEach(chip => {
    const col = chip.dataset.col;
    if (selectedMulti[groupKey].includes(col)) chip.classList.add("selected");
    chip.addEventListener("click", () => {
      const arr = selectedMulti[groupKey];
      const idx = arr.indexOf(col);
      if (idx >= 0) { arr.splice(idx, 1); chip.classList.remove("selected"); }
      else { arr.push(col); chip.classList.add("selected"); }
    });
  });
}

// ============ Render Chart ============
document.getElementById("renderBtn").addEventListener("click", async () => {
  if (!currentDatasetId) return;
  const type = document.getElementById("chartType").value;

  document.getElementById("empty").style.display = "none";
  document.getElementById("chartBox").style.display = "none";
  document.getElementById("loading").style.display = "block";

  try {
    let url, body;
    if (type === "line") {
      const yCols = selectedMulti.lineY || [];
      if (!yCols.length) { throw new Error("Select at least one Y column"); }
      url = "/api/viz/line";
      body = {
        dataset_id: currentDatasetId,
        x_col: document.getElementById("vLineX").value,
        y_cols: yCols,
        agg: document.getElementById("vLineAgg").value,
      };
    } else if (type === "bar") {
      const topEl = document.getElementById("vBarTop");
      const top = topEl.value ? parseInt(topEl.value) : null;
      url = "/api/viz/bar";
      body = {
        dataset_id: currentDatasetId,
        x_col: document.getElementById("vBarX").value,
        y_col: document.getElementById("vBarY").value,
        agg: document.getElementById("vBarAgg").value,
        top_n: top,
      };
    } else if (type === "scatter") {
      url = "/api/viz/scatter";
      body = {
        dataset_id: currentDatasetId,
        x_col: document.getElementById("vScX").value,
        y_col: document.getElementById("vScY").value,
        color_col: document.getElementById("vScColor").value || null,
      };
    } else if (type === "histogram") {
      url = "/api/viz/histogram";
      body = {
        dataset_id: currentDatasetId,
        col: document.getElementById("vHistCol").value,
        bins: parseInt(document.getElementById("vHistBins").value) || 30,
      };
    } else if (type === "box") {
      url = "/api/viz/box";
      body = {
        dataset_id: currentDatasetId,
        col: document.getElementById("vBoxCol").value,
        group_col: document.getElementById("vBoxGroup").value || null,
      };
    } else if (type === "pie") {
      url = "/api/viz/pie";
      body = {
        dataset_id: currentDatasetId,
        category_col: document.getElementById("vPieCat").value,
        value_col: document.getElementById("vPieVal").value || null,
        top_n: parseInt(document.getElementById("vPieTop").value) || 10,
      };
    } else if (type === "heatmap") {
      const cols = selectedMulti.heatmapCols || [];
      if (cols.length < 2) { throw new Error("Select at least 2 columns"); }
      url = "/api/viz/heatmap";
      body = { dataset_id: currentDatasetId, cols };
    }

    const data = await apiFetch(url, { method: "POST", body });
    document.getElementById("loading").style.display = "none";
    document.getElementById("chartBox").style.display = "block";
    renderPlotly(type, data);
    toast("Chart rendered", "success", 1500);
  } catch (e) {
    document.getElementById("loading").style.display = "none";
    document.getElementById("empty").style.display = "block";
    toast(e.message, "error");
  }
});

// ============ Plotly rendering ============
function isDark() {
  return document.body.classList.contains("dark");
}

function theme() {
  const d = isDark();
  return {
    paper: d ? "#181c24" : "#ffffff",
    plot: d ? "#181c24" : "#ffffff",
    text: d ? "#e7e5e4" : "#1c1917",
    grid: d ? "#2a2e38" : "#e7e5e4",
    palette: ["#047857", "#b45309", "#a855f7", "#06b6d4", "#ec4899", "#84cc16", "#f59e0b", "#6366f1"],
  };
}

function layoutBase(title) {
  const t = theme();
  return {
    title: { text: title, font: { family: "IBM Plex Sans", size: 15, color: t.text } },
    paper_bgcolor: t.paper,
    plot_bgcolor: t.plot,
    font: { family: "IBM Plex Sans", size: 12, color: t.text },
    margin: { l: 60, r: 30, t: 50, b: 60 },
    hoverlabel: { bgcolor: t.paper, font: { color: t.text } },
    showlegend: true,
    legend: { orientation: "h", y: -0.15, font: { color: t.text } },
  };
}

function renderPlotly(type, data) {
  const t = theme();
  const config = { responsive: true, displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
    toImageButtonOptions: { format: "png", filename: "neda_chart", height: 800, width: 1400 } };

  let plotData = [], layout = {};

  if (type === "line") {
    plotData = data.series.map((s, i) => ({
      x: data.x, y: s.y, type: "scatter", mode: "lines+markers", name: s.name,
      line: { color: t.palette[i % t.palette.length], width: 2 },
      marker: { size: 6 },
    }));
    layout = { ...layoutBase("Line Chart — " + data.aggregation), xaxis: { gridcolor: t.grid, zerolinecolor: t.grid }, yaxis: { gridcolor: t.grid, zerolinecolor: t.grid } };
  } else if (type === "bar") {
    plotData = [{
      x: data.x, y: data.y, type: "bar",
      marker: { color: data.y.map((_, i) => t.palette[i % t.palette.length]) },
    }];
    layout = { ...layoutBase("Bar Chart — " + data.aggregation), xaxis: { gridcolor: t.grid }, yaxis: { gridcolor: t.grid } };
  } else if (type === "scatter") {
    if (data.color_values) {
      const groups = {};
      data.color_values.forEach((c, i) => {
        if (!groups[c]) groups[c] = [];
        groups[c].push({ x: data.x[i], y: data.y[i] });
      });
      plotData = Object.keys(groups).slice(0, 10).map((k, i) => ({
        x: groups[k].map(p => p.x), y: groups[k].map(p => p.y),
        mode: "markers", type: "scatter", name: k,
        marker: { size: 8, color: t.palette[i % t.palette.length], opacity: 0.7 },
      }));
    } else {
      plotData = [{
        x: data.x, y: data.y, mode: "markers", type: "scatter",
        marker: { size: 8, color: t.palette[0], opacity: 0.7 },
        name: "Points",
      }];
      if (data.trend) {
        const xMin = Math.min(...data.x), xMax = Math.max(...data.x);
        plotData.push({
          x: [xMin, xMax],
          y: [data.trend.slope * xMin + data.trend.intercept, data.trend.slope * xMax + data.trend.intercept],
          mode: "lines", type: "scatter", name: "Trend",
          line: { color: "#b45309", width: 2, dash: "dash" },
        });
      }
    }
    layout = { ...layoutBase(data.x_label + " vs " + data.y_label), xaxis: { title: data.x_label, gridcolor: t.grid }, yaxis: { title: data.y_label, gridcolor: t.grid } };
  } else if (type === "histogram") {
    plotData = [{
      x: data.centers, y: data.counts, type: "bar",
      marker: { color: t.palette[0] },
      name: "Frequency",
    }];
    layout = { ...layoutBase(`Histogram (n=${data.n})`), xaxis: { gridcolor: t.grid }, yaxis: { gridcolor: t.grid }, bargap: 0.05 };
  } else if (type === "box") {
    if (data.chart === "box_grouped") {
      plotData = data.groups.map((g, i) => {
        const st = data.stats[i];
        return {
          name: g, type: "box",
          q1: [st.q1], median: [st.median], q3: [st.q3],
          lowerfence: [st.lower_fence], upperfence: [st.upper_fence],
          y: [st.median],
          marker: { color: t.palette[i % t.palette.length] },
        };
      });
    } else {
      const st = data.stats;
      plotData = [{
        name: data.y_label, type: "box",
        q1: [st.q1], median: [st.median], q3: [st.q3],
        lowerfence: [st.lower_fence], upperfence: [st.upper_fence],
        y: [st.median],
        marker: { color: t.palette[0] },
        boxpoints: "outliers",
      }];
    }
    layout = { ...layoutBase("Box Plot"), yaxis: { gridcolor: t.grid } };
  } else if (type === "pie") {
    plotData = [{
      labels: data.labels, values: data.values, type: "pie",
      hole: 0.35,
      marker: { colors: data.labels.map((_, i) => t.palette[i % t.palette.length]) },
      textinfo: "label+percent",
      textfont: { color: t.text },
    }];
    layout = { ...layoutBase(`Pie Chart — ${data.n_categories} categories`), showlegend: true };
  } else if (type === "heatmap") {
    plotData = [{
      z: data.matrix, x: data.columns, y: data.columns, type: "heatmap",
      colorscale: [[0, "#b91c1c"], [0.5, "#fafaf9"], [1, "#047857"]],
      zmin: -1, zmax: 1,
      hovertemplate: "%{y} vs %{x}: %{z:.3f}<extra></extra>",
    }];
    layout = { ...layoutBase(`Correlation Heatmap (n=${data.n_obs})`), xaxis: { tickangle: -30 }, yaxis: { autorange: "reversed" } };
  }

  Plotly.newPlot("plotlyChart", plotData, layout, config);
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

// Re-render chart when dark mode toggles
document.addEventListener("click", (e) => {
  if (e.target.id === "darkModeToggle" && document.getElementById("chartBox").style.display !== "none") {
    setTimeout(() => {
      const type = document.getElementById("chartType").value;
      document.getElementById("renderBtn").click();
    }, 300);
  }
});

loadDatasets();
document.addEventListener("neda:dataset-uploaded", loadDatasets);
'''

target = FRONTEND / "viz"
target.mkdir(parents=True, exist_ok=True)
(target / "viz.html").write_text(VIZ_HTML, encoding="utf-8")
print("  + frontend/viz/viz.html")
(target / "viz.js").write_text(VIZ_JS, encoding="utf-8")
print("  + frontend/viz/viz.js")

# Patch sidebar in all pages
PAGES = [
    "dashboard/dashboard.html", "workspace/workspace.html", "forecast/forecast.html",
    "profile/profile.html", "dataset/dataset.html", "entity/entity.html",
    "stats/stats.html", "adv-stats/adv-stats.html",
    "data-ops/data-ops.html", "feature-eng/feature-eng.html", "quality/quality.html",
    "versions/versions.html", "scheduler/scheduler.html",
    "econometrics/econometrics.html", "econometrics/stats-tests.html",
    "econometrics/panel.html", "econometrics/var.html",
    "econometrics/advanced.html", "econometrics/hypothesis.html",
    "ml/ml.html", "ml/evaluation.html", "ml/predict.html", "ml/unsupervised.html", "ml/tuning.html",
    "automl/automl.html",
]

MARKER = '<a href="../profile/profile.html" data-page="profile" class="sidebar-link">👤 Profile</a>'
NEW_LINK = '<a href="../viz/viz.html" data-page="viz" class="sidebar-link">📊 Visualization</a>'

for rel in PAGES:
    p = FRONTEND / rel
    if not p.exists(): continue
    content = p.read_text(encoding="utf-8")
    if "viz/viz.html" in content: continue
    if MARKER in content:
        content = content.replace(MARKER, NEW_LINK + "\n      " + MARKER, 1)
        p.write_text(content, encoding="utf-8")
        print("  + patched: " + rel)

print()
print("Done. Hard refresh (Ctrl+Shift+R).")
print("URL: http://127.0.0.1:5500/NEDALAB/frontend/viz/viz.html")