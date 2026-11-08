// NEDA LAB — UI helpers (toast, spinner, confirm)

function ensureToastContainer() {
  let c = document.getElementById("toastContainer");
  if (!c) {
    c = document.createElement("div");
    c.id = "toastContainer";
    c.style.cssText = `
      position: fixed; top: 20px; right: 20px; z-index: 9999;
      display: flex; flex-direction: column; gap: 10px;
      max-width: 360px; pointer-events: none;
    `;
    document.body.appendChild(c);
  }
  return c;
}

function toast(message, type = "info", duration = 3500) {
  const c = ensureToastContainer();
  const el = document.createElement("div");
  const colors = {
    success: { bg: "#ecfdf5", border: "#047857", text: "#065f46", icon: "✓" },
    error:   { bg: "#fef2f2", border: "#b91c1c", text: "#7f1d1d", icon: "!" },
    info:    { bg: "#eff6ff", border: "#1d4ed8", text: "#1e3a8a", icon: "i" },
    warning: { bg: "#fffbeb", border: "#b45309", text: "#78350f", icon: "⚠" },
  };
  const c2 = colors[type] || colors.info;

  el.style.cssText = `
    background: ${c2.bg};
    border-left: 4px solid ${c2.border};
    color: ${c2.text};
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 14px;
    font-family: 'IBM Plex Sans', sans-serif;
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    display: flex; align-items: center; gap: 10px;
    opacity: 0; transform: translateX(20px);
    transition: all 0.25s ease;
    pointer-events: auto;
  `;
  el.innerHTML = `
    <span style="font-weight:700;font-size:15px;width:20px;height:20px;display:flex;align-items:center;justify-content:center;border-radius:50%;background:${c2.border};color:white;flex-shrink:0">${c2.icon}</span>
    <span style="flex:1">${message}</span>
  `;
  c.appendChild(el);

  requestAnimationFrame(() => {
    el.style.opacity = "1";
    el.style.transform = "translateX(0)";
  });

  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transform = "translateX(20px)";
    setTimeout(() => el.remove(), 300);
  }, duration);
}

function showLoading(element, text = "Loading...") {
  if (!element) return;
  const prev = element.innerHTML;
  element.dataset.prevHtml = prev;
  element.innerHTML = `
    <div style="display:flex;align-items:center;gap:10px;color:#78716c;font-size:14px;padding:12px 0">
      <span class="spinner"></span>
      <span>${text}</span>
    </div>`;
}

function hideLoading(element, fallback = "") {
  if (!element) return;
  element.innerHTML = element.dataset.prevHtml || fallback;
}

function skeletonRows(count = 3) {
  let html = "";
  for (let i = 0; i < count; i++) {
    html += `
      <div class="skeleton-row" style="height:60px;border-radius:8px;margin-bottom:8px"></div>
    `;
  }
  return html;
}
