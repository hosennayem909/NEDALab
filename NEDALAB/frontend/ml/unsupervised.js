requireAuth();
renderSidebar("ml-unsup");

let currentDatasetId = null;
let activeMethod = "kmeans";
let charts = {};
const CLUSTER_COLORS = ["#047857", "#b45309", "#a855f7", "#06b6d4", "#ec4899", "#84cc16", "#f59e0b", "#6366f1", "#14b8a6", "#ef4444", "#8b5cf6", "#0891b2"];

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
    const box = document.getElementById("featureList");
    box.innerHTML = info.numeric_columns.map(c => `
      <label class="flex items-center gap-1.5 text-sm cursor-pointer">
        <input type="checkbox" class="feat-check" value="${esc(c)}" style="accent-color:#047857" checked />
        <span class="text-stone-700">${esc(c)}</span>
      </label>
    `).join("");
    if (!info.numeric_columns.length) {
      box.innerHTML = '<p class="text-xs text-stone-500">No numeric columns</p>';
    }
  } catch (e) { toast(e.message, "error"); }
});

document.querySelectorAll(".unsup-tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".unsup-tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeMethod = btn.dataset.method;
    renderConfig();
  });
});

function renderConfig() {
  const box = document.getElementById("configBox");
  if (activeMethod === "kmeans") {
    box.innerHTML = `
      <div class="grid grid-cols-3 gap-4 mb-4">
        <div>
          <label class="label">Number of clusters (K)</label>
          <input id="kClusters" type="number" min="2" max="20" value="3" class="input" />
        </div>
        <div>
          <label class="label">Sample size (max)</label>
          <input id="sampleSize" type="number" min="100" max="20000" value="5000" class="input" />
        </div>
        <div class="flex items-end">
          <button id="runBtn" class="btn-primary w-full">🔵 Run K-Means</button>
        </div>
      </div>
    `;
  } else if (activeMethod === "dbscan") {
    box.innerHTML = `
      <div class="grid grid-cols-4 gap-4 mb-4">
        <div>
          <label class="label">Epsilon (eps)</label>
          <input id="dbEps" type="number" step="0.1" min="0.1" value="0.5" class="input" />
        </div>
        <div>
          <label class="label">Min samples</label>
          <input id="dbMin" type="number" min="2" value="5" class="input" />
        </div>
        <div>
          <label class="label">Sample size</label>
          <input id="sampleSize" type="number" min="100" max="20000" value="5000" class="input" />
        </div>
        <div class="flex items-end">
          <button id="runBtn" class="btn-primary w-full">🟢 Run DBSCAN</button>
        </div>
      </div>
    `;
  } else if (activeMethod === "pca") {
    box.innerHTML = `
      <div class="grid grid-cols-3 gap-4 mb-4">
        <div>
          <label class="label">Components (blank = auto)</label>
          <input id="pcaN" type="number" min="1" max="20" class="input" placeholder="auto" />
        </div>
        <div>
          <label class="label">Sample size</label>
          <input id="sampleSize" type="number" min="100" max="20000" value="5000" class="input" />
        </div>
        <div class="flex items-end">
          <button id="runBtn" class="btn-primary w-full">🎯 Run PCA</button>
        </div>
      </div>
    `;
  } else if (activeMethod === "anomaly") {
    box.innerHTML = `
      <div class="grid grid-cols-3 gap-4 mb-4">
        <div>
          <label class="label">Contamination (%)</label>
          <input id="contam" type="number" step="0.01" min="0.001" max="0.5" value="0.05" class="input" />
        </div>
        <div>
          <label class="label">Sample size</label>
          <input id="sampleSize" type="number" min="100" max="20000" value="10000" class="input" />
        </div>
        <div class="flex items-end">
          <button id="runBtn" class="btn-primary w-full">⚠️ Detect Anomalies</button>
        </div>
      </div>
    `;
  }
  document.getElementById("runBtn").addEventListener("click", run);
}

async function run() {
  const features = Array.from(document.querySelectorAll(".feat-check:checked")).map(c => c.value);
  if (!currentDatasetId) { toast("Select dataset", "warning"); return; }
  if (!features.length) { toast("Select at least one feature", "warning"); return; }

  document.getElementById("empty").style.display = "none";
  document.getElementById("result").innerHTML = "";
  document.getElementById("loading").style.display = "block";

  try {
    const sampleSize = parseInt(document.getElementById("sampleSize")?.value || "5000");
    let body = { dataset_id: currentDatasetId, columns: features, sample_size: sampleSize };
    let endpoint = "";

    if (activeMethod === "kmeans") {
      body.n_clusters = parseInt(document.getElementById("kClusters").value);
      endpoint = "/api/ml/kmeans";
    } else if (activeMethod === "dbscan") {
      body.eps = parseFloat(document.getElementById("dbEps").value);
      body.min_samples = parseInt(document.getElementById("dbMin").value);
      endpoint = "/api/ml/dbscan";
    } else if (activeMethod === "pca") {
      const nRaw = document.getElementById("pcaN").value;
      body.n_components = nRaw ? parseInt(nRaw) : null;
      endpoint = "/api/ml/pca";
    } else if (activeMethod === "anomaly") {
      body.contamination = parseFloat(document.getElementById("contam").value);
      endpoint = "/api/ml/anomaly";
    }

    const res = await apiFetch(endpoint, { method: "POST", body });
    if (activeMethod === "kmeans") renderKMeans(res);
    else if (activeMethod === "dbscan") renderDBSCAN(res);
    else if (activeMethod === "pca") renderPCA(res);
    else if (activeMethod === "anomaly") renderAnomaly(res);
    document.getElementById("loading").style.display = "none";
  } catch (e) {
    document.getElementById("loading").style.display = "none";
    document.getElementById("result").innerHTML = '<div class="card p-6"><p class="text-sm text-red-600">' + esc(e.message) + '</p></div>';
  }
}

// ============ K-Means ============
function renderKMeans(r) {
  const q = r.quality || {};
  const box = document.getElementById("result");
  box.innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-4">K-Means Clustering (K=${r.n_clusters})</h2>
      <div class="grid grid-cols-4 gap-3 mb-6">
        <div class="stat-card"><p class="stat-label">Samples</p><p class="stat-value">${r.n_samples}</p></div>
        <div class="stat-card"><p class="stat-label">Clusters</p><p class="stat-value">${r.n_clusters}</p></div>
        <div class="stat-card"><p class="stat-label">Silhouette</p><p class="stat-value">${q.silhouette?.toFixed(4) ?? '—'}</p></div>
        <div class="stat-card"><p class="stat-label">Davies-Bouldin</p><p class="stat-value">${q.davies_bouldin?.toFixed(4) ?? '—'}</p></div>
      </div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Cluster Visualization (PCA 2D)</h3>
      <div style="height:400px" class="mb-6"><canvas id="clusterChart"></canvas></div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Elbow Method</h3>
      <div style="height:280px" class="mb-6"><canvas id="elbowChart"></canvas></div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Cluster Sizes</h3>
      <div class="mb-4">
        ${r.cluster_sizes.map((c, i) => `<span class="cluster-chip" style="background:${CLUSTER_COLORS[i % CLUSTER_COLORS.length]}20;color:${CLUSTER_COLORS[i % CLUSTER_COLORS.length]}">Cluster ${c.cluster}: ${c.count} rows</span>`).join("")}
      </div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Centroids</h3>
      <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:6px">
        <table class="data-table">
          <thead><tr><th>Cluster</th>${Object.keys(r.centroids[0].center).map(k => `<th style="text-align:right">${esc(k)}</th>`).join("")}</tr></thead>
          <tbody>
            ${r.centroids.map(c => `<tr>
              <td><strong style="color:${CLUSTER_COLORS[c.cluster % CLUSTER_COLORS.length]}">Cluster ${c.cluster}</strong></td>
              ${Object.values(c.center).map(v => `<td style="text-align:right">${v}</td>`).join("")}
            </tr>`).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
  setTimeout(() => renderScatter("clusterChart", r.vis_points, r.n_clusters), 100);
  setTimeout(() => renderElbow(r.elbow), 200);
}

function renderScatter(canvasId, points, nClusters) {
  const ctx = document.getElementById(canvasId).getContext("2d");
  if (charts[canvasId]) charts[canvasId].destroy();

  const grouped = {};
  points.forEach(p => {
    if (!grouped[p.label]) grouped[p.label] = [];
    grouped[p.label].push({ x: p.x, y: p.y });
  });

  const datasets = Object.keys(grouped).map(label => {
    const idx = parseInt(label);
    const color = idx === -1 ? "#a8a29e" : CLUSTER_COLORS[idx % CLUSTER_COLORS.length];
    return {
      label: idx === -1 ? "Noise" : "Cluster " + idx,
      data: grouped[label],
      backgroundColor: color + "80",
      borderColor: color,
      pointRadius: 3,
      pointHoverRadius: 5,
    };
  });

  charts[canvasId] = new Chart(ctx, {
    type: "scatter",
    data: { datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" } },
      scales: {
        x: { title: { display: true, text: "PC1" }, grid: { color: "#e7e5e4" } },
        y: { title: { display: true, text: "PC2" }, grid: { color: "#e7e5e4" } },
      },
    },
  });
}

function renderElbow(elbow) {
  const ctx = document.getElementById("elbowChart").getContext("2d");
  if (charts.elbow) charts.elbow.destroy();
  charts.elbow = new Chart(ctx, {
    type: "line",
    data: {
      labels: elbow.map(e => "K=" + e.k),
      datasets: [{
        label: "Inertia",
        data: elbow.map(e => e.inertia),
        borderColor: "#047857",
        backgroundColor: "rgba(4,120,87,0.1)",
        borderWidth: 2, tension: 0.2, fill: true,
        pointRadius: 4, pointBackgroundColor: "#047857",
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: "#e7e5e4" } },
        y: { grid: { color: "#e7e5e4" } },
      },
    },
  });
}

// ============ DBSCAN ============
function renderDBSCAN(r) {
  const q = r.quality || {};
  const box = document.getElementById("result");
  box.innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-4">DBSCAN Clustering</h2>
      <div class="grid grid-cols-4 gap-3 mb-6">
        <div class="stat-card"><p class="stat-label">Samples</p><p class="stat-value">${r.n_samples}</p></div>
        <div class="stat-card"><p class="stat-label">Clusters</p><p class="stat-value">${r.n_clusters}</p></div>
        <div class="stat-card"><p class="stat-label">Noise points</p><p class="stat-value">${r.n_noise}</p></div>
        <div class="stat-card"><p class="stat-label">Silhouette</p><p class="stat-value">${q.silhouette?.toFixed(4) ?? '—'}</p></div>
      </div>
      <p class="text-xs text-stone-500 mb-4">eps = ${r.eps} · min_samples = ${r.min_samples}</p>
      <div style="height:400px"><canvas id="clusterChart"></canvas></div>
    </div>
  `;
  setTimeout(() => renderScatter("clusterChart", r.vis_points, r.n_clusters), 100);
}

// ============ PCA ============
function renderPCA(r) {
  const box = document.getElementById("result");
  const total = (r.cumulative_variance[r.cumulative_variance.length - 1] * 100).toFixed(2);
  const pcsTo80 = r.cumulative_variance.findIndex(v => v >= 0.8) + 1;
  const pcsTo95 = r.cumulative_variance.findIndex(v => v >= 0.95) + 1;

  box.innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-4">PCA Analysis</h2>
      <div class="grid grid-cols-4 gap-3 mb-6">
        <div class="stat-card"><p class="stat-label">Original Features</p><p class="stat-value">${r.n_features_original}</p></div>
        <div class="stat-card"><p class="stat-label">Components Kept</p><p class="stat-value">${r.n_components}</p></div>
        <div class="stat-card"><p class="stat-label">PCs for 80%</p><p class="stat-value">${pcsTo80 || '—'}</p></div>
        <div class="stat-card"><p class="stat-label">PCs for 95%</p><p class="stat-value">${pcsTo95 || '—'}</p></div>
      </div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Variance Explained</h3>
      <div style="height:280px" class="mb-6"><canvas id="varChart"></canvas></div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">2D Projection</h3>
      <div style="height:400px" class="mb-6"><canvas id="pcaScatter"></canvas></div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Component Loadings</h3>
      <div class="space-y-3">
        ${r.loadings.slice(0, 5).map(l => `
          <details style="border:1px solid #e7e5e4;border-radius:6px">
            <summary class="p-3 cursor-pointer text-sm font-medium" style="background:#fafaf9">
              ${l.pc} — ${l.variance_pct}% variance
            </summary>
            <div class="p-3">
              <div class="grid grid-cols-3 gap-2 text-xs">
                ${Object.entries(l.weights).map(([k, v]) => `
                  <div style="display:flex;justify-content:space-between">
                    <span class="text-stone-600">${esc(k)}</span>
                    <span style="font-weight:600;color:${v > 0 ? '#047857' : '#b91c1c'}">${v}</span>
                  </div>
                `).join("")}
              </div>
            </div>
          </details>
        `).join("")}
      </div>
    </div>
  `;
  setTimeout(() => {
    const ctx = document.getElementById("varChart").getContext("2d");
    if (charts.var) charts.var.destroy();
    charts.var = new Chart(ctx, {
      type: "bar",
      data: {
        labels: r.explained_variance.map((_, i) => "PC" + (i + 1)),
        datasets: [
          {
            label: "Individual",
            data: r.explained_variance.map(v => v * 100),
            backgroundColor: "#047857",
            borderRadius: 4,
          },
          {
            type: "line",
            label: "Cumulative",
            data: r.cumulative_variance.map(v => v * 100),
            borderColor: "#b45309",
            backgroundColor: "transparent",
            borderWidth: 2, tension: 0.2,
            pointRadius: 4, pointBackgroundColor: "#b45309",
          },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } },
        scales: {
          x: { grid: { color: "#e7e5e4" } },
          y: { grid: { color: "#e7e5e4" }, title: { display: true, text: "Variance %" } },
        },
      },
    });

    const sctx = document.getElementById("pcaScatter").getContext("2d");
    if (charts.pca) charts.pca.destroy();
    charts.pca = new Chart(sctx, {
      type: "scatter",
      data: {
        datasets: [{
          label: "Samples",
          data: r.vis_points.map(p => ({ x: p.pc1, y: p.pc2 })),
          backgroundColor: "rgba(4,120,87,0.6)",
          pointRadius: 3,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { title: { display: true, text: "PC1" }, grid: { color: "#e7e5e4" } },
          y: { title: { display: true, text: "PC2" }, grid: { color: "#e7e5e4" } },
        },
      },
    });
  }, 100);
}

// ============ Anomaly ============
function renderAnomaly(r) {
  const box = document.getElementById("result");
  box.innerHTML = `
    <div class="card p-6 mb-6">
      <h2 class="font-semibold text-stone-900 text-lg mb-4">Anomaly Detection (Isolation Forest)</h2>
      <div class="grid grid-cols-4 gap-3 mb-6">
        <div class="stat-card"><p class="stat-label">Samples</p><p class="stat-value">${r.n_samples}</p></div>
        <div class="stat-card"><p class="stat-label">Anomalies</p><p class="stat-value" style="color:#b91c1c">${r.n_anomalies}</p></div>
        <div class="stat-card"><p class="stat-label">Normal</p><p class="stat-value">${r.n_normal}</p></div>
        <div class="stat-card"><p class="stat-label">Anomaly %</p><p class="stat-value">${r.anomaly_pct}%</p></div>
      </div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Distribution (PCA 2D)</h3>
      <div style="height:400px" class="mb-6"><canvas id="anomalyChart"></canvas></div>
      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Top Anomalies</h3>
      ${r.top_anomalies.length ? `
        <div class="overflow-auto" style="border:1px solid #e7e5e4;border-radius:6px">
          <table class="data-table">
            <thead><tr>
              <th>Row</th><th>Score</th>
              ${Object.keys(r.top_anomalies[0].values).map(k => `<th style="text-align:right">${esc(k)}</th>`).join("")}
            </tr></thead>
            <tbody>
              ${r.top_anomalies.map(a => `<tr>
                <td><strong>${a.row_index}</strong></td>
                <td style="color:#b91c1c;font-family:monospace">${a.score}</td>
                ${Object.values(a.values).map(v => `<td style="text-align:right">${v}</td>`).join("")}
              </tr>`).join("")}
            </tbody>
          </table>
        </div>
      ` : '<p class="text-sm text-stone-500">No anomalies detected at this contamination level.</p>'}
    </div>
  `;

  setTimeout(() => {
    const ctx = document.getElementById("anomalyChart").getContext("2d");
    if (charts.anomaly) charts.anomaly.destroy();
    const normalPts = r.vis_points.filter(p => p.label !== -1).map(p => ({ x: p.x, y: p.y }));
    const anomalyPts = r.vis_points.filter(p => p.label === -1).map(p => ({ x: p.x, y: p.y }));
    charts.anomaly = new Chart(ctx, {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "Normal",
            data: normalPts,
            backgroundColor: "rgba(4,120,87,0.5)",
            pointRadius: 3,
          },
          {
            label: "Anomaly",
            data: anomalyPts,
            backgroundColor: "rgba(185,28,28,0.9)",
            pointRadius: 5,
          },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } },
        scales: {
          x: { title: { display: true, text: "PC1" }, grid: { color: "#e7e5e4" } },
          y: { title: { display: true, text: "PC2" }, grid: { color: "#e7e5e4" } },
        },
      },
    });
  }, 100);
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

loadDatasets();
renderConfig();
document.addEventListener("neda:dataset-uploaded", loadDatasets);
