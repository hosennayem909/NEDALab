// Upload Widget v3 - clean structure
(function () {
  const API_BASE = window.NEDA_API_BASE || "http://127.0.0.1:8000";
  window.NEDA_API_BASE = API_BASE;

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    if (!localStorage.getItem("neda_token")) return;
    if (document.getElementById("nedaUploadFab")) return;

    let selectedPreset = "standard";

    // FAB button
    const fab = document.createElement("button");
    fab.id = "nedaUploadFab";
    fab.type = "button";
    fab.className = "neda-upload-fab";
    fab.innerHTML = '📤 <span class="label">Upload</span>';
    document.body.appendChild(fab);

    // Overlay
    const overlay = document.createElement("div");
    overlay.id = "nedaUploadOverlay";
    overlay.className = "neda-modal-overlay hidden";

    // Modal built as HTML string (well-formed)
    overlay.innerHTML = [
      '<div class="neda-modal" role="dialog">',
      '  <div class="neda-modal-header">',
      '    <h3 class="neda-modal-title">Upload dataset</h3>',
      '    <button class="neda-modal-close" type="button" aria-label="Close">&times;</button>',
      '  </div>',
      '  <div class="neda-modal-body">',
      '    <div class="neda-drop-zone" id="nedaDropZone">',
      '      <div class="neda-drop-icon">📁</div>',
      '      <p class="neda-drop-text">Drop CSV or Excel here</p>',
      '      <p class="neda-drop-hint">or click to browse</p>',
      '      <div class="neda-file-chosen" id="nedaFileChosen"></div>',
      '    </div>',
      '    <input id="nedaFileInput" type="file" accept=".csv,.xlsx,.xls" style="display:none" />',
      '    <div class="neda-preset-section">',
      '      <p class="neda-preset-label">Cleaning preset</p>',
      '      <div class="neda-preset-grid">',
      '        <div class="neda-preset-card" data-preset="minimal">',
      '          <p class="neda-preset-title">Minimal</p>',
      '          <p class="neda-preset-desc">Trim only</p>',
      '        </div>',
      '        <div class="neda-preset-card active" data-preset="standard">',
      '          <p class="neda-preset-title">Standard</p>',
      '          <p class="neda-preset-desc">Smart fill</p>',
      '        </div>',
      '        <div class="neda-preset-card" data-preset="aggressive">',
      '          <p class="neda-preset-title">Aggressive</p>',
      '          <p class="neda-preset-desc">+outliers</p>',
      '        </div>',
      '        <div class="neda-preset-card" data-preset="custom">',
      '          <p class="neda-preset-title">Custom</p>',
      '          <p class="neda-preset-desc">Advanced</p>',
      '        </div>',
      '      </div>',
      '    </div>',
      '  </div>',
      '  <div class="neda-modal-footer">',
      '    <button class="neda-btn-cancel" type="button" id="nedaCancelBtn">Cancel</button>',
      '    <button class="neda-btn-upload" type="button" id="nedaUploadBtn" disabled>Upload &amp; Clean</button>',
      '  </div>',
      '</div>'
    ].join('');

    document.body.appendChild(overlay);

    const fileInput = document.getElementById("nedaFileInput");
    const fileChosen = document.getElementById("nedaFileChosen");
    const uploadBtn = document.getElementById("nedaUploadBtn");
    const dropZone = document.getElementById("nedaDropZone");

    function openModal() {
      overlay.classList.remove("hidden");
      document.body.style.overflow = "hidden";
    }
    function closeModal() {
      overlay.classList.add("hidden");
      document.body.style.overflow = "";
      fileInput.value = "";
      fileChosen.textContent = "";
      fileChosen.classList.remove("show");
      uploadBtn.disabled = true;
    }

    fab.addEventListener("click", openModal);
    overlay.querySelector(".neda-modal-close").addEventListener("click", closeModal);
    document.getElementById("nedaCancelBtn").addEventListener("click", closeModal);
    overlay.addEventListener("click", function (e) { if (e.target === overlay) closeModal(); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !overlay.classList.contains("hidden")) closeModal();
    });

    // Drop zone click → trigger file input
    dropZone.addEventListener("click", function () { fileInput.click(); });

    // Preset selection
    overlay.querySelectorAll(".neda-preset-card").forEach(function (card) {
      card.addEventListener("click", function () {
        overlay.querySelectorAll(".neda-preset-card").forEach(function (c) { c.classList.remove("active"); });
        card.classList.add("active");
        selectedPreset = card.dataset.preset;
      });
    });

    fileInput.addEventListener("change", function () {
      if (fileInput.files.length) {
        fileChosen.textContent = "Selected: " + fileInput.files[0].name;
        fileChosen.classList.add("show");
        uploadBtn.disabled = false;
      }
    });

    ["dragenter", "dragover"].forEach(function (ev) {
      dropZone.addEventListener(ev, function (e) { e.preventDefault(); dropZone.classList.add("dragover"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      dropZone.addEventListener(ev, function (e) { e.preventDefault(); dropZone.classList.remove("dragover"); });
    });
    dropZone.addEventListener("drop", function (e) {
      const files = e.dataTransfer.files;
      if (files.length) {
        fileInput.files = files;
        fileChosen.textContent = "Selected: " + files[0].name;
        fileChosen.classList.add("show");
        uploadBtn.disabled = false;
      }
    });

    uploadBtn.addEventListener("click", async function () {
      if (!fileInput.files.length) return;
      uploadBtn.disabled = true;
      const origText = uploadBtn.innerHTML;
      uploadBtn.textContent = "Uploading...";

      const fd = new FormData();
      fd.append("file", fileInput.files[0]);
      fd.append("preset", selectedPreset);
      fd.append("drop_empty_rows", "true");
      fd.append("duplicates", "drop_all");
      fd.append("missing", "auto");
      fd.append("outliers", "keep");
      fd.append("strings", "trim");

      try {
        const token = localStorage.getItem("neda_token");
        const res = await fetch(API_BASE + "/api/data/upload-with-config", {
          method: "POST",
          headers: token ? { Authorization: "Bearer " + token } : {},
          body: fd,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Upload failed");

        if (typeof toast === "function") {
          toast("Saved (" + selectedPreset + "): " + data.row_count + " rows · " + data.column_count + " cols", "success", 4000);
        }

        if (typeof window.loadDatasets === "function") {
          try { window.loadDatasets(); } catch (e) {}
        }

        document.dispatchEvent(new CustomEvent("neda:dataset-uploaded", { detail: data }));
        closeModal();
      } catch (err) {
        if (typeof toast === "function") toast(err.message, "error");
        else alert(err.message);
        uploadBtn.disabled = false;
      } finally {
        uploadBtn.innerHTML = origText;
      }
    });
  });
})();
