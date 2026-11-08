// NEDA LAB — Dark Mode Toggle
(function () {
  const STORAGE_KEY = "neda_theme";

  // Apply saved theme ASAP
  function applyTheme(isDark) {
    document.body.classList.toggle("dark", isDark);
    const btn = document.getElementById("darkModeToggle");
    if (btn) {
      btn.innerHTML = isDark ? "☀️ Light mode" : "🌙 Dark mode";
    }
  }

  // Read saved preference
  const saved = localStorage.getItem(STORAGE_KEY);
  const isDarkOnLoad = saved === "dark";

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    applyTheme(isDarkOnLoad);
    injectToggle();
  });

  function injectToggle() {
    if (document.getElementById("darkModeToggle")) return;

    const logoutBtn = document.getElementById("logoutBtn");
    const btn = document.createElement("button");
    btn.id = "darkModeToggle";
    btn.type = "button";

    if (logoutBtn && logoutBtn.parentNode) {
      btn.className = "dark-toggle";
      logoutBtn.parentNode.insertBefore(btn, logoutBtn);
    } else {
      btn.className = "dark-toggle floating";
      document.body.appendChild(btn);
    }

    btn.innerHTML = document.body.classList.contains("dark")
      ? "☀️ Light mode"
      : "🌙 Dark mode";

    btn.addEventListener("click", function () {
      const nowDark = !document.body.classList.contains("dark");
      applyTheme(nowDark);
      localStorage.setItem(STORAGE_KEY, nowDark ? "dark" : "light");
    });
  }
})();
