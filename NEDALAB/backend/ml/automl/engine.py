"""AutoML engine: train multiple models, rank by metric."""
import time
import numpy as np
from ml.preprocessing import prepare_data
from ml.trainers import CLASSIFIERS, REGRESSORS, train_model


# CPU-friendly: 10 algorithms (order doesn't matter)
AUTOML_CANDIDATES_CLASSIFICATION = [
    "logistic_regression",
    "decision_tree",
    "random_forest",
    "gradient_boosting",
    "knn",
    "xgboost",
    "lightgbm",
]

AUTOML_CANDIDATES_REGRESSION = [
    "linear_regression",
    "ridge",
    "decision_tree",
    "random_forest",
    "gradient_boosting",
    "knn",
    "xgboost",
    "lightgbm",
]


def _get_score(metrics: dict, task_type: str) -> float:
    """Higher is better."""
    if task_type == "classification":
        return float(metrics.get("accuracy", 0) or 0)
    else:
        return float(metrics.get("r2", -1e9) or -1e9)


def run_automl(
    df,
    target_column: str,
    feature_columns: list,
    task_type: str = "auto",
    test_size: float = 0.2,
    random_state: int = 42,
    max_models: int = 10,
):
    """Run AutoML on given data. Returns leaderboard + best model info."""
    # Prepare data once
    data = prepare_data(
        df, target_column, feature_columns,
        task_type=task_type, test_size=test_size, random_state=random_state,
    )
    actual_task = data["task_type"]

    candidates = (
        AUTOML_CANDIDATES_CLASSIFICATION if actual_task == "classification"
        else AUTOML_CANDIDATES_REGRESSION
    )[:max_models]

    # Filter to available algorithms
    available = CLASSIFIERS if actual_task == "classification" else REGRESSORS
    candidates = [c for c in candidates if c in available]

    leaderboard = []
    started = time.time()

    for alg in candidates:
        alg_label = available[alg]["label"]
        t0 = time.time()
        try:
            model, metrics, feature_importance, extras = train_model(data, actual_task, alg)
            score = _get_score(metrics, actual_task)
            elapsed = round(time.time() - t0, 2)

            leaderboard.append({
                "algorithm": alg,
                "algorithm_label": alg_label,
                "score": score,
                "metrics": metrics,
                "elapsed_seconds": elapsed,
                "status": "success",
                "feature_importance": feature_importance[:20],
                "confusion_matrix": extras.get("confusion_matrix"),
            })
        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            leaderboard.append({
                "algorithm": alg,
                "algorithm_label": alg_label,
                "score": None,
                "metrics": None,
                "elapsed_seconds": elapsed,
                "status": "failed",
                "error": f"{type(e).__name__}: {str(e)}",
            })

    # Sort by score descending
    successful = [r for r in leaderboard if r["score"] is not None]
    successful.sort(key=lambda x: -x["score"])
    failed = [r for r in leaderboard if r["score"] is None]

    # Rank successful entries
    for i, r in enumerate(successful):
        r["rank"] = i + 1

    total_elapsed = int(time.time() - started)

    best = successful[0] if successful else None

    return {
        "task_type": actual_task,
        "leaderboard": successful + failed,
        "best_algorithm": best["algorithm"] if best else None,
        "best_score": best["score"] if best else None,
        "best_metrics": best["metrics"] if best else None,
        "total_models_tested": len(candidates),
        "total_successful": len(successful),
        "total_failed": len(failed),
        "elapsed_seconds": total_elapsed,
        "data": data,
    }
