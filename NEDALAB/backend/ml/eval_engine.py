"""Advanced evaluation: CV, ROC, PR curves, learning curves, diagnostics."""
import numpy as np
import pandas as pd
from sklearn.model_selection import (
    cross_val_score, StratifiedKFold, KFold, learning_curve,
)
from sklearn.metrics import (
    roc_curve, auc, precision_recall_curve, average_precision_score,
)
from ml.preprocessing import prepare_data
from ml.trainers import CLASSIFIERS, REGRESSORS, _to_py


def _get_estimator(task_type: str, algorithm: str):
    if task_type == "classification":
        if algorithm not in CLASSIFIERS:
            raise ValueError(f"Unknown classifier: {algorithm}")
        spec = CLASSIFIERS[algorithm]
    else:
        if algorithm not in REGRESSORS:
            raise ValueError(f"Unknown regressor: {algorithm}")
        spec = REGRESSORS[algorithm]
    return spec["class"](**spec["params"])


def cross_validate(
    df: pd.DataFrame,
    target_column: str,
    feature_columns: list,
    algorithm: str,
    task_type: str = "classification",
    n_folds: int = 5,
) -> dict:
    """K-Fold cross-validation."""
    data = prepare_data(df, target_column, feature_columns, task_type)

    X = np.vstack([data["X_train"], data["X_test"]])
    y = np.concatenate([data["y_train"], data["y_test"]])

    if len(y) < n_folds * 3:
        raise ValueError(f"Need at least {n_folds * 3} rows for {n_folds}-fold CV")

    if task_type == "classification":
        n_classes = len(np.unique(y))
        # Ensure each class has enough samples
        min_class_count = pd.Series(y).value_counts().min()
        actual_folds = min(n_folds, int(min_class_count))
        if actual_folds < 2:
            raise ValueError(f"Not enough samples per class for CV (min={min_class_count})")
        cv = StratifiedKFold(n_splits=actual_folds, shuffle=True, random_state=42)
        scoring = "accuracy"
    else:
        cv = KFold(n_splits=n_folds, shuffle=True, random_state=42)
        scoring = "r2"

    scores = []
    estimator = _get_estimator(task_type, algorithm)

    try:
        for train_idx, test_idx in cv.split(X, y):
            est = _get_estimator(task_type, algorithm)
            est.fit(X[train_idx], y[train_idx])
            preds = est.predict(X[test_idx])
            if task_type == "classification":
                from sklearn.metrics import accuracy_score
                scores.append(accuracy_score(y[test_idx], preds))
            else:
                from sklearn.metrics import r2_score
                scores.append(r2_score(y[test_idx], preds))
    except Exception as e:
        raise ValueError(f"CV failed: {type(e).__name__}: {e}")

    scores = np.array(scores)
    return {
        "task_type": task_type,
        "algorithm": algorithm,
        "n_folds": int(actual_folds if task_type == "classification" else n_folds),
        "scoring": scoring,
        "scores": [_to_py(s) for s in scores.tolist()],
        "mean": _to_py(scores.mean()),
        "std": _to_py(scores.std()),
        "min": _to_py(scores.min()),
        "max": _to_py(scores.max()),
        "n_samples": int(len(y)),
    }


def roc_data(
    df: pd.DataFrame,
    target_column: str,
    feature_columns: list,
    algorithm: str,
    task_type: str = "classification",
) -> dict:
    """ROC curve data for binary classification."""
    data = prepare_data(df, target_column, feature_columns, task_type)
    if data["task_type"] != "classification":
        raise ValueError("ROC curve requires classification task")

    X_train = data["X_train"]; X_test = data["X_test"]
    y_train = data["y_train"]; y_test = data["y_test"]

    n_classes = len(np.unique(y_train))
    if n_classes != 2:
        raise ValueError(f"ROC curve requires exactly 2 classes, got {n_classes}")

    est = _get_estimator("classification", algorithm)
    est.fit(X_train, y_train)

    if hasattr(est, "predict_proba"):
        y_score = est.predict_proba(X_test)[:, 1]
    elif hasattr(est, "decision_function"):
        y_score = est.decision_function(X_test)
    else:
        raise ValueError(f"{algorithm} does not support probability output")

    fpr, tpr, _ = roc_curve(y_test, y_score)
    roc_auc = auc(fpr, tpr)

    # Downsample for cleaner JSON
    step = max(1, len(fpr) // 100)
    fpr_ds = fpr[::step].tolist()
    tpr_ds = tpr[::step].tolist()
    if fpr_ds[-1] != 1.0:
        fpr_ds.append(1.0)
        tpr_ds.append(1.0)

    return {
        "fpr": [_to_py(x) for x in fpr_ds],
        "tpr": [_to_py(x) for x in tpr_ds],
        "auc": _to_py(roc_auc),
        "n_test": int(len(y_test)),
    }


def pr_curve_data(
    df: pd.DataFrame,
    target_column: str,
    feature_columns: list,
    algorithm: str,
    task_type: str = "classification",
) -> dict:
    """Precision-Recall curve data for binary classification."""
    data = prepare_data(df, target_column, feature_columns, task_type)
    if data["task_type"] != "classification":
        raise ValueError("PR curve requires classification task")

    X_train = data["X_train"]; X_test = data["X_test"]
    y_train = data["y_train"]; y_test = data["y_test"]

    n_classes = len(np.unique(y_train))
    if n_classes != 2:
        raise ValueError(f"PR curve requires exactly 2 classes, got {n_classes}")

    est = _get_estimator("classification", algorithm)
    est.fit(X_train, y_train)

    if hasattr(est, "predict_proba"):
        y_score = est.predict_proba(X_test)[:, 1]
    elif hasattr(est, "decision_function"):
        y_score = est.decision_function(X_test)
    else:
        raise ValueError(f"{algorithm} does not support probability output")

    prec, rec, _ = precision_recall_curve(y_test, y_score)
    ap = average_precision_score(y_test, y_score)

    step = max(1, len(prec) // 100)
    prec_ds = prec[::step].tolist()
    rec_ds = rec[::step].tolist()

    return {
        "precision": [_to_py(x) for x in prec_ds],
        "recall": [_to_py(x) for x in rec_ds],
        "avg_precision": _to_py(ap),
        "n_test": int(len(y_test)),
    }


def learning_curve_data(
    df: pd.DataFrame,
    target_column: str,
    feature_columns: list,
    algorithm: str,
    task_type: str = "classification",
    n_folds: int = 5,
) -> dict:
    """Learning curve: train/val score vs training set size."""
    data = prepare_data(df, target_column, feature_columns, task_type)

    X = np.vstack([data["X_train"], data["X_test"]])
    y = np.concatenate([data["y_train"], data["y_test"]])

    if task_type == "classification":
        min_class = pd.Series(y).value_counts().min()
        folds = min(n_folds, int(min_class))
        if folds < 2:
            raise ValueError(f"Not enough per-class samples (min={min_class})")
        cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
        scoring = "accuracy"
    else:
        cv = KFold(n_splits=n_folds, shuffle=True, random_state=42)
        scoring = "r2"
        folds = n_folds

    est = _get_estimator(task_type, algorithm)

    try:
        train_sizes, train_scores, val_scores = learning_curve(
            est, X, y,
            train_sizes=np.linspace(0.1, 1.0, 8),
            cv=cv, scoring=scoring, n_jobs=-1,
        )
    except Exception as e:
        raise ValueError(f"Learning curve failed: {type(e).__name__}: {e}")

    return {
        "task_type": task_type,
        "scoring": scoring,
        "train_sizes": [_to_py(x) for x in train_sizes.tolist()],
        "train_mean": [_to_py(x) for x in train_scores.mean(axis=1).tolist()],
        "train_std": [_to_py(x) for x in train_scores.std(axis=1).tolist()],
        "val_mean": [_to_py(x) for x in val_scores.mean(axis=1).tolist()],
        "val_std": [_to_py(x) for x in val_scores.std(axis=1).tolist()],
    }


def regression_diagnostics(
    df: pd.DataFrame,
    target_column: str,
    feature_columns: list,
    algorithm: str,
) -> dict:
    """Residuals + actual vs predicted for regression."""
    data = prepare_data(df, target_column, feature_columns, "regression")

    X_train = data["X_train"]; X_test = data["X_test"]
    y_train = data["y_train"]; y_test = data["y_test"]

    est = _get_estimator("regression", algorithm)
    est.fit(X_train, y_train)

    y_pred_test = est.predict(X_test)
    y_pred_train = est.predict(X_train)

    residuals_train = y_train - y_pred_train
    residuals_test = y_test - y_pred_test

    # Sample points for scatter (limit to 300)
    n_test = len(y_test)
    idx = np.random.RandomState(42).choice(n_test, size=min(300, n_test), replace=False)

    scatter = [
        {"actual": _to_py(y_test[i]), "predicted": _to_py(y_pred_test[i])}
        for i in idx
    ]

    # Residuals histogram
    resid_hist_vals, bin_edges = np.histogram(residuals_test, bins=30)

    return {
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "scatter": scatter,
        "residual_stats": {
            "mean": _to_py(np.mean(residuals_test)),
            "std": _to_py(np.std(residuals_test)),
            "min": _to_py(np.min(residuals_test)),
            "max": _to_py(np.max(residuals_test)),
        },
        "residual_histogram": {
            "counts": [_to_py(x) for x in resid_hist_vals.tolist()],
            "bin_edges": [_to_py(x) for x in bin_edges.tolist()],
        },
    }
