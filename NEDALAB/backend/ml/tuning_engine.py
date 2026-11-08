"""Hyperparameter tuning: GridSearch + RandomizedSearch."""
import numpy as np
import json
import time
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, StratifiedKFold, KFold
from ml.trainers import CLASSIFIERS, REGRESSORS


PARAM_GRIDS = {
    "classification": {
        "random_forest": {
            "n_estimators": [50, 100, 200],
            "max_depth": [None, 10, 20, 30],
            "min_samples_split": [2, 5, 10],
            "min_samples_leaf": [1, 2, 4],
        },
        "xgboost": {
            "n_estimators": [50, 100, 200],
            "max_depth": [3, 6, 9],
            "learning_rate": [0.01, 0.05, 0.1, 0.2],
            "subsample": [0.8, 0.9, 1.0],
        },
        "lightgbm": {
            "n_estimators": [50, 100, 200],
            "num_leaves": [15, 31, 63],
            "learning_rate": [0.01, 0.05, 0.1],
        },
        "gradient_boosting": {
            "n_estimators": [50, 100, 200],
            "max_depth": [3, 5, 7],
            "learning_rate": [0.01, 0.05, 0.1],
        },
        "logistic_regression": {
            "C": [0.01, 0.1, 1.0, 10.0],
            "solver": ["lbfgs", "liblinear"],
        },
        "decision_tree": {
            "max_depth": [3, 5, 10, 20, None],
            "min_samples_split": [2, 5, 10],
        },
        "knn": {
            "n_neighbors": [3, 5, 7, 11],
            "weights": ["uniform", "distance"],
        },
    },
    "regression": {
        "random_forest": {
            "n_estimators": [50, 100, 200],
            "max_depth": [None, 10, 20, 30],
            "min_samples_split": [2, 5, 10],
        },
        "xgboost": {
            "n_estimators": [50, 100, 200],
            "max_depth": [3, 6, 9],
            "learning_rate": [0.01, 0.05, 0.1, 0.2],
            "subsample": [0.8, 0.9, 1.0],
        },
        "lightgbm": {
            "n_estimators": [50, 100, 200],
            "num_leaves": [15, 31, 63],
            "learning_rate": [0.01, 0.05, 0.1],
        },
        "gradient_boosting": {
            "n_estimators": [50, 100, 200],
            "max_depth": [3, 5, 7],
            "learning_rate": [0.01, 0.05, 0.1],
        },
        "ridge": {
            "alpha": [0.01, 0.1, 1.0, 10.0, 100.0],
        },
        "decision_tree": {
            "max_depth": [3, 5, 10, 20, None],
            "min_samples_split": [2, 5, 10],
        },
        "knn": {
            "n_neighbors": [3, 5, 7, 11],
            "weights": ["uniform", "distance"],
        },
    },
}




# ============================================================
# Fallback for models with no hyperparameters
# ============================================================
PARAM_GRIDS["regression"]["linear_regression"] = {
    "fit_intercept": [True, False],
}
PARAM_GRIDS["classification"]["linear_regression"] = {
    "fit_intercept": [True, False],
}


def _validate_algorithm(task_type, algorithm):
    """Friendly error if algorithm not in param grids."""
    if algorithm not in PARAM_GRIDS.get(task_type, {}):
        # Suggest alternatives based on task
        if task_type == "regression":
            suggestion = (
                f"'{algorithm}' has no tunable hyperparameters. "
                "Try one of: Ridge, Random Forest, Gradient Boosting, XGBoost, or LightGBM"
            )
        else:
            suggestion = (
                f"'{algorithm}' has no tunable hyperparameters. "
                "Try one of: Logistic Regression, Random Forest, Gradient Boosting, XGBoost, or LightGBM"
            )
        raise ValueError(suggestion)


def _get_estimator(task_type, algorithm):
    if task_type == "classification":
        if algorithm not in CLASSIFIERS:
            raise ValueError(f"Unknown classifier: {algorithm}")
        spec = CLASSIFIERS[algorithm]
    else:
        if algorithm not in REGRESSORS:
            raise ValueError(f"Unknown regressor: {algorithm}")
        spec = REGRESSORS[algorithm]
    return spec["class"](**spec["params"])


def tune_model(
    data: dict,
    task_type: str,
    algorithm: str,
    method: str = "grid",
    n_iter: int = 20,
    cv_folds: int = 5,
    n_jobs: int = -1,
) -> dict:
    """Run GridSearchCV or RandomizedSearchCV."""
    X_train = data["X_train"]
    y_train = data["y_train"]

    _validate_algorithm(task_type, algorithm)

    param_grid = PARAM_GRIDS[task_type][algorithm]

    # Compute total combinations for grid
    total_combos = 1
    for v in param_grid.values():
        total_combos *= len(v)

    # Adjust folds if data too small
    n_samples = len(y_train)
    if task_type == "classification":
        min_class = int(np.bincount(y_train.astype(int)).min()) if len(y_train) > 0 else 0
        cv_folds = min(cv_folds, max(2, min_class))
        cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
        scoring = "accuracy"
    else:
        cv_folds = min(cv_folds, max(2, n_samples // 5))
        cv = KFold(n_splits=cv_folds, shuffle=True, random_state=42)
        scoring = "r2"

    estimator = _get_estimator(task_type, algorithm)

    start = time.time()
    try:
        if method == "random" and total_combos > n_iter:
            search = RandomizedSearchCV(
                estimator, param_distributions=param_grid,
                n_iter=min(n_iter, total_combos),
                cv=cv, scoring=scoring, n_jobs=n_jobs, random_state=42, verbose=0,
            )
        else:
            search = GridSearchCV(
                estimator, param_grid=param_grid,
                cv=cv, scoring=scoring, n_jobs=n_jobs, verbose=0,
            )
        search.fit(X_train, y_train)
    except Exception as e:
        raise ValueError(f"Tuning failed: {type(e).__name__}: {e}")

    elapsed = round(time.time() - start, 2)

    # Results (top 10)
    results = []
    cv_results = search.cv_results_
    indices = np.argsort(cv_results["rank_test_score"])[:10]
    for i in indices:
        results.append({
            "rank": int(cv_results["rank_test_score"][i]),
            "mean_score": round(float(cv_results["mean_test_score"][i]), 6),
            "std_score": round(float(cv_results["std_test_score"][i]), 6),
            "params": {k: _py(v) for k, v in cv_results["params"][i].items()},
        })

    return {
        "task_type": task_type,
        "algorithm": algorithm,
        "method": method,
        "cv_folds": cv_folds,
        "scoring": scoring,
        "total_combinations": total_combos,
        "tested": len(cv_results["params"]),
        "elapsed_seconds": elapsed,
        "best_score": round(float(search.best_score_), 6),
        "best_params": {k: _py(v) for k, v in search.best_params_.items()},
        "top_results": results,
    }


def _py(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return round(float(v), 6)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if v is None:
        return None
    return v
