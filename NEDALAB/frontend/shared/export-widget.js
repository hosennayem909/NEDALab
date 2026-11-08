// Universal Export Widget
(function () {
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    if (!localStorage.getItem("neda_token")) return;
    if (document.getElementById("nedaExportFab")) return;

    // Only show on pages with a dataset selected
    const datasetSelects = document.querySelectorAll(
      "#datasetSelect, #formulaDataset, #leftDataset, #applyDataset"
    );
    if (!datasetSelects.length) return;

    const fab = document.createElement("button");
    fab.id = "nedaExportFab";
    fab.type = "button";
    fab.className = "neda-export-fab";
    fab.innerHTML = '📥 <span class="label">Export</span>';
    document.body.appendChild(fab);

    const menu = document.createElement("div");
    menu.id = "nedaExportMenu";
    menu.className = "neda-export-menu hidden";
    menu.innerHTML = `
      <button id="nedaExportExcel">
        <span style="font-size:16px">📊</span>
        <span>Export as Excel (.xlsx)</span>
      </button>
      <button id="nedaExportPdf">
        <span style="font-size:16px">📄</span>
        <span>Export PDF report</span>
      </button>
    `;
    document.body.appendChild(menu);

    function openMenu() { menu.classList.remove("hidden"); }
    function closeMenu() { menu.classList.add("hidden"); }
    function toggleMenu() { menu.classList.toggle("hidden"); }

    fab.addEventListener("click", (e) => { e.stopPropagation(); toggleMenu(); });
    document.addEventListener("click", (e) => {
      if (!menu.contains(e.target) && e.target !== fab) closeMenu();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeMenu();
    });

    function getCurrentDatasetId() {
      for (const sel of datasetSelects) {
        if (sel && sel.value) return sel.value;
      }
      return null;
    }

    function download(url, filename) {
      const token = localStorage.getItem("neda_token");
      if (typeof toast === "function") toast("Generating " + filename + "...", "info", 2500);

      fetch(url, { headers: { Authorization: "Bearer " + token } })
        .then(res => {
          if (!res.ok) return res.json().then(d => { throw new Error(d.detail || "Export failed"); });
          return res.blob();
        })
        .then(blob => {
          const a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = filename;
          a.click();
          URL.revokeObjectURL(a.href);
          if (typeof toast === "function") toast("Downloaded: " + filename, "success");
          closeMenu();
        })
        .catch(err => {
          if (typeof toast === "function") toast(err.message, "error");
          else alert(err.message);
        });
    }

    document.getElementById("nedaExportExcel").addEventListener("click", () => {
      const id = getCurrentDatasetId();
      if (!id) { if (typeof toast === "function") toast("Select a dataset first", "warning"); return; }
      download(`${window.NEDA_API_BASE}/api/export/dataset/${id}/excel`, `dataset_${id}.xlsx`);
    });

    document.getElementById("nedaExportPdf").addEventListener("click", () => {
      const id = getCurrentDatasetId();
      if (!id) { if (typeof toast === "function") toast("Select a dataset first", "warning"); return; }
      download(`${window.NEDA_API_BASE}/api/export/dataset/${id}/pdf`, `dataset_${id}_report.pdf`);
    });
  });
})();
