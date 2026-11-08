"""Feature engineering engine."""
import numpy as np
import pandas as pd


def _sf(v, d=6):
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, d)
    except (TypeError, ValueError):
        return None


# ============================================================
# Lag Features
# ============================================================
def make_lag_features(df, columns, lags, drop_na=True):
    """Create lag features: {col}_lag{k}."""
    result = df.copy()
    new_cols = []
    for col in columns:
        if col not in df.columns:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        for k in lags:
            new_name = f"{col}_lag{k}"
            result[new_name] = df[col].shift(k)
            new_cols.append(new_name)

    if drop_na and new_cols:
        result = result.dropna(subset=new_cols).reset_index(drop=True)

    return result, {
        "created_columns": new_cols,
        "n_new": len(new_cols),
        "method": "lag",
        "lags": list(lags),
    }


# ============================================================
# Rolling Statistics
# ============================================================
def make_rolling_features(df, columns, windows, stats=None, drop_na=True):
    """Create rolling statistics: {col}_rolling_{stat}_{w}."""
    if stats is None:
        stats = ["mean", "std", "min", "max"]

    result = df.copy()
    new_cols = []
    for col in columns:
        if col not in df.columns:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        s = df[col]
        for w in windows:
            r = s.rolling(window=w)
            for st in stats:
                if hasattr(r, st):
                    method = getattr(r, st)
                    new_name = f"{col}_rolling_{st}_{w}"
                    result[new_name] = method()
                    new_cols.append(new_name)

    if drop_na and new_cols:
        result = result.dropna(subset=new_cols).reset_index(drop=True)

    return result, {
        "created_columns": new_cols,
        "n_new": len(new_cols),
        "method": "rolling",
        "windows": list(windows),
        "stats": stats,
    }


# ============================================================
# Diff Features
# ============================================================
def make_diff_features(df, columns, order=1, include_pct_change=True, drop_na=True):
    """Create diff and pct_change features."""
    result = df.copy()
    new_cols = []
    for col in columns:
        if col not in df.columns:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        diff_name = f"{col}_diff{order}"
        result[diff_name] = df[col].diff(order)
        new_cols.append(diff_name)

        if include_pct_change:
            pct_name = f"{col}_pct_change"
            result[pct_name] = df[col].pct_change().replace([np.inf, -np.inf], np.nan)
            new_cols.append(pct_name)

    if drop_na and new_cols:
        result = result.dropna(subset=new_cols).reset_index(drop=True)

    return result, {
        "created_columns": new_cols,
        "n_new": len(new_cols),
        "method": "diff",
        "order": order,
    }


# ============================================================
# Interaction Terms
# ============================================================
def make_interaction_features(df, pairs, operations=None, drop_na=False):
    """Create interaction features between column pairs.

    pairs: list of [col_a, col_b]
    operations: list of 'multiply', 'divide', 'add', 'subtract'
    """
    if operations is None:
        operations = ["multiply"]

    result = df.copy()
    new_cols = []
    for pair in pairs:
        if len(pair) != 2:
            continue
        a, b = pair
        if a not in df.columns or b not in df.columns:
            continue
        if not (pd.api.types.is_numeric_dtype(df[a]) and pd.api.types.is_numeric_dtype(df[b])):
            continue

        for op in operations:
            if op == "multiply":
                name = f"{a}_x_{b}"
                result[name] = df[a] * df[b]
            elif op == "divide":
                name = f"{a}_div_{b}"
                result[name] = df[a] / df[b].replace(0, np.nan)
            elif op == "add":
                name = f"{a}_plus_{b}"
                result[name] = df[a] + df[b]
            elif op == "subtract":
                name = f"{a}_minus_{b}"
                result[name] = df[a] - df[b]
            else:
                continue
            result[name] = result[name].replace([np.inf, -np.inf], np.nan)
            new_cols.append(name)

    return result, {
        "created_columns": new_cols,
        "n_new": len(new_cols),
        "method": "interaction",
        "pairs": pairs,
        "operations": operations,
    }


# ============================================================
# Polynomial Features
# ============================================================
def make_polynomial_features(df, columns, degrees=None):
    """Create polynomial features: {col}^2, {col}^3."""
    if degrees is None:
        degrees = [2]

    result = df.copy()
    new_cols = []
    for col in columns:
        if col not in df.columns:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        for d in degrees:
            if d < 2:
                continue
            name = f"{col}_pow{d}"
            result[name] = df[col] ** d
            new_cols.append(name)

    return result, {
        "created_columns": new_cols,
        "n_new": len(new_cols),
        "method": "polynomial",
        "degrees": list(degrees),
    }


# ============================================================
# Date Features
# ============================================================
def make_date_features(df, date_columns, features=None):
    """Extract date components."""
    if features is None:
        features = ["year", "month", "day", "weekday", "quarter", "dayofyear"]

    result = df.copy()
    new_cols = []
    for col in date_columns:
        if col not in df.columns:
            continue
        try:
            dt = pd.to_datetime(df[col], errors="coerce")
            if dt.notna().sum() == 0:
                continue

            for f in features:
                new_name = f"{col}_{f}"
                if f == "year":
                    result[new_name] = dt.dt.year
                elif f == "month":
                    result[new_name] = dt.dt.month
                elif f == "day":
                    result[new_name] = dt.dt.day
                elif f == "weekday":
                    result[new_name] = dt.dt.weekday
                elif f == "quarter":
                    result[new_name] = dt.dt.quarter
                elif f == "dayofyear":
                    result[new_name] = dt.dt.dayofyear
                elif f == "week":
                    result[new_name] = dt.dt.isocalendar().week
                elif f == "hour":
                    result[new_name] = dt.dt.hour
                elif f == "minute":
                    result[new_name] = dt.dt.minute
                else:
                    continue
                new_cols.append(new_name)
        except Exception:
            continue

    return result, {
        "created_columns": new_cols,
        "n_new": len(new_cols),
        "method": "date",
        "features": features,
    }


# ============================================================
# Binning
# ============================================================
def make_binning_features(df, columns, n_bins=5, strategy="equal_width"):
    """Binning: equal-width or equal-frequency."""
    result = df.copy()
    new_cols = []
    for col in columns:
        if col not in df.columns:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue

        name = f"{col}_bin_{n_bins}"
        try:
            if strategy == "equal_width":
                binned = pd.cut(df[col], bins=n_bins, labels=False)
            else:  # equal_frequency
                binned = pd.qcut(df[col], q=n_bins, labels=False, duplicates="drop")
            result[name] = binned
            new_cols.append(name)
        except Exception:
            continue

    return result, {
        "created_columns": new_cols,
        "n_new": len(new_cols),
        "method": "binning",
        "n_bins": n_bins,
        "strategy": strategy,
    }


# ============================================================
# One-Hot Encoding
# ============================================================
def make_onehot_features(df, columns, max_categories=20, drop_first=False):
    """One-hot encode categorical columns."""
    result = df.copy()
    new_cols = []
    for col in columns:
        if col not in df.columns:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            continue

        n_unique = df[col].nunique()
        if n_unique > max_categories:
            continue

        try:
            dummies = pd.get_dummies(df[col], prefix=col, drop_first=drop_first, dtype=int)
            for c in dummies.columns:
                result[c] = dummies[c]
                new_cols.append(str(c))
        except Exception:
            continue

    return result, {
        "created_columns": new_cols,
        "n_new": len(new_cols),
        "method": "onehot",
        "max_categories": max_categories,
    }


# ============================================================
# Master: Apply multiple operations at once
# ============================================================
def apply_engineering(df, config: dict):
    """Apply a chain of engineering operations."""
    result = df.copy()
    all_reports = []
    total_new = 0

    if config.get("lag", {}).get("enabled"):
        cols = config["lag"].get("columns", [])
        lags = config["lag"].get("lags", [1])
        result, rpt = make_lag_features(result, cols, lags)
        all_reports.append(rpt)
        total_new += rpt["n_new"]

    if config.get("rolling", {}).get("enabled"):
        cols = config["rolling"].get("columns", [])
        windows = config["rolling"].get("windows", [3])
        stats = config["rolling"].get("stats", ["mean"])
        result, rpt = make_rolling_features(result, cols, windows, stats)
        all_reports.append(rpt)
        total_new += rpt["n_new"]

    if config.get("diff", {}).get("enabled"):
        cols = config["diff"].get("columns", [])
        order = config["diff"].get("order", 1)
        result, rpt = make_diff_features(result, cols, order)
        all_reports.append(rpt)
        total_new += rpt["n_new"]

    if config.get("interaction", {}).get("enabled"):
        pairs = config["interaction"].get("pairs", [])
        ops = config["interaction"].get("operations", ["multiply"])
        result, rpt = make_interaction_features(result, pairs, ops)
        all_reports.append(rpt)
        total_new += rpt["n_new"]

    if config.get("polynomial", {}).get("enabled"):
        cols = config["polynomial"].get("columns", [])
        degrees = config["polynomial"].get("degrees", [2])
        result, rpt = make_polynomial_features(result, cols, degrees)
        all_reports.append(rpt)
        total_new += rpt["n_new"]

    if config.get("date", {}).get("enabled"):
        cols = config["date"].get("columns", [])
        feats = config["date"].get("features", ["year", "month", "day"])
        result, rpt = make_date_features(result, cols, feats)
        all_reports.append(rpt)
        total_new += rpt["n_new"]

    if config.get("binning", {}).get("enabled"):
        cols = config["binning"].get("columns", [])
        n_bins = config["binning"].get("n_bins", 5)
        strategy = config["binning"].get("strategy", "equal_width")
        result, rpt = make_binning_features(result, cols, n_bins, strategy)
        all_reports.append(rpt)
        total_new += rpt["n_new"]

    if config.get("onehot", {}).get("enabled"):
        cols = config["onehot"].get("columns", [])
        max_cat = config["onehot"].get("max_categories", 20)
        result, rpt = make_onehot_features(result, cols, max_cat)
        all_reports.append(rpt)
        total_new += rpt["n_new"]

    return result, {
        "operations": all_reports,
        "total_new_columns": total_new,
        "original_shape": [int(df.shape[0]), int(df.shape[1])],
        "final_shape": [int(result.shape[0]), int(result.shape[1])],
    }
