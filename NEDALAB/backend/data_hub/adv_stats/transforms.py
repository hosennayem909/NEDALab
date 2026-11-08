"""Statistical transformations: Winsorization, Log, Box-Cox, Sqrt."""
import numpy as np
import pandas as pd
from scipy import stats


def _parse_numeric(s: pd.Series) -> np.ndarray:
    return pd.to_numeric(s, errors="coerce")


def winsorize_series(s: pd.Series, lower_pct: float = 1.0, upper_pct: float = 99.0) -> tuple:
    """Cap extreme values at percentiles. Returns (new_series, stats)."""
    parsed = _parse_numeric(s)
    mask = parsed.notna()
    if mask.sum() < 3:
        return s.copy(), {"changed": 0, "lower": None, "upper": None}

    lower_val = float(np.percentile(parsed[mask], lower_pct))
    upper_val = float(np.percentile(parsed[mask], upper_pct))

    new_parsed = parsed.copy()
    clipped_low = (parsed < lower_val).sum()
    clipped_high = (parsed > upper_val).sum()
    new_parsed = new_parsed.clip(lower=lower_val, upper=upper_val)

    new_s = s.copy()
    new_s.loc[mask] = new_parsed[mask]

    return new_s, {
        "changed": int(clipped_low + clipped_high),
        "clipped_low": int(clipped_low),
        "clipped_high": int(clipped_high),
        "lower_bound": round(lower_val, 4),
        "upper_bound": round(upper_val, 4),
        "lower_pct": lower_pct,
        "upper_pct": upper_pct,
    }


def log_transform_series(s: pd.Series, shift: float | None = None) -> tuple:
    """Natural log. Auto-shift if data contains <= 0 values."""
    parsed = _parse_numeric(s)
    mask = parsed.notna()
    if mask.sum() < 1:
        return s.copy(), {"changed": 0, "error": "no values"}

    min_val = float(parsed[mask].min())
    used_shift = shift if shift is not None else (1.0 - min_val if min_val <= 0 else 0.0)

    new_vals = np.log(parsed[mask] + used_shift)
    new_s = s.copy()
    new_s.loc[mask] = new_vals

    return new_s, {
        "changed": int(mask.sum()),
        "shift_applied": round(float(used_shift), 4),
        "min_original": round(min_val, 4),
    }


def sqrt_transform_series(s: pd.Series, shift: float | None = None) -> tuple:
    """Square root. Auto-shift for negative values."""
    parsed = _parse_numeric(s)
    mask = parsed.notna()
    if mask.sum() < 1:
        return s.copy(), {"changed": 0, "error": "no values"}

    min_val = float(parsed[mask].min())
    used_shift = shift if shift is not None else (abs(min_val) if min_val < 0 else 0.0)

    new_vals = np.sqrt(parsed[mask] + used_shift)
    new_s = s.copy()
    new_s.loc[mask] = new_vals

    return new_s, {
        "changed": int(mask.sum()),
        "shift_applied": round(float(used_shift), 4),
    }


def boxcox_transform_series(s: pd.Series) -> tuple:
    """Box-Cox power transform. Requires strictly positive values."""
    parsed = _parse_numeric(s)
    mask = parsed.notna()
    if mask.sum() < 3:
        return s.copy(), {"changed": 0, "error": "too few values"}

    values = parsed[mask].to_numpy(dtype=float)
    min_val = float(np.min(values))
    if min_val <= 0:
        values = values - min_val + 1.0
        shift_used = 1.0 - min_val
    else:
        shift_used = 0.0

    try:
        transformed, lam = stats.boxcox(values)
    except Exception as e:
        return s.copy(), {"changed": 0, "error": str(e)}

    new_s = s.copy()
    new_s.loc[mask] = transformed

    return new_s, {
        "changed": int(mask.sum()),
        "lambda": round(float(lam), 4),
        "shift_applied": round(float(shift_used), 4),
    }


def preview_transform(df: pd.DataFrame, column: str, method: str, params: dict) -> dict:
    """Preview a transform: return before/after stats."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")

    s = df[column]
    original_numeric = _parse_numeric(s).dropna()

    if method == "winsorize":
        new_s, meta = winsorize_series(s, params.get("lower_pct", 1.0), params.get("upper_pct", 99.0))
    elif method == "log":
        new_s, meta = log_transform_series(s)
    elif method == "sqrt":
        new_s, meta = sqrt_transform_series(s)
    elif method == "boxcox":
        new_s, meta = boxcox_transform_series(s)
    else:
        raise ValueError(f"Unknown method: {method}")

    new_numeric = _parse_numeric(new_s).dropna()

    def _stats(arr):
        if len(arr) < 2:
            return None
        return {
            "n": int(len(arr)),
            "mean": round(float(np.mean(arr)), 4),
            "std": round(float(np.std(arr, ddof=1)), 4),
            "min": round(float(np.min(arr)), 4),
            "max": round(float(np.max(arr)), 4),
            "median": round(float(np.median(arr)), 4),
            "skewness": round(float(stats.skew(arr, bias=False)), 4) if len(arr) > 2 else 0.0,
            "kurtosis": round(float(stats.kurtosis(arr, bias=False, fisher=True)), 4) if len(arr) > 3 else 0.0,
        }

    return {
        "column": column,
        "method": method,
        "meta": meta,
        "before": _stats(original_numeric.to_numpy(dtype=float)),
        "after": _stats(new_numeric.to_numpy(dtype=float)),
    }


def apply_transform(df: pd.DataFrame, column: str, method: str, params: dict) -> pd.DataFrame:
    """Apply transform and return new df."""
    df = df.copy()
    s = df[column]
    if method == "winsorize":
        new_s, _ = winsorize_series(s, params.get("lower_pct", 1.0), params.get("upper_pct", 99.0))
    elif method == "log":
        new_s, _ = log_transform_series(s)
    elif method == "sqrt":
        new_s, _ = sqrt_transform_series(s)
    elif method == "boxcox":
        new_s, _ = boxcox_transform_series(s)
    else:
        raise ValueError(f"Unknown method: {method}")
    df[column] = new_s
    return df
