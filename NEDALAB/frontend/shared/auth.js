function saveSession(token, user) {
  localStorage.setItem("neda_token", token);
  localStorage.setItem("neda_user", JSON.stringify(user));
}
function getUser() {
  const raw = localStorage.getItem("neda_user");
  return raw ? JSON.parse(raw) : null;
}
function logout() {
  localStorage.removeItem("neda_token");
  localStorage.removeItem("neda_user");
  window.location.href = "../login/login.html";
}
function requireAuth() {
  const hasToken = !!localStorage.getItem("neda_token");
  if (hasToken) return;

  const isFileProtocol = window.location.protocol === "file:";
  const isLocalHost = ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
  const isPublicPage = ["index.html", "login.html", "register.html"].includes(window.location.pathname.split("/").pop() || "");

  if (!isFileProtocol && !isLocalHost && !isPublicPage) {
    window.location.href = "../login/login.html";
  }
}

function renderSidebar(active) {
  const user = getUser();
  const nameEl = document.getElementById("sideUserName");
  const emailEl = document.getElementById("sideUserEmail");
  if (user && nameEl) nameEl.textContent = user.name;
  if (user && emailEl) emailEl.textContent = user.email;

  function applyActiveState() {
    const links = document.querySelectorAll(".sidebar-link");
    links.forEach(el => {
      el.classList.toggle("active", el.dataset.page === active);
    });
  }

  if (typeof window.renderSidebarNav === "function") {
    window.renderSidebarNav();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyActiveState, { once: true });
  } else {
    applyActiveState();
  }

  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) logoutBtn.addEventListener("click", logout);

  // Mobile menu
  const menuBtn = document.getElementById("mobileMenuBtn");
  const sidebar = document.querySelector(".app-sidebar");
  const overlay = document.getElementById("sidebarOverlay");
  if (menuBtn && sidebar) {
    menuBtn.addEventListener("click", () => {
      sidebar.classList.add("open");
      if (overlay) overlay.classList.add("show");
    });
  }
  if (overlay && sidebar) {
    overlay.addEventListener("click", () => {
      sidebar.classList.remove("open");
      overlay.classList.remove("show");
    });
  }
}
