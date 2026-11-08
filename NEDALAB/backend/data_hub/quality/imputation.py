"""Advanced imputation: KNN, MICE, Linear Interpolation."""
import numpy as np
import pandas as pd
from sklearn.impute import KNNImputer
from sklearn.experimental import enable_iterative_imputer  # noqa
from sklearn.impute import IterativeImputer
from sklearn.preprocessing import OrdinalEncoder


def impute_advanced(df: pd.DataFrame, method: str = "knn", columns: list = None, n_neighbors: int = 5, max_iter: int = 10) -> tuple:
    """Apply advanced imputation to numeric columns."""
    if method not in ("knn", "mice", "interpolate"):
        raise ValueError(f"Unknown method: {method}")

    result = df.copy()

    # Determine columns to impute
    if columns:
        target_cols = [c for c in columns if c in df.columns]
    else:
        target_cols = df.select_dtypes(include="number").columns.tolist()

    if not target_cols:
        raise ValueError("No numeric columns to impute")

    numeric_df = result[target_cols].apply(pd.to_numeric, errors="coerce")
    n_missing_before = int(numeric_df.isna().sum().sum())

    if n_missing_before == 0:
        return result, {
            "method": method,
            "columns": target_cols,
            "missing_before": 0,
            "missing_after": 0,
            "filled": 0,
        }

    try:
        if method == "knn":
            imputer = KNNImputer(n_neighbors=n_neighbors)
            imputed = imputer.fit_transform(numeric_df)
        elif method == "mice":
            imputer = IterativeImputer(max_iter=max_iter, random_state=42)
            imputed = imputer.fit_transform(numeric_df)
        elif method == "interpolate":
            imputed = numeric_df.interpolate(method="linear", limit_direction="both").to_numpy()
        else:
            raise ValueError(f"Unknown: {method}")

        imputed_df = pd.DataFrame(imputed, columns=target_cols, index=result.index)
        for c in target_cols:
            result[c] = imputed_df[c]

    except Exception as e:
        raise ValueError(f"Imputation failed: {type(e).__name__}: {e}")

    n_missing_after = int(result[target_cols].isna().sum().sum())

    return result, {
        "method": method,
        "columns": target_cols,
        "missing_before": n_missing_before,
        "missing_after": n_missing_after,
        "filled": n_missing_before - n_missing_after,
        "n_neighbors": n_neighbors if method == "knn" else None,
        "max_iter": max_iter if method == "mice" else None,
    }
