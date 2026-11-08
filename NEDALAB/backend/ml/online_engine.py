"""Online Learning Engine using River.

Models learn incrementally from streaming data.
No retraining needed — model updates with each new sample.
"""
import uuid
import pickle
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import numpy as np
import pandas as pd

from river import linear_model, tree, forest, preprocessing, metrics, compose


# Session storage (in-memory; replace with Redis for production)
_SESSIONS: Dict[str, Dict[str, Any]] = {}

# Models persist directory
MODEL_DIR = Path(__file__).resolve().parent / "online_models"
MODEL_DIR.mkdir(exist_ok=True)


# ---------- Model Factory ----------
def _build_model(task: str, model_type: str):
    """Build a River model pipeline with scaler + model."""
    scaler = preprocessing.StandardScaler()

    if task == "classification":
        if model_type == "linear":
            base = linear_model.LogisticRegression()
        elif model_type == "tree":
            base = tree.HoeffdingTreeClassifier()
        elif model_type == "forest":
            base = forest.ARFClassifier(n_models=10, seed=42)
        else:
            raise ValueError(f"Unknown model: {model_type}")

        metric = metrics.Accuracy()
        rolling = metrics.Rolling(metrics.Accuracy(), window_size=100)
    else:  # regression
        if model_type == "linear":
            base = linear_model.LinearRegression()
        elif model_type == "tree":
            base = tree.HoeffdingTreeRegressor()
        elif model_type == "forest":
            base = forest.ARFRegressor(n_models=10, seed=42)
        else:
            raise ValueError(f"Unknown model: {model_type}")

        metric = metrics.R2()
        rolling = metrics.Rolling(metrics.R2(), window_size=100)

    pipeline = compose.Pipeline(scaler, base)
    return pipeline, metric, rolling


# ---------- Session Management ----------
def init_session(
    dataset_id: int,
    target: str,
    features: List[str],
    task: str = "regression",
    model: str = "linear",
) -> Dict[str, Any]:
    """Create a new online learning session."""
    session_id = str(uuid.uuid4())[:8]

    pipeline, metric, rolling = _build_model(task, model)

    _SESSIONS[session_id] = {
        "session_id": session_id,
        "dataset_id": dataset_id,
        "target": target,
        "features": features,
        "task": task,
        "model_type": model,
        "model": pipeline,
        "metric": metric,
        "rolling": rolling,
        "n_samples_seen": 0,
        "created_at": datetime.utcnow().isoformat(),
        "history": [],
    }

    return _session_info(session_id)


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    return _SESSIONS.get(session_id)


def list_sessions() -> List[Dict[str, Any]]:
    return [_session_info(sid) for sid in _SESSIONS.keys()]


def delete_session(session_id: str) -> bool:
    if session_id in _SESSIONS:
        del _SESSIONS[session_id]
        return True
    return False


def _session_info(session_id: str) -> Dict[str, Any]:
    s = _SESSIONS[session_id]
    return {
        "session_id": session_id,
        "dataset_id": s["dataset_id"],
        "model_name": s["model_type"],
        "task": s["task"],
        "n_samples_seen": s["n_samples_seen"],
        "metric_name": _metric_name(s["metric"]),
        "metric_value": _metric_value(s["metric"]),
        "rolling_metric": _metric_value(s["rolling"]),
        "features": s["features"],
        "target": s["target"],
    }


def _metric_name(metric) -> str:
    return type(metric).__name__


def _metric_value(metric) -> Optional[float]:
    try:
        if hasattr(metric, "get"):
            v = metric.get()
            if v is None:
                return None
            return round(float(v), 6)
    except Exception:
        pass
    return None


# ---------- Step / Batch Processing ----------
def step(
    session_id: str,
    x: Dict[str, Any],
    y: Optional[float] = None,
    learn: bool = True,
) -> Dict[str, Any]:
    """Feed one sample. Returns prediction + updated metric."""
    s = _SESSIONS.get(session_id)
    if s is None:
        raise ValueError(f"Session {session_id} not found")

    model = s["model"]

    # Clean features
    x_clean = {}
    for f in s["features"]:
        v = x.get(f)
        if v is None:
            return {"error": f"Missing feature: {f}"}
        try:
            x_clean[f] = float(v)
        except (TypeError, ValueError):
            return {"error": f"Non-numeric feature: {f}={v}"}

    # Predict
    try:
        y_pred = model.predict_one(x_clean)
    except Exception:
        y_pred = None

    # Learn
    learned = False
    if y is not None and learn:
        try:
            model.learn_one(x_clean, float(y))
            learned = True
            s["n_samples_seen"] += 1

            try:
                s["metric"].update(float(y), y_pred)
                s["rolling"].update(float(y), y_pred)
            except Exception:
                pass

            s["history"].append({
                "y_true": float(y),
                "y_pred": y_pred,
                "n": s["n_samples_seen"],
            })
            if len(s["history"]) > 500:
                s["history"] = s["history"][-500:]
        except Exception as e:
            return {"error": f"Learn failed: {e}"}

    return {
        "session_id": session_id,
        "prediction": _safe_float(y_pred),
        "learned": learned,
        "n_samples_seen": s["n_samples_seen"],
        "metric_value": _metric_value(s["metric"]),
        "rolling_metric": _metric_value(s["rolling"]),
    }


def batch_step(
    session_id: str,
    samples: List[Dict[str, Any]],
    learn: bool = True,
) -> Dict[str, Any]:
    """Feed multiple samples. Returns summary."""
    results = []
    for sample in samples:
        s = _SESSIONS.get(session_id)
        if s is None:
            raise ValueError(f"Session {session_id} not found")
        target = s["target"]
        sample_copy = dict(sample)
        y = sample_copy.pop(target, None)
        result = step(session_id, sample_copy, y, learn)
        results.append(result)

    s = _SESSIONS[session_id]
    return {
        "session_id": session_id,
        "n_processed": len(samples),
        "n_samples_seen": s["n_samples_seen"],
        "metric_value": _metric_value(s["metric"]),
        "rolling_metric": _metric_value(s["rolling"]),
        "sample_results": results[-10:],
    }


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, 6)
    except (TypeError, ValueError):
        return None


# ---------- Model Persistence ----------
def save_session(session_id: str) -> str:
    s = _SESSIONS.get(session_id)
    if s is None:
        raise ValueError("Session not found")

    path = MODEL_DIR / f"{session_id}.pkl"
    with open(path, "wb") as f:
        pickle.dump({
            "model": s["model"],
            "features": s["features"],
            "target": s["target"],
            "task": s["task"],
            "model_type": s["model_type"],
            "n_samples_seen": s["n_samples_seen"],
        }, f)
    return str(path)