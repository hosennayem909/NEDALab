(function () {
  function normalizeBrandLockups() {
    const brandHtml = '<span class="brand-mark">N</span><span class="brand-name"><span class="brand-word">NEDA</span><span class="brand-accent">Lab</span></span>';

    const directBrandNodes = document.querySelectorAll('.brand-lockup, .brand-anchor');
    directBrandNodes.forEach((node) => {
      if (!node.querySelector('.brand-mark')) {
        node.classList.add('brand-lockup');
        node.innerHTML = brandHtml;
      }
    });
  }

  const NAV_SECTIONS = [
    {
      title: "Overview",
      items: [
        { key: "dashboard", label: "Dashboard", icon: "📊", href: "../dashboard/dashboard.html" },
        { key: "workspace", label: "Workspaces", icon: "🗂", href: "../workspace/workspace.html" },
        { key: "profile", label: "Profile", icon: "👤", href: "../profile/profile.html" },
      ],
    },
    {
      title: "Data Preparation",
      items: [
        { key: "dataset", label: "Dataset Hub", icon: "📁", href: "../dashboard/dashboard.html" },
        { key: "stats", label: "Statistical Cleaning", icon: "📐", href: "../stats/stats.html" },
        { key: "adv-stats", label: "Advanced Cleaning", icon: "⚗️", href: "../adv-stats/adv-stats.html" },
        { key: "data-ops", label: "Data Operations", icon: "🧮", href: "../data-ops/data-ops.html" },
        { key: "quality", label: "Data Quality", icon: "✅", href: "../quality/quality.html" },
        { key: "feature-eng", label: "Feature Engineering", icon: "⚡", href: "../feature-eng/feature-eng.html" },
        { key: "versions", label: "Version History", icon: "📚", href: "../versions/versions.html" },
      ],
    },
    {
      title: "Research & Forecasting",
      items: [
        { key: "forecast", label: "Forecasting", icon: "📈", href: "../forecast/forecast.html" },
        { key: "entity", label: "Entity Mapping", icon: "🔗", href: "../entity/entity.html" },
        { key: "econometrics", label: "Regression Analysis", icon: "📉", href: "../econometrics/econometrics.html" },
        { key: "stats-tests", label: "Statistical Tests", icon: "🔬", href: "../econometrics/stats-tests.html" },
        { key: "panel", label: "Panel Data", icon: "📊", href: "../econometrics/panel.html" },
        { key: "var", label: "VAR Analysis", icon: "🔄", href: "../econometrics/var.html" },
        { key: "hypothesis", label: "Hypothesis Tests", icon: "🧪", href: "../econometrics/hypothesis.html" },
        { key: "viz", label: "Visualization", icon: "📊", href: "../viz/viz.html" },
        { key: "scheduler", label: "Scheduler", icon: "⏰", href: "../scheduler/scheduler.html" },
      ],
    },
    {
      title: "Machine Learning",
      items: [
        { key: "ml", label: "Machine Learning", icon: "🤖", href: "../ml/ml.html" },
        { key: "ml-eval", label: "Model Evaluation", icon: "🎯", href: "../ml/evaluation.html" },
        { key: "ml-predict", label: "Predictions", icon: "🔮", href: "../ml/predict.html" },
        { key: "ml-unsup", label: "Unsupervised ML", icon: "🧩", href: "../ml/unsupervised.html" },
        { key: "ml-tune", label: "Tuning & SHAP", icon: "🎛️", href: "../ml/tuning.html" },
        { key: "automl", label: "AutoML Studio", icon: "✨", href: "../automl/automl.html" },
      ],
    },
  ];

  function renderSidebarNav() {
    const nav = document.getElementById("sidebarNav");
    if (!nav) return;

    const currentPath = window.location.pathname.split("/").pop() || "dashboard.html";

    nav.innerHTML = NAV_SECTIONS.map((section) => {
      const links = section.items.map((item) => {
        const isActive = currentPath === item.href.split("/").pop();
        return `
          <a href="${item.href}" data-page="${item.key}" class="sidebar-link ${isActive ? "active" : ""}">
            <span aria-hidden="true">${item.icon}</span>
            <span>${item.label}</span>
          </a>
        `;
      }).join("");

      return `
        <div class="nav-section">
          <div class="nav-section-title">${section.title}</div>
          ${links}
        </div>
      `;
    }).join("");
  }

  window.NEDA_NAV_SECTIONS = NAV_SECTIONS;
  window.renderSidebarNav = renderSidebarNav;

  function initBranding() {
    normalizeBrandLockups();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      renderSidebarNav();
      initBranding();
    });
  } else {
    renderSidebarNav();
    initBranding();
  }
})();
