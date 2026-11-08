// NEDA LAB — Notifications (clean)
(function () {
  const API_BASE = window.NEDA_API_BASE || "http://127.0.0.1:8000";
  window.NEDA_API_BASE = API_BASE;
  const POLL_MS = 30000;
  let pollTimer = null;
  let panelOpen = false;

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    injectBell();
    refreshUnread();
    pollTimer = setInterval(refreshUnread, POLL_MS);
    window.addEventListener("resize", () => { if (panelOpen) positionPanel(); });
    window.addEventListener("scroll", () => { if (panelOpen) positionPanel(); }, true);
  });

  function injectBell() {
    if (document.getElementById("notifBtn")) return;
    const logoutBtn = document.getElementById("logoutBtn");
    if (!logoutBtn || !logoutBtn.parentNode) return;

    // Button wrapper inside sidebar
    const wrap = document.createElement("div");
    wrap.id = "notifWrap";
    wrap.style.cssText = "margin-bottom:8px;";
    wrap.innerHTML = `
      <button id="notifBtn" type="button" class="notif-btn">
        <span>🔔 Notifications</span>
        <span id="notifBadge" class="notif-badge hidden">0</span>
      </button>`;
    logoutBtn.parentNode.insertBefore(wrap, logoutBtn);

    // Panel at body level (fixed position)
    const panel = document.createElement("div");
    panel.id = "notifPanel";
    panel.className = "notif-panel hidden";
    panel.innerHTML = `
      <div class="notif-header">
        <span class="notif-title">Activity</span>
        <div class="notif-actions">
          <button id="notifMarkAll" type="button" class="notif-link">Mark all read</button>
          <button id="notifClearAll" type="button" class="notif-link danger">Clear all</button>
        </div>
      </div>
      <div id="notifList" class="notif-list">
        <p class="notif-empty">Loading...</p>
      </div>`;
    document.body.appendChild(panel);

    document.getElementById("notifBtn").addEventListener("click", (e) => {
      e.stopPropagation();
      togglePanel();
    });
    document.getElementById("notifMarkAll").addEventListener("click", markAllRead);
    document.getElementById("notifClearAll").addEventListener("click", clearAll);

    document.addEventListener("click", (e) => {
      if (!panelOpen) return;
      const p = document.getElementById("notifPanel");
      const b = document.getElementById("notifBtn");
      if (!p || !b) return;
      if (!p.contains(e.target) && !b.contains(e.target)) closePanel();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && panelOpen) closePanel();
    });
  }

  function togglePanel() {
    if (panelOpen) closePanel(); else openPanel();
  }

  function openPanel() {
    panelOpen = true;
    positionPanel();
    const p = document.getElementById("notifPanel");
    if (!p) return;
    p.classList.remove("hidden");
    loadList();
  }

  function positionPanel() {
    const btn = document.getElementById("notifBtn");
    const panel = document.getElementById("notifPanel");
    if (!btn || !panel) return;

    const rect = btn.getBoundingClientRect();
    const sidebar = document.querySelector(".app-sidebar");
    const sidebarRight = sidebar ? sidebar.getBoundingClientRect().right : rect.right;

    const GAP = 8;
    const PANEL_WIDTH = 380;
    let left = sidebarRight + GAP;

    const maxLeft = window.innerWidth - PANEL_WIDTH - 16;
    if (left > maxLeft) left = maxLeft;
    if (left < 16) left = 16;

    let bottom = window.innerHeight - rect.top + GAP;
    // ensure panel fits in viewport
    const maxBottom = window.innerHeight - 40;
    if (bottom > maxBottom) bottom = maxBottom;

    panel.style.setProperty("--notif-left", left + "px");
    panel.style.setProperty("--notif-bottom", bottom + "px");
  }

  function closePanel() {
    panelOpen = false;
    const p = document.getElementById("notifPanel");
    if (p) p.classList.add("hidden");
  }

  async function refreshUnread() {
    try {
      const token = localStorage.getItem("neda_token");
      if (!token) return;
      const res = await fetch(API_BASE + "/api/notifications/unread-count", {
        headers: { Authorization: "Bearer " + token },
      });
      if (!res.ok) return;
      const data = await res.json();
      updateBadge(data.unread_count);
    } catch (e) {}
  }

  function updateBadge(count) {
    const b = document.getElementById("notifBadge");
    if (!b) return;
    if (count > 0) {
      b.textContent = count > 99 ? "99+" : String(count);
      b.classList.remove("hidden");
    } else {
      b.classList.add("hidden");
    }
  }

  async function loadList() {
    const box = document.getElementById("notifList");
    if (!box) return;
    box.innerHTML = '<p class="notif-empty">Loading...</p>';
    try {
      const token = localStorage.getItem("neda_token");
      const res = await fetch(API_BASE + "/api/notifications?limit=40", {
        headers: { Authorization: "Bearer " + token },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to load");
      updateBadge(data.unread_count || 0);
      renderList(data.items || []);
    } catch (err) {
      box.innerHTML = '<p class="notif-empty error">' + err.message + '</p>';
    }
  }

  function renderList(items) {
    const box = document.getElementById("notifList");
    if (!items.length) {
      box.innerHTML = `
        <div class="notif-empty-block">
          <div style="font-size:32px;margin-bottom:8px;">📭</div>
          <p style="font-weight:500;">No notifications yet</p>
          <p style="font-size:12px;color:#a8a29e;margin-top:4px;">Your recent activity will show up here.</p>
        </div>`;
      return;
    }
    box.innerHTML = items.map(n => {
      const icon = iconFor(n.type);
      const time = timeAgo(n.created_at);
      const unreadClass = n.is_read ? "" : " unread";
      const linkAttr = n.link ? `data-link="${n.link}"` : "";
      return `
        <div class="notif-item${unreadClass}" data-id="${n.id}" ${linkAttr}>
          <div class="notif-icon">${icon}</div>
          <div class="notif-body">
            <p class="notif-item-title">${escapeHtml(n.title)}</p>
            ${n.message ? `<p class="notif-item-msg">${escapeHtml(n.message)}</p>` : ""}
            <p class="notif-item-time">${time}</p>
          </div>
          <button class="notif-del" data-del="${n.id}" title="Remove">×</button>
        </div>`;
    }).join("");

    box.querySelectorAll(".notif-item").forEach(el => {
      el.addEventListener("click", async (e) => {
        if (e.target.classList.contains("notif-del")) return;
        const id = el.dataset.id;
        const link = el.dataset.link;
        try {
          const token = localStorage.getItem("neda_token");
          await fetch(`${API_BASE}/api/notifications/${id}/read`, {
            method: "POST",
            headers: { Authorization: "Bearer " + token },
          });
          el.classList.remove("unread");
          refreshUnread();
          if (link) {
            const parts = window.location.pathname.split("/").slice(0, -1);
            const idx = parts.lastIndexOf("frontend");
            if (idx >= 0) {
              const base = parts.slice(0, idx + 1).join("/");
              window.location.href = base + link;
            } else {
              window.location.href = ".." + link;
            }
          }
        } catch (err) {}
      });
    });

    box.querySelectorAll(".notif-del").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const id = btn.dataset.del;
        try {
          const token = localStorage.getItem("neda_token");
          await fetch(`${API_BASE}/api/notifications/${id}`, {
            method: "DELETE",
            headers: { Authorization: "Bearer " + token },
          });
          loadList();
        } catch (err) {}
      });
    });
  }

  async function markAllRead() {
    try {
      const token = localStorage.getItem("neda_token");
      await fetch(API_BASE + "/api/notifications/read-all", {
        method: "POST",
        headers: { Authorization: "Bearer " + token },
      });
      loadList();
    } catch (e) {}
  }

  async function clearAll() {
    if (!confirm("Delete all notifications?")) return;
    try {
      const token = localStorage.getItem("neda_token");
      await fetch(API_BASE + "/api/notifications", {
        method: "DELETE",
        headers: { Authorization: "Bearer " + token },
      });
      loadList();
    } catch (e) {}
  }

  function iconFor(type) {
    if (type === "dataset_upload") return "📁";
    if (type === "model_train") return "📈";
    if (type === "aggregation") return "📊";
    if (type === "workspace_created") return "🗂️";
    if (type === "member_added" || type === "member_invited") return "👥";
    return "🔔";
  }

  function timeAgo(iso) {
    try {
      const d = new Date(iso);
      const sec = Math.floor((Date.now() - d.getTime()) / 1000);
      if (sec < 60) return "just now";
      if (sec < 3600) return Math.floor(sec / 60) + "m ago";
      if (sec < 86400) return Math.floor(sec / 3600) + "h ago";
      if (sec < 604800) return Math.floor(sec / 86400) + "d ago";
      return d.toLocaleDateString();
    } catch (e) { return ""; }
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }
})();
