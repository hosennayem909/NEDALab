"""Base ML trainers using scikit-learn."""
import numpy as np
from sklearn.linear_model import LogisticRegression, LinearRegression, Ridge
from sklearn.ensemble import (
    RandomForestClassifier, RandomForestRegressor,
    GradientBoostingClassifier, GradientBoostingRegressor,
)
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report,
    r2_score, mean_absolute_error, mean_squared_error,
)


CLASSIFIERS = {
    "logistic_regression": {
        "label": "Logistic Regression",
        "class": LogisticRegression,
        "params": {"max_iter": 1000, "random_state": 42},
    },
    "random_forest": {
        "label": "Random Forest Classifier",
        "class": RandomForestClassifier,
        "params": {"n_estimators": 100, "random_state": 42, "n_jobs": -1},
    },
    "gradient_boosting": {
        "label": "Gradient Boosting Classifier",
        "class": GradientBoostingClassifier,
        "params": {"n_estimators": 100, "random_state": 42},
    },
    "decision_tree": {
        "label": "Decision Tree Classifier",
        "class": DecisionTreeClassifier,
        "params": {"random_state": 42},
    },
    "knn": {
        "label": "K-Nearest Neighbors Classifier",
        "class": KNeighborsClassifier,
        "params": {"n_neighbors": 5},
    },
}

REGRESSORS = {
    "linear_regression": {
        "label": "Linear Regression",
        "class": LinearRegression,
        "params": {},
    },
    "ridge": {
        "label": "Ridge Regression",
        "class": Ridge,
        "params": {"alpha": 1.0},
    },
    "random_forest": {
        "label": "Random Forest Regressor",
        "class": RandomForestRegressor,
        "params": {"n_estimators": 100, "random_state": 42, "n_jobs": -1},
    },
    "gradient_boosting": {
        "label": "Gradient Boosting Regressor",
        "class": GradientBoostingRegressor,
        "params": {"n_estimators": 100, "random_state": 42},
    },
    "decision_tree": {
        "label": "Decision Tree Regressor",
        "class": DecisionTreeRegressor,
        "params": {"random_state": 42},
    },
    "knn": {
        "label": "K-Nearest Neighbors Regressor",
        "class": KNeighborsRegressor,
        "params": {"n_neighbors": 5},
    },
}


def list_algorithms():
    return {
        "classification": [
            {"value": k, "label": v["label"]} for k, v in CLASSIFIERS.items()
        ],
        "regression": [
            {"value": k, "label": v["label"]} for k, v in REGRESSORS.items()
        ],
    }


def _to_py(v):
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, 6)
    if isinstance(v, np.ndarray):
        return [_to_py(x) for x in v.tolist()]
    if isinstance(v, dict):
        return {k: _to_py(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_to_py(x) for x in v]
    if isinstance(v, float):
        if np.isnan(v) or np.isinf(v):
            return None
        return round(v, 6)
    return v


def _classif_metrics(y_true, y_pred, y_proba=None):
    avg = "binary" if len(np.unique(y_true)) == 2 else "weighted"
    m = {
        "accuracy": _to_py(accuracy_score(y_true, y_pred)),
        "precision": _to_py(precision_score(y_true, y_pred, average=avg, zero_division=0)),
        "recall": _to_py(recall_score(y_true, y_pred, average=avg, zero_division=0)),
        "f1": _to_py(f1_score(y_true, y_pred, average=avg, zero_division=0)),
    }
    return m


def _regress_metrics(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    mse = mean_squared_error(y_true, y_pred)
    rmse = float(np.sqrt(mse))
    r2 = r2_score(y_true, y_pred)
    # MAPE (avoid div by zero)
    mask = y_true != 0
    if mask.any():
        mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)
    else:
        mape = None
    return {
        "r2": _to_py(r2),
        "mae": _to_py(mae),
        "mse": _to_py(mse),
        "rmse": _to_py(rmse),
        "mape": _to_py(mape),
    }


def train_model(data: dict, task_type: str, algorithm: str):
    """Train the selected model. Returns (fitted_model, metrics, extras)."""
    X_train = data["X_train"]
    X_test = data["X_test"]
    y_train = data["y_train"]
    y_test = data["y_test"]

    if task_type == "classification":
        if algorithm not in CLASSIFIERS:
            raise ValueError(f"Unknown classifier: {algorithm}")
        spec = CLASSIFIERS[algorithm]
    else:
        if algorithm not in REGRESSORS:
            raise ValueError(f"Unknown regressor: {algorithm}")
        spec = REGRESSORS[algorithm]

    model = spec["class"](**spec["params"])

    try:
        model.fit(X_train, y_train)
    except Exception as e:
        raise ValueError(f"Training failed: {type(e).__name__}: {e}")

    y_pred = model.predict(X_test)

    extras = {}
    if task_type == "classification":
        metrics = _classif_metrics(y_test, y_pred)
        cm = confusion_matrix(y_test, y_pred)
        extras["confusion_matrix"] = _to_py(cm)
        try:
            cr = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
            extras["classification_report"] = _to_py(cr)
        except Exception:
            extras["classification_report"] = None
    else:
        metrics = _regress_metrics(y_test, y_pred)
        extras["confusion_matrix"] = None
        extras["classification_report"] = None

    # Feature importance
    feature_importance = []
    feature_names = data.get("feature_names", [])
    try:
        if hasattr(model, "feature_importances_"):
            imps = model.feature_importances_
        elif hasattr(model, "coef_"):
            coef = model.coef_
            if coef.ndim == 1:
                imps = np.abs(coef)
            else:
                imps = np.abs(coef).mean(axis=0)
        else:
            imps = None

        if imps is not None and len(feature_names) == len(imps):
            paired = list(zip(feature_names, imps.tolist()))
            paired.sort(key=lambda x: abs(x[1]), reverse=True)
            total = sum(abs(x[1]) for x in paired) or 1.0
            feature_importance = [
                {"feature": str(name), "importance": _to_py(abs(val)), "pct": _to_py(abs(val) / total * 100)}
                for name, val in paired[:30]
            ]
    except Exception:
        feature_importance = []

    return model, metrics, feature_importance, extras


# ============================================================
# Advanced Algorithms: XGBoost + LightGBM
# ============================================================
try:
    from xgboost import XGBClassifier, XGBRegressor
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    from lightgbm import LGBMClassifier, LGBMRegressor
    LGBM_AVAILABLE = True
except ImportError:
    LGBM_AVAILABLE = False


if XGB_AVAILABLE:
    CLASSIFIERS["xgboost"] = {
        "label": "XGBoost Classifier",
        "class": XGBClassifier,
        "params": {
            "n_estimators": 100,
            "max_depth": 6,
            "learning_rate": 0.1,
            "random_state": 42,
            "n_jobs": -1,
            "verbosity": 0,
            "use_label_encoder": False,
        },
    }
    REGRESSORS["xgboost"] = {
        "label": "XGBoost Regressor",
        "class": XGBRegressor,
        "params": {
            "n_estimators": 100,
            "max_depth": 6,
            "learning_rate": 0.1,
            "random_state": 42,
            "n_jobs": -1,
            "verbosity": 0,
        },
    }

if LGBM_AVAILABLE:
    CLASSIFIERS["lightgbm"] = {
        "label": "LightGBM Classifier",
        "class": LGBMClassifier,
        "params": {
            "n_estimators": 100,
            "max_depth": -1,
            "learning_rate": 0.1,
            "random_state": 42,
            "n_jobs": -1,
            "verbose": -1,
        },
    }
    REGRESSORS["lightgbm"] = {
        "label": "LightGBM Regressor",
        "class": LGBMRegressor,
        "params": {
            "n_estimators": 100,
            "max_depth": -1,
            "learning_rate": 0.1,
            "random_state": 42,
            "n_jobs": -1,
            "verbose": -1,
        },
    }
