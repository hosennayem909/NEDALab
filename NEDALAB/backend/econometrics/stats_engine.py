"""Statistical tests: correlation, VIF, Granger causality, descriptives."""
import numpy as np
import pandas as pd
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tsa.stattools import grangercausalitytests
from scipy import stats


def _py(v):
    if v is None:
        return None
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return f
    if isinstance(v, np.ndarray):
        return [_py(x) for x in v.tolist()]
    if isinstance(v, list):
        return [_py(x) for x in v]
    if isinstance(v, dict):
        return {k: _py(val) for k, val in v.items()}
    if isinstance(v, float):
        if np.isnan(v) or np.isinf(v):
            return None
    return v


def _sf(v, d=4):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return round(f, d)


# ============ Correlation Matrix ============
def correlation_matrix(df: pd.DataFrame, columns: list) -> dict:
    if not columns or len(columns) < 2:
        raise ValueError("Need at least 2 columns")
    for c in columns:
        if c not in df.columns:
            raise ValueError(f"Column '{c}' not found")

    sub = df[columns].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 3:
        raise ValueError("Too few valid rows after removing NaN")

    corr_pearson = sub.corr(method="pearson")
    corr_spearman = sub.corr(method="spearman")

    # High correlation pairs
    high_corr = []
    for i in range(len(columns)):
        for j in range(i + 1, len(columns)):
            r = corr_pearson.iloc[i, j]
            if pd.notna(r) and abs(r) >= 0.7:
                high_corr.append({
                    "var1": columns[i],
                    "var2": columns[j],
                    "pearson": _sf(r, 4),
                    "spearman": _sf(corr_spearman.iloc[i, j], 4),
                    "strength": "strong" if abs(r) >= 0.9 else "moderate",
                })

    return {
        "columns": columns,
        "pearson": {c: {c2: _sf(corr_pearson.loc[c, c2], 4) for c2 in columns} for c in columns},
        "spearman": {c: {c2: _sf(corr_spearman.loc[c, c2], 4) for c2 in columns} for c in columns},
        "high_correlations": high_corr,
        "n_obs": int(len(sub)),
    }


# ============ VIF ============
def vif_test(df: pd.DataFrame, columns: list) -> dict:
    if not columns or len(columns) < 2:
        raise ValueError("VIF needs at least 2 columns")
    for c in columns:
        if c not in df.columns:
            raise ValueError(f"Column '{c}' not found")

    sub = df[columns].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < len(columns) + 2:
        raise ValueError("Too few valid rows")

    X = sub.to_numpy(dtype=float)
    vifs = []
    for i, col in enumerate(columns):
        try:
            v = float(variance_inflation_factor(X, i))
        except Exception:
            v = None
        if v is None or np.isnan(v) or np.isinf(v):
            interpretation = "cannot compute"
        elif v < 5:
            interpretation = "OK"
        elif v < 10:
            interpretation = "moderate"
        else:
            interpretation = "high (multicollinearity)"
        vifs.append({
            "variable": col,
            "vif": _sf(v, 4),
            "interpretation": interpretation,
        })

    high_vif = [x for x in vifs if x["vif"] is not None and x["vif"] >= 10]

    return {
        "variables": vifs,
        "high_vif_count": len(high_vif),
        "high_vif_vars": [x["variable"] for x in high_vif],
        "n_obs": int(len(sub)),
    }


# ============ Granger Causality ============
def granger_causality(df: pd.DataFrame, cause: str, effect: str, max_lag: int = 5) -> dict:
    if cause not in df.columns or effect not in df.columns:
        raise ValueError("Columns not found")

    sub = df[[effect, cause]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < max_lag * 3:
        raise ValueError(f"Need at least {max_lag * 3} rows, got {len(sub)}")

    data = sub[[effect, cause]].to_numpy(dtype=float)

    try:
        results = grangercausalitytests(data, maxlag=max_lag, verbose=False)
    except Exception as e:
        raise ValueError(f"Granger test failed: {e}")

    lag_results = []
    for lag in range(1, max_lag + 1):
        r = results[lag][0]
        # F-test
        f_stat = _sf(r["ssr_ftest"][0], 4)
        f_p = _sf(r["ssr_ftest"][1], 6)
        # Chi-square
        chi2 = _sf(r["ssr_chi2test"][0], 4)
        chi2_p = _sf(r["ssr_chi2test"][1], 6)

        lag_results.append({
            "lag": lag,
            "f_stat": f_stat,
            "f_pvalue": f_p,
            "chi2_stat": chi2,
            "chi2_pvalue": chi2_p,
            "is_significant": (f_p is not None and f_p < 0.05),
        })

    # Overall: significant if ANY lag is significant
    significant_lags = [r["lag"] for r in lag_results if r["is_significant"]]
    has_causality = len(significant_lags) > 0

    if has_causality:
        interpretation = (
            f"'{cause}' Granger-causes '{effect}' "
            f"(significant at lag(s): {', '.join(map(str, significant_lags))})"
        )
    else:
        interpretation = f"No Granger causality from '{cause}' to '{effect}' at tested lags"

    return {
        "cause": cause,
        "effect": effect,
        "max_lag": max_lag,
        "results": lag_results,
        "has_causality": has_causality,
        "significant_lags": significant_lags,
        "interpretation": interpretation,
        "n_obs": int(len(sub)),
    }


# ============ Descriptive Statistics ============
def descriptive_stats(df: pd.DataFrame, columns: list) -> dict:
    if not columns:
        raise ValueError("Select at least one column")
    for c in columns:
        if c not in df.columns:
            raise ValueError(f"Column '{c}' not found")

    rows = []
    for c in columns:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if len(s) < 2:
            rows.append({"variable": c, "n": int(len(s)), "error": "too few values"})
            continue
        arr = s.to_numpy(dtype=float)
        rows.append({
            "variable": c,
            "n": int(len(s)),
            "mean": _sf(np.mean(arr), 4),
            "median": _sf(np.median(arr), 4),
            "std": _sf(np.std(arr, ddof=1), 4),
            "min": _sf(np.min(arr), 4),
            "max": _sf(np.max(arr), 4),
            "q1": _sf(np.percentile(arr, 25), 4),
            "q3": _sf(np.percentile(arr, 75), 4),
            "skewness": _sf(stats.skew(arr, bias=False), 4) if len(arr) > 2 else None,
            "kurtosis": _sf(stats.kurtosis(arr, bias=False, fisher=True), 4) if len(arr) > 3 else None,
        })
    return {"variables": rows, "n_columns": len(columns)}
