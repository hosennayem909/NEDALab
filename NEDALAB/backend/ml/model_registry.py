"""Model persistence: save/load trained models with joblib."""
import joblib
from pathlib import Path
from datetime import datetime

MODEL_DIR = Path("uploads/ml_models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def save_model_bundle(model, preprocessor, feature_names, task_type,
                      label_encoder, metadata: dict) -> str:
    """Save model + preprocessor + metadata to disk."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"model_{stamp}.joblib"
    path = MODEL_DIR / filename

    bundle = {
        "model": model,
        "preprocessor": preprocessor,
        "feature_names": feature_names,
        "task_type": task_type,
        "label_encoder": label_encoder,
        "metadata": metadata,
        "saved_at": datetime.now().isoformat(),
    }
    joblib.dump(bundle, path, compress=3)
    return str(path)


def load_model_bundle(path: str) -> dict:
    """Load model bundle from disk."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Model file missing: {path}")
    return joblib.load(p)


def delete_model_file(path: str):
    try:
        p = Path(path)
        if p.exists():
            p.unlink()
    except Exception:
        pass
