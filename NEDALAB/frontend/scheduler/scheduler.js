requireAuth();
renderSidebar("scheduler");

let allTasks = [];
let selectedTaskForRuns = null;

async function loadDatasets() {
  const sel = document.getElementById("taskDataset");
  try {
    const data = await apiFetch("/api/data/datasets");
    sel.innerHTML = '<option value="">— Select dataset —</option>' +
      data.map(d => `<option value="${d.id}">${esc(d.filename)}</option>`).join("");
  } catch (e) { sel.innerHTML = '<option value="">Error</option>'; }
}

async function loadTasks() {
  const box = document.getElementById("taskList");
  try {
    allTasks = await apiFetch("/api/scheduler/tasks");
    if (!allTasks.length) {
      document.getElementById("empty").style.display = "block";
      box.innerHTML = "";
      return;
    }
    document.getElementById("empty").style.display = "none";
    box.innerHTML = `<div class="space-y-3">${allTasks.map(t => renderTask(t)).join("")}</div>`;
    attachHandlers();
  } catch (e) {
    box.innerHTML = '<p class="text-sm text-red-600">' + esc(e.message) + '</p>';
  }
}

function renderTask(t) {
  const lastRun = t.last_run_at ? new Date(t.last_run_at).toLocaleString() : "never";
  const nextRun = t.next_run_at ? new Date(t.next_run_at).toLocaleString() : "—";
  const typeIcon = { snapshot: "📸", export_excel: "📊", export_pdf: "📄" }[t.task_type] || "🔧";
  return `
    <div class="task-card ${t.enabled ? '' : 'disabled'}" data-tid="${t.id}">
      <div class="flex justify-between items-start flex-wrap gap-3">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap mb-1">
            <span style="font-size:18px">${typeIcon}</span>
            <p class="font-medium text-stone-900">${esc(t.name)}</p>
            <span class="status-badge ${t.enabled ? 'status-success' : 'status-running'}">${t.enabled ? 'enabled' : 'disabled'}</span>
            <span class="status-badge" style="background:#e7e5e4;color:#44403c">${esc(t.schedule)}</span>
          </div>
          <p class="text-xs text-stone-500">Type: ${esc(t.task_type)}</p>
          <p class="text-xs text-stone-500">Last run: ${lastRun} · Next: ${nextRun}</p>
        </div>
        <div class="flex gap-2 shrink-0 flex-wrap">
          <button class="task-run btn-primary" style="padding:6px 12px;font-size:12px">▶ Run Now</button>
          <button class="task-toggle btn-secondary" style="padding:6px 12px;font-size:12px">${t.enabled ? 'Disable' : 'Enable'}</button>
          <button class="task-runs btn-ghost">📜 History</button>
          <button class="task-delete btn-ghost" style="color:#b91c1c">🗑</button>
        </div>
      </div>
    </div>
  `;
}

function attachHandlers() {
  document.querySelectorAll(".task-card").forEach(card => {
    const id = parseInt(card.dataset.tid);
    const task = allTasks.find(x => x.id === id);
    card.querySelector(".task-run").addEventListener("click", () => runNow(id));
    card.querySelector(".task-toggle").addEventListener("click", () => toggleTask(id, task.enabled));
    card.querySelector(".task-runs").addEventListener("click", () => showRuns(id));
    card.querySelector(".task-delete").addEventListener("click", () => deleteTask(id));
  });
}

async function runNow(id) {
  const btn = document.querySelector(`.task-card[data-tid="${id}"] .task-run`);
  if (btn) { btn.disabled = true; btn.textContent = "Running..."; }
  try {
    const run = await apiFetch(`/api/scheduler/tasks/${id}/run`, { method: "POST" });
    if (run.status === "success") toast("Task completed successfully", "success");
    else toast("Task failed: " + (run.message || "unknown"), "error");
    loadTasks();
  } catch (e) {
    toast(e.message, "error");
    if (btn) { btn.disabled = false; btn.textContent = "▶ Run Now"; }
  }
}

async function toggleTask(id, currentlyEnabled) {
  try {
    await apiFetch(`/api/scheduler/tasks/${id}`, {
      method: "PUT",
      body: { enabled: !currentlyEnabled },
    });
    toast(currentlyEnabled ? "Task disabled" : "Task enabled", "success");
    loadTasks();
  } catch (e) { toast(e.message, "error"); }
}

async function deleteTask(id) {
  if (!confirm("Delete this task?")) return;
  try {
    await apiFetch(`/api/scheduler/tasks/${id}`, { method: "DELETE" });
    toast("Task deleted", "success");
    loadTasks();
    document.getElementById("runsPanel").innerHTML = "";
  } catch (e) { toast(e.message, "error"); }
}

async function showRuns(id) {
  selectedTaskForRuns = id;
  const box = document.getElementById("runsPanel");
  box.innerHTML = '<div class="card p-6"><span class="spinner"></span> Loading history...</div>';
  try {
    const runs = await apiFetch(`/api/scheduler/tasks/${id}/runs?limit=20`);
    if (!runs.length) {
      box.innerHTML = '<div class="card p-6"><p class="text-sm text-stone-500">No runs yet.</p></div>';
      return;
    }
    box.innerHTML = `
      <div class="card p-6">
        <h3 class="font-semibold text-stone-900 mb-3">Run History</h3>
        <table class="data-table">
          <thead><tr>
            <th>#</th><th>Status</th><th>Started</th><th>Completed</th><th>Message</th>
          </tr></thead>
          <tbody>
            ${runs.map(r => `
              <tr>
                <td>${r.id}</td>
                <td><span class="status-badge status-${r.status}">${esc(r.status)}</span></td>
                <td>${r.started_at ? new Date(r.started_at).toLocaleString() : '—'}</td>
                <td>${r.completed_at ? new Date(r.completed_at).toLocaleString() : '—'}</td>
                <td class="text-xs">${esc(r.message || '')}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    box.innerHTML = '<p class="text-sm text-red-600">' + esc(e.message) + '</p>';
  }
}

// New task form
document.getElementById("newTaskBtn").addEventListener("click", () => {
  document.getElementById("newTaskForm").style.display = "block";
  document.getElementById("newTaskBtn").style.display = "none";
});
document.getElementById("cancelNewBtn").addEventListener("click", () => {
  document.getElementById("newTaskForm").style.display = "none";
  document.getElementById("newTaskBtn").style.display = "inline-block";
});

document.getElementById("createTaskBtn").addEventListener("click", async () => {
  const name = document.getElementById("taskName").value.trim();
  const task_type = document.getElementById("taskType").value;
  const dataset_id = document.getElementById("taskDataset").value ? parseInt(document.getElementById("taskDataset").value) : null;
  const schedule = document.getElementById("taskSchedule").value;

  if (!name) { toast("Enter task name", "warning"); return; }
  if (!dataset_id) { toast("Select dataset", "warning"); return; }

  const btn = document.getElementById("createTaskBtn");
  btn.disabled = true;
  try {
    await apiFetch("/api/scheduler/tasks", {
      method: "POST",
      body: { name, task_type, dataset_id, schedule, enabled: true },
    });
    toast("Task created", "success");
    document.getElementById("newTaskForm").style.display = "none";
    document.getElementById("newTaskBtn").style.display = "inline-block";
    document.getElementById("taskName").value = "";
    loadTasks();
  } catch (e) {
    toast(e.message, "error");
  } finally {
    btn.disabled = false;
  }
});

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

loadDatasets();
loadTasks();
document.addEventListener("neda:dataset-uploaded", () => loadDatasets());
