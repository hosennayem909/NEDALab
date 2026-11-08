"""SHAP explainability for trained models."""
import numpy as np
import pandas as pd
import json
from pathlib import Path


def compute_shap(model_path: str, df: pd.DataFrame, max_samples: int = 100) -> dict:
    """Compute SHAP values for a trained model."""
    try:
        import shap
    except ImportError:
        raise ValueError("SHAP not installed. Run: pip install shap")

    from ml.model_registry import load_model_bundle

    bundle = load_model_bundle(model_path)
    model = bundle["model"]
    preprocessor = bundle["preprocessor"]
    feature_names = bundle["feature_names"]
    task_type = bundle["task_type"]

    missing = [f for f in feature_names if f not in df.columns]
    if missing:
        raise ValueError(f"Missing features: {', '.join(missing)}")

    X = df[feature_names]
    # Sample if too large
    if len(X) > max_samples:
        X = X.sample(n=max_samples, random_state=42).reset_index(drop=True)

    try:
        X_t = preprocessor.transform(X)
    except Exception as e:
        raise ValueError(f"Preprocessing failed: {e}")

    # Choose explainer
    try:
        # Try TreeExplainer for tree-based models
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_t)
    except Exception:
        try:
            explainer = shap.LinearExplainer(model, X_t)
            shap_values = explainer.shap_values(X_t)
        except Exception:
            explainer = shap.KernelExplainer(model.predict, X_t[:50])
            shap_values = explainer.shap_values(X_t[:50])

    # Handle multi-output
    if isinstance(shap_values, list):
        shap_values = shap_values[0] if len(shap_values) == 2 else np.mean(shap_values, axis=0)

    shap_arr = np.asarray(shap_values)

    # Handle 3D (samples, features, classes)
    if shap_arr.ndim == 3:
        shap_arr = shap_arr.mean(axis=2)

    # Global importance: mean |SHAP|
    mean_abs = np.abs(shap_arr).mean(axis=0)

    # Align feature count
    n_feat = len(feature_names)
    if len(mean_abs) != n_feat:
        # Reduced/aligned feature names
        if len(mean_abs) > n_feat:
            feature_names = [f"f_{i}" for i in range(len(mean_abs))]
        else:
            mean_abs = mean_abs[:n_feat]

    global_importance = []
    for i, name in enumerate(feature_names[:len(mean_abs)]):
        global_importance.append({
            "feature": str(name),
            "mean_abs_shap": round(float(mean_abs[i]), 6),
        })
    global_importance.sort(key=lambda x: -x["mean_abs_shap"])

    # Local explanation (first sample)
    local = []
    if len(shap_arr) > 0:
        first = shap_arr[0]
        for i, name in enumerate(feature_names[:len(first)]):
            local.append({
                "feature": str(name),
                "shap_value": round(float(first[i]), 6),
                "feature_value": round(float(X_t[0][i]), 4) if i < X_t.shape[1] else None,
            })
        local.sort(key=lambda x: -abs(x["shap_value"]))

    return {
        "task_type": task_type,
        "n_samples_explained": int(len(shap_arr)),
        "n_features": len(feature_names),
        "global_importance": global_importance[:30],
        "local_explanation": local[:20],
    }
