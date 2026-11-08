requireAuth();
renderSidebar("ml");

let activeTab = "train";
let allAlgorithms = { classification: [], regression: [] };
let currentDatasetId = null;
let numericalColumns = [];
let categoricalColumns = [];

// Tab switching
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeTab = btn.dataset.tab;
    renderTab();
  });
});

async function renderTab() {
  if (activeTab === "train") return renderTrain();
  if (activeTab === "models") return renderModels();
  if (activeTab === "colab") return renderColab();
}

function renderColab() {
  const box = document.getElementById("tabContent");
  box.innerHTML = `
    <div class="split-grid grid grid-cols-3 gap-6">
      <section class="card p-5 h-fit">
        <h2 class="font-semibold text-stone-900 mb-4">Configure notebook</h2>
        <div class="space-y-3">
          <div>
            <label class="label" for="colabDatasetSelect">Saved dataset</label>
            <select id="colabDatasetSelect" class="input"><option value="">Loading datasets...</option></select>
          </div>
          <div>
            <label class="label" for="colabTargetSelect">Target column</label>
            <select id="colabTargetSelect" class="input" disabled><option value="">Select a dataset first</option></select>
          </div>
          <div>
            <label class="label" for="colabTaskSelect">Deep-learning task</label>
            <select id="colabTaskSelect" class="input">
              <option value="regression">Regression</option>
              <option value="classification">Classification</option>
            </select>
          </div>
          <button id="downloadColabBtn" class="btn-primary w-full" disabled>Download .ipynb</button>
          <p id="colabStatus" class="text-xs text-stone-500" role="status">Choose a saved dataset to begin.</p>
        </div>
      </section>
      <section class="col-span-2 card p-6 h-fit">
        <h2 class="font-semibold text-stone-900 mb-2">Run in Google Colab</h2>
        <p class="text-sm text-stone-600 mb-4">Training runs in Colab, not on this PC. Download the selected dataset as CSV from its Preview page, then upload that file when the notebook prompts.</p>
        <ol class="text-sm text-stone-600 list-decimal pl-5 space-y-2">
          <li>Open the downloaded notebook in Google Colab.</li>
          <li>Select a GPU runtime if you want accelerator support.</li>
          <li>Run the cells and upload the matching CSV.</li>
          <li>Evaluate the model and download the trained model artifacts.</li>
        </ol>
      </section>
    </div>
  `;

  const datasetSelect = document.getElementById("colabDatasetSelect");
  const targetSelect = document.getElementById("colabTargetSelect");
  const taskSelect = document.getElementById("colabTaskSelect");
  const downloadButton = document.getElementById("downloadColabBtn");
  const status = document.getElementById("colabStatus");

  datasetSelect.addEventListener("change", async () => {
    targetSelect.disabled = true;
    targetSelect.innerHTML = '<option value="">Loading columns...</option>';
    downloadButton.disabled = true;
    if (!datasetSelect.value) {
      targetSelect.innerHTML = '<option value="">Select a dataset first</option>';
      status.textContent = "Choose a saved dataset to begin.";
      return;
    }

    status.textContent = "Loading dataset columns...";
    try {
      const info = await apiFetch(`/api/data/datasets/${datasetSelect.value}/column-info`);
      const columns = info.all_columns || [];
      targetSelect.innerHTML = '<option value="">— Select target —</option>' +
        columns.map(column => `<option value="${esc(column)}">${esc(column)}</option>`).join("");
      targetSelect.disabled = !columns.length;
      status.textContent = columns.length
        ? `${columns.length} columns available. Confirm the prediction target.`
        : "No columns found in this dataset.";
    } catch (error) {
      targetSelect.innerHTML = '<option value="">Could not load columns</option>';
      status.textContent = error.message;
    }
  });

  const updateDownloadAvailability = () => {
    downloadButton.disabled = !datasetSelect.value || !targetSelect.value;
  };
  targetSelect.addEventListener("change", updateDownloadAvailability);
  taskSelect.addEventListener("change", updateDownloadAvailability);
  downloadButton.addEventListener("click", downloadColabNotebook);

  loadColabDatasets(datasetSelect, status);
}

async function loadColabDatasets(select, status) {
  try {
    const datasets = await apiFetch("/api/data/datasets");
    select.innerHTML = '<option value="">— Select dataset —</option>' +
      datasets.map(dataset => `<option value="${dataset.id}">${esc(dataset.filename)} (${Number(dataset.row_count).toLocaleString()} rows)</option>`).join("");
    if (!datasets.length) {
      select.innerHTML = '<option value="">No saved datasets</option>';
      status.textContent = "Upload a dataset before generating a notebook.";
    }
  } catch (error) {
    select.innerHTML = '<option value="">Could not load datasets</option>';
    status.textContent = error.message;
  }
}

  function downloadColabNotebook() {
    const datasetSelect = document.getElementById("colabDatasetSelect");
    const targetColumn = document.getElementById("colabTargetSelect").value;
    const taskType = document.getElementById("colabTaskSelect").value;
    const datasetName = datasetSelect.selectedOptions[0]?.textContent.replace(/ \(\d[\d,]* rows\)$/, "") || "dataset.csv";
    if (!datasetSelect.value || !targetColumn) return;

    const pythonCells = [
    `from google.colab import files
  import io
  import inspect
  import joblib
  import matplotlib.pyplot as plt
  import numpy as np
  import pandas as pd
  import tensorflow as tf
  from sklearn.compose import ColumnTransformer
  from sklearn.impute import SimpleImputer
  from sklearn.model_selection import train_test_split
  from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler
  from sklearn.pipeline import Pipeline

  print("TensorFlow:", tf.__version__)
  print("GPU devices:", tf.config.list_physical_devices("GPU"))

  uploaded = files.upload()
  if not uploaded:
    raise ValueError("Upload the CSV downloaded from NEDA LAB to continue.")

  dataset_name = next(iter(uploaded))
  df = pd.read_csv(io.BytesIO(uploaded[dataset_name]))
  target_column = ${JSON.stringify(targetColumn)}
  task_type = ${JSON.stringify(taskType)}

  if target_column not in df.columns:
    raise ValueError(f"Target column {target_column!r} was not found in {dataset_name}.")

  print(f"Loaded {dataset_name}: {df.shape[0]:,} rows × {df.shape[1]} columns")
  display(df.head())`,
    `data = df.dropna(subset=[target_column]).copy()
  label_encoder = None

  if task_type == "classification":
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(data[target_column].astype(str))
    if len(label_encoder.classes_) < 2:
      raise ValueError("Classification needs at least two target classes.")
  else:
    y = pd.to_numeric(data[target_column], errors="coerce")
    valid_target = y.notna()
    data = data.loc[valid_target].copy()
    y = y.loc[valid_target].to_numpy(dtype="float32")

  X = data.drop(columns=[target_column]).copy()
  if X.shape[1] == 0:
    raise ValueError("The dataset needs at least one feature column besides the target.")
  if len(data) < 5:
    raise ValueError("At least five valid rows are needed for a train/test split.")

  stratify = None
  if task_type == "classification":
    classes, class_counts = np.unique(y, return_counts=True)
    test_rows = max(1, int(np.ceil(len(y) * 0.2)))
    train_rows = len(y) - test_rows
    if len(classes) > 1 and class_counts.min() >= 2 and len(classes) <= min(test_rows, train_rows):
      stratify = y

  X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=stratify
  )
  print(f"Training rows: {len(X_train):,} · Test rows: {len(X_test):,}")`,
    `numeric_columns = X_train.select_dtypes(include=np.number).columns.tolist()
  categorical_columns = X_train.select_dtypes(exclude=np.number).columns.tolist()
  transformers = []

  if numeric_columns:
    numeric_pipeline = Pipeline([
      ("imputer", SimpleImputer(strategy="median")),
      ("scaler", StandardScaler()),
    ])
    transformers.append(("numeric", numeric_pipeline, numeric_columns))

  if categorical_columns:
    encoder_options = {"handle_unknown": "ignore"}
    if "sparse_output" in inspect.signature(OneHotEncoder).parameters:
      encoder_options["sparse_output"] = False
    else:
      encoder_options["sparse"] = False
    categorical_pipeline = Pipeline([
      ("imputer", SimpleImputer(strategy="most_frequent")),
      ("onehot", OneHotEncoder(**encoder_options)),
    ])
    transformers.append(("categorical", categorical_pipeline, categorical_columns))

  preprocessor = ColumnTransformer(transformers, remainder="drop")
  X_train_processed = preprocessor.fit_transform(X_train).astype("float32")
  X_test_processed = preprocessor.transform(X_test).astype("float32")
  print("Processed feature shape:", X_train_processed.shape)`,
    `tf.keras.utils.set_random_seed(42)
  inputs = tf.keras.Input(shape=(X_train_processed.shape[1],))
  x = tf.keras.layers.Dense(128, activation="relu")(inputs)
  x = tf.keras.layers.Dropout(0.2)(x)
  x = tf.keras.layers.Dense(64, activation="relu")(x)

  if task_type == "classification":
    class_count = len(label_encoder.classes_)
    if class_count == 2:
      outputs = tf.keras.layers.Dense(1, activation="sigmoid")(x)
      loss = "binary_crossentropy"
      metrics = ["accuracy"]
    else:
      outputs = tf.keras.layers.Dense(class_count, activation="softmax")(x)
      loss = "sparse_categorical_crossentropy"
      metrics = ["accuracy"]
  else:
    outputs = tf.keras.layers.Dense(1)(x)
    loss = "mse"
    metrics = ["mae"]

  model = tf.keras.Model(inputs=inputs, outputs=outputs)
  model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3), loss=loss, metrics=metrics)
  callbacks = [tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=8, restore_best_weights=True)] if len(X_train) >= 10 else []
  history = model.fit(
    X_train_processed,
    y_train,
    validation_split=0.2 if len(X_train) >= 10 else 0,
    epochs=100,
    batch_size=min(32, len(X_train)),
    callbacks=callbacks,
    verbose=1,
  )`,
    `test_metrics = model.evaluate(X_test_processed, y_test, verbose=0, return_dict=True)
  print("Test metrics:", {name: round(float(value), 4) for name, value in test_metrics.items()})

  plt.figure(figsize=(7, 4))
  plt.plot(history.history["loss"], label="Training loss")
  if "val_loss" in history.history:
    plt.plot(history.history["val_loss"], label="Validation loss")
  plt.xlabel("Epoch")
  plt.ylabel("Loss")
  plt.title("Training history")
  plt.legend()
  plt.grid(alpha=0.25)
  plt.show()

  if task_type == "classification":
    probabilities = model.predict(X_test_processed, verbose=0)
    predictions = (probabilities.ravel() >= 0.5).astype(int) if len(label_encoder.classes_) == 2 else probabilities.argmax(axis=1)
    from sklearn.metrics import classification_report
    print(classification_report(y_test, predictions, labels=np.arange(len(label_encoder.classes_)), target_names=label_encoder.classes_.astype(str), zero_division=0))
  else:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    predictions = model.predict(X_test_processed, verbose=0).ravel()
    rmse = float(np.sqrt(mean_squared_error(y_test, predictions)))
    print("Test MAE:", round(float(mean_absolute_error(y_test, predictions)), 4))
    print("Test RMSE:", round(rmse, 4))
    if len(y_test) > 1:
      print("Test R²:", round(float(r2_score(y_test, predictions)), 4))`,
    `model.save("neda_deep_learning_model.keras")
  joblib.dump({
    "preprocessor": preprocessor,
    "label_encoder": label_encoder,
    "task_type": task_type,
    "target_column": target_column,
  }, "neda_preprocessing.joblib")

  print("Saved model and preprocessing artifacts.")
  files.download("neda_deep_learning_model.keras")
  files.download("neda_preprocessing.joblib")`,
    ];

    const markdownCells = [
    `# NEDA LAB · Colab Deep Learning\n\nDataset: ${datasetName}\n\nTarget: ${targetColumn}\n\nTask: ${taskType}\n\nThis notebook trains in Google Colab, so model training does not use your PC's CPU/GPU. Before running, download this dataset as CSV from NEDA LAB and upload it when prompted. For larger data, choose a GPU runtime in Colab.`,
    `## 1. Load the CSV\n\nRun this cell and upload the CSV you downloaded from NEDA LAB. The target and task are preconfigured from your selection.`,
    `## 2. Prepare features and target\n\nThe notebook removes rows with missing targets and creates a train/test split. Classification labels are encoded automatically.`,
    `## 3. Preprocess data\n\nNumeric features are imputed and scaled; categorical features are imputed and one-hot encoded.`,
    `## 4. Train a neural network\n\nThe model uses TensorFlow/Keras and supports both binary/multiclass classification and regression. If enabled, Colab's GPU runtime is used automatically.`,
    `## 5. Evaluate\n\nReview test metrics and the learning curve. Results are measured on a holdout split, not the training rows.`,
    `## 6. Download artifacts\n\nThe trained Keras model and preprocessing configuration are downloaded separately so they can be used together for future predictions.`,
    ];

    const makeCell = (cellType, language, source, index) => ({
    cell_type: cellType,
    id: `neda-colab-${index + 1}`,
    metadata: { id: `neda-colab-${index + 1}`, language },
    source: source.split("\n").map((line, lineIndex, lines) => line + (lineIndex < lines.length - 1 ? "\n" : "")),
    ...(cellType === "code" ? { execution_count: null, outputs: [] } : {}),
    });

    const cells = [];
    const sectionCount = Math.min(markdownCells.length, pythonCells.length);
    for (let index = 0; index < sectionCount; index++) {
      cells.push(makeCell("markdown", "markdown", markdownCells[index], cells.length));
      cells.push(makeCell("code", "python", pythonCells[index], cells.length));
    }
    for (let index = sectionCount; index < markdownCells.length; index++) {
      cells.push(makeCell("markdown", "markdown", markdownCells[index], cells.length));
    }
    for (let index = sectionCount; index < pythonCells.length; index++) {
      cells.push(makeCell("code", "python", pythonCells[index], cells.length));
    }
    const notebook = {
    cells,
    metadata: {
      colab: { name: "NEDA_Colab_Deep_Learning.ipynb", provenance: [] },
      kernelspec: { display_name: "Python 3", language: "python", name: "python3" },
      language_info: { name: "python" },
    },
    nbformat: 4,
    nbformat_minor: 5,
    };

    const blob = new Blob([JSON.stringify(notebook, null, 2)], { type: "application/x-ipynb+json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${datasetName.replace(/[^a-z0-9._-]+/gi, "_").replace(/\.[^.]+$/, "")}_colab_deep_learning.ipynb`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    document.getElementById("colabStatus").textContent = "Notebook downloaded. Upload the matching CSV in Colab to run it.";
    toast("Colab notebook downloaded", "success");
  }

// ============ TRAIN TAB ============
async function renderTrain() {
  const box = document.getElementById("tabContent");
  box.innerHTML = `
    <div class="split-grid grid grid-cols-3 gap-6">
      <div class="card p-5 h-fit">
        <h2 class="font-semibold text-stone-900 mb-4">Configure Model</h2>
        <div class="space-y-3">
          <div>
            <label class="label">Dataset</label>
            <select id="datasetSelect" class="input"><option value="">Loading...</option></select>
          </div>
          <div id="configSection" style="display:none">
            <div>
              <label class="label">Task type</label>
              <select id="taskType" class="input">
                <option value="classification">Classification</option>
                <option value="regression">Regression</option>
              </select>
            </div>
            <div>
              <label class="label">Target column (Y)</label>
              <select id="targetSelect" class="input"></select>
            </div>
            <div>
              <label class="label">Algorithm</label>
              <select id="algoSelect" class="input"></select>
            </div>
            <div>
              <label class="label">Feature columns (X)</label>
              <div id="featureList" class="border rounded-md p-2 max-h-48 overflow-y-auto" style="border-color:#e7e5e4"></div>
            </div>
            <div>
              <label class="label">Test size: <span id="testSizeVal">20%</span></label>
              <input id="testSize" type="range" min="10" max="50" value="20" class="w-full" />
            </div>
            <button id="trainBtn" class="btn-primary w-full mt-2">🚀 Train Model</button>
          </div>
        </div>
      </div>

      <div class="col-span-2 space-y-4">
        <div id="empty" class="card p-10 text-center">
          <p class="text-4xl mb-3">🤖</p>
          <p class="font-medium text-stone-700">Configure and train a model</p>
          <p class="text-sm text-stone-500 mt-1">Results with metrics + feature importance will appear here.</p>
        </div>
        <div id="loading" style="display:none" class="card p-8 text-center">
          <span class="spinner"></span>
          <p class="text-sm text-stone-600 mt-2">Training model...</p>
        </div>
        <div id="result" style="display:none"></div>
      </div>
    </div>
  `;

  await loadDatasetsForTrain();
  await loadAlgorithms();
}

async function loadDatasetsForTrain() {
  const sel = document.getElementById("datasetSelect");
  try {
    const data = await apiFetch("/api/data/datasets");
    if (!data.length) { sel.innerHTML = '<option value="">No datasets</option>'; return; }
    sel.innerHTML = '<option value="">— Select dataset —</option>' +
      data.map(d => `<option value="${d.id}">${esc(d.filename)} (${d.row_count} rows)</option>`).join("");
    sel.addEventListener("change", onDatasetChange);
  } catch (e) { sel.innerHTML = '<option value="">Error</option>'; }
}

async function loadAlgorithms() {
  try {
    allAlgorithms = await apiFetch("/api/ml/algorithms");
  } catch (e) { /* ignore */ }
}

async function onDatasetChange() {
  const id = document.getElementById("datasetSelect").value;
  if (!id) {
    document.getElementById("configSection").style.display = "none";
    return;
  }
  currentDatasetId = parseInt(id);
  try {
    const info = await apiFetch("/api/data/datasets/" + currentDatasetId + "/column-info");
    numericalColumns = info.numeric_columns || [];
    categoricalColumns = info.all_columns.filter(c => !numericalColumns.includes(c));

    // Target selector: all columns
    const tgt = document.getElementById("targetSelect");
    tgt.innerHTML = '<option value="">— Select target —</option>' +
      info.all_columns.map(c => `<option value="${c}">${esc(c)}</option>`).join("");

    // Features: all columns
    const fl = document.getElementById("featureList");
    fl.innerHTML = info.all_columns.map(c => `
      <label class="flex items-center gap-2 text-sm py-0.5 cursor-pointer">
        <input type="checkbox" class="feature-check" value="${esc(c)}" style="accent-color:#047857" />
        <span class="text-stone-700">${esc(c)}</span>
      </label>
    `).join("");

    updateAlgorithmList();
    document.getElementById("configSection").style.display = "block";
  } catch (e) { toast(e.message, "error"); }
}

document.addEventListener("change", (e) => {
  if (e.target.id === "taskType") updateAlgorithmList();
  if (e.target.id === "testSize") {
    document.getElementById("testSizeVal").textContent = e.target.value + "%";
  }
});

function updateAlgorithmList() {
  const taskType = document.getElementById("taskType").value;
  const algos = allAlgorithms[taskType] || [];
  const sel = document.getElementById("algoSelect");
  sel.innerHTML = algos.map(a => `<option value="${a.value}">${esc(a.label)}</option>`).join("");
}

document.addEventListener("click", async (e) => {
  if (e.target.id !== "trainBtn") return;
  const target = document.getElementById("targetSelect").value;
  if (!target) { toast("Select target column", "warning"); return; }
  const features = Array.from(document.querySelectorAll(".feature-check:checked")).map(c => c.value);
  if (!features.length) { toast("Select at least one feature", "warning"); return; }
  if (features.includes(target)) { toast("Target cannot be in features", "warning"); return; }

  document.getElementById("empty").style.display = "none";
  document.getElementById("result").style.display = "none";
  document.getElementById("loading").style.display = "block";

  try {
    const payload = {
      dataset_id: currentDatasetId,
      target_column: target,
      feature_columns: features,
      task_type: document.getElementById("taskType").value,
      algorithm: document.getElementById("algoSelect").value,
      test_size: parseInt(document.getElementById("testSize").value) / 100,
      random_state: 42,
    };
    const res = await apiFetch("/api/ml/train", { method: "POST", body: payload });
    renderResult(res);
    document.getElementById("loading").style.display = "none";
    document.getElementById("result").style.display = "block";
    toast("Model trained successfully", "success");
  } catch (err) {
    document.getElementById("loading").style.display = "none";
    document.getElementById("empty").style.display = "block";
    toast(err.message, "error");
  }
});

function renderResult(r) {
  const isClassif = r.task_type === "classification";
  const metrics = r.metrics || {};

  const metricCards = isClassif ? `
    <div class="metric-card"><p class="metric-label">Accuracy</p><p class="metric-value">${(metrics.accuracy * 100).toFixed(2)}%</p></div>
    <div class="metric-card"><p class="metric-label">Precision</p><p class="metric-value">${(metrics.precision * 100).toFixed(2)}%</p></div>
    <div class="metric-card"><p class="metric-label">Recall</p><p class="metric-value">${(metrics.recall * 100).toFixed(2)}%</p></div>
    <div class="metric-card"><p class="metric-label">F1 Score</p><p class="metric-value">${(metrics.f1 * 100).toFixed(2)}%</p></div>
  ` : `
    <div class="metric-card"><p class="metric-label">R²</p><p class="metric-value">${metrics.r2?.toFixed(4) ?? '—'}</p></div>
    <div class="metric-card"><p class="metric-label">MAE</p><p class="metric-value">${metrics.mae?.toFixed(2) ?? '—'}</p></div>
    <div class="metric-card"><p class="metric-label">RMSE</p><p class="metric-value">${metrics.rmse?.toFixed(2) ?? '—'}</p></div>
    <div class="metric-card"><p class="metric-label">MAPE</p><p class="metric-value">${metrics.mape ? metrics.mape.toFixed(2) + '%' : '—'}</p></div>
  `;

  document.getElementById("result").innerHTML = `
    <div class="card p-6 mb-6">
      <div class="flex justify-between items-start mb-4 flex-wrap gap-2">
        <div>
          <h2 class="font-semibold text-stone-900 text-lg">${esc(r.name)}</h2>
          <p class="text-xs text-stone-500 mt-1">
            <span class="badge badge-emerald">${esc(r.task_type)}</span>
            <span class="badge badge-stone" style="margin-left:6px">${esc(r.algorithm)}</span>
          </p>
        </div>
        <div class="text-xs text-stone-500 text-right">
          <p>n_train: ${r.n_train}</p>
          <p>n_test: ${r.n_test}</p>
          <p>features: ${r.n_features}</p>
        </div>
      </div>

      <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Metrics</h3>
      <div class="grid grid-cols-4 gap-3 mb-6">${metricCards}</div>

      ${r.feature_importance?.length ? `
        <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Feature Importance (Top 15)</h3>
        <div class="mb-6" style="height:${Math.min(400, r.feature_importance.length * 28 + 40)}px">
          <canvas id="featImportanceChart"></canvas>
        </div>
      ` : ''}

      ${r.confusion_matrix ? `
        <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Confusion Matrix</h3>
        <div class="overflow-auto mb-6" style="border:1px solid #e7e5e4;border-radius:6px">
          <table class="data-table">
            <thead><tr><th>Actual ↓ / Predicted →</th>${r.confusion_matrix[0].map((_, j) => `<th style="text-align:right">Class ${j}</th>`).join("")}</tr></thead>
            <tbody>
              ${r.confusion_matrix.map((row, i) => `
                <tr>
                  <td><strong>Class ${i}</strong></td>
                  ${row.map((v, j) => `<td style="text-align:right;${i === j ? 'background:#ecfdf5;font-weight:600;color:#047857' : ''}">${v}</td>`).join("")}
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      ` : ''}
    </div>
  `;

  // Render feature importance chart
  setTimeout(() => {
    const canvas = document.getElementById("featImportanceChart");
    if (canvas && r.feature_importance?.length) {
      const top = r.feature_importance.slice(0, 15);
      new Chart(canvas.getContext("2d"), {
        type: "bar",
        data: {
          labels: top.map(f => f.feature),
          datasets: [{
            label: "Importance",
            data: top.map(f => f.importance),
            backgroundColor: "#047857",
            borderRadius: 4,
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false, indexAxis: "y",
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { color: "#e7e5e4" }, beginAtZero: true },
            y: { grid: { display: false } },
          },
        },
      });
    }
  }, 100);
}

// ============ MODELS TAB ============
async function renderModels() {
  const box = document.getElementById("tabContent");
  box.innerHTML = '<div class="card p-8 text-center"><span class="spinner"></span> Loading...</div>';
  try {
    const models = await apiFetch("/api/ml/models");
    if (!models.length) {
      box.innerHTML = `
        <div class="card p-10 text-center">
          <p class="text-4xl mb-3">📦</p>
          <p class="font-medium text-stone-700">No models yet</p>
          <p class="text-sm text-stone-500 mt-1">Train your first model from the Train tab.</p>
        </div>`;
      return;
    }
    box.innerHTML = `
      <div class="space-y-3">
        ${models.map(m => {
          const metrics = JSON.parse(m.metrics_json || "{}");
          const metricStr = m.task_type === "classification"
            ? `Accuracy ${((metrics.accuracy || 0) * 100).toFixed(2)}%`
            : `R² ${(metrics.r2 || 0).toFixed(4)}`;
          return `
            <div class="card p-4 flex justify-between items-center flex-wrap gap-3">
              <div class="flex-1 min-w-0">
                <p class="font-medium text-stone-900">${esc(m.name)}</p>
                <p class="text-xs text-stone-500 mt-1">
                  <span class="badge badge-emerald">${esc(m.task_type)}</span>
                  <span class="badge badge-stone" style="margin-left:6px">${esc(m.algorithm)}</span>
                  <span style="margin-left:8px">${esc(m.target_column)}</span>
                </p>
                <p class="text-xs text-stone-500 mt-1">${new Date(m.created_at).toLocaleString()} · ${m.training_samples} training samples</p>
              </div>
              <div class="flex gap-3 items-center shrink-0">
                <span class="text-sm font-medium text-stone-700">${metricStr}</span>
                <button class="delete-model btn-ghost" data-id="${m.id}" style="color:#b91c1c">🗑</button>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    `;
    box.querySelectorAll(".delete-model").forEach(btn => {
      btn.addEventListener("click", async () => {
        if (!confirm("Delete this model?")) return;
        try {
          await apiFetch(`/api/ml/models/${btn.dataset.id}`, { method: "DELETE" });
          toast("Model deleted", "success");
          renderModels();
        } catch (e) { toast(e.message, "error"); }
      });
    });
  } catch (e) {
    box.innerHTML = '<p class="text-sm text-red-600">' + esc(e.message) + '</p>';
  }
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

renderTab();
document.addEventListener("neda:dataset-uploaded", () => { if (activeTab === "train") renderTrain(); });
