"""Prediction: single + batch."""
import numpy as np
import pandas as pd
from ml.model_registry import load_model_bundle


def _coerce(v):
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        f = float(v)
        return None if (np.isnan(f) or np.isinf(f)) else round(f, 6)
    if isinstance(v, np.ndarray):
        return [_coerce(x) for x in v.tolist()]
    if isinstance(v, list):
        return [_coerce(x) for x in v]
    if isinstance(v, float):
        return None if (np.isnan(v) or np.isinf(v)) else round(v, 6)
    return v


def predict_single(model_path: str, input_data: dict) -> dict:
    bundle = load_model_bundle(model_path)
    model = bundle["model"]
    preprocessor = bundle["preprocessor"]
    feature_names = bundle["feature_names"]
    task_type = bundle["task_type"]
    label_encoder = bundle.get("label_encoder")

    missing = [f for f in feature_names if f not in input_data]
    if missing:
        raise ValueError(f"Missing required features: {', '.join(missing)}")

    row = {f: input_data.get(f) for f in feature_names}
    df = pd.DataFrame([row])

    try:
        X_t = preprocessor.transform(df)
    except Exception as e:
        raise ValueError(f"Preprocessing failed: {e}")

    pred = model.predict(X_t)[0]
    result = {
        "task_type": task_type,
        "raw_prediction": _coerce(pred),
    }

    if task_type == "classification":
        pred_int = int(pred)
        if label_encoder is not None:
            result["label"] = str(label_encoder.inverse_transform([pred_int])[0])
        else:
            result["label"] = str(pred_int)
        if hasattr(model, "predict_proba"):
            try:
                proba = model.predict_proba(X_t)[0]
                result["probabilities"] = [_coerce(p) for p in proba]
            except Exception:
                pass
    else:
        result["prediction"] = _coerce(float(pred))

    return result


def predict_batch(model_path: str, df: pd.DataFrame) -> tuple:
    bundle = load_model_bundle(model_path)
    model = bundle["model"]
    preprocessor = bundle["preprocessor"]
    feature_names = bundle["feature_names"]
    task_type = bundle["task_type"]
    label_encoder = bundle.get("label_encoder")

    missing = [f for f in feature_names if f not in df.columns]
    if missing:
        raise ValueError(f"Missing features: {', '.join(missing)}")

    X = df[feature_names]
    try:
        X_t = preprocessor.transform(X)
    except Exception as e:
        raise ValueError(f"Preprocessing failed: {e}")

    preds = model.predict(X_t)
    out = df.copy()

    if task_type == "regression":
        out["prediction"] = [float(p) for p in preds]
    else:
        out["prediction"] = [int(p) for p in preds]
        if label_encoder is not None:
            out["predicted_label"] = [str(label_encoder.inverse_transform([int(p)])[0]) for p in preds]
        if hasattr(model, "predict_proba"):
            try:
                proba = model.predict_proba(X_t)
                for i in range(proba.shape[1]):
                    out[f"proba_class_{i}"] = [float(v) for v in proba[:, i]]
            except Exception:
                pass

    stats = {
        "n_rows": int(len(df)),
        "n_predicted": int(len(preds)),
        "task_type": task_type,
    }
    if task_type == "regression":
        stats["mean"] = float(np.mean(preds))
        stats["min"] = float(np.min(preds))
        stats["max"] = float(np.max(preds))
    else:
        unique, counts = np.unique(preds, return_counts=True)
        stats["class_distribution"] = [
            {"class": int(u), "count": int(c)} for u, c in zip(unique, counts)
        ]

    return out, stats
