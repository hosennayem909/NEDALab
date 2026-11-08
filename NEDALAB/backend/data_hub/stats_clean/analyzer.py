"""Statistical analysis + outlier detection."""
import pandas as pd
import numpy as np
from scipy import stats


def analyze_distribution(s: pd.Series) -> dict:
    """Compute distribution stats for a numeric column."""
    parsed = pd.to_numeric(s, errors="coerce").dropna()
    n = len(parsed)
    if n < 3:
        return {"n": n, "error": "Too few data points"}

    arr = parsed.to_numpy(dtype=float)
    mean = float(np.mean(arr))
    median = float(np.median(arr))
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0

    skew = float(stats.skew(arr, bias=False)) if n > 2 else 0.0
    kurt = float(stats.kurtosis(arr, bias=False, fisher=True)) if n > 3 else 0.0

    # Coefficient of variation
    cv = (std / mean * 100) if mean != 0 else None

    # Percentiles
    q = np.percentile(arr, [1, 5, 25, 50, 75, 95, 99])

    # Normality test (Shapiro needs n >= 3, prefer <= 5000)
    if 3 <= n <= 5000:
        try:
            shapiro_stat, shapiro_p = stats.shapiro(arr)
            is_normal = shapiro_p > 0.05
        except Exception:
            shapiro_stat, shapiro_p, is_normal = None, None, None
    else:
        shapiro_stat, shapiro_p, is_normal = None, None, None

    return {
        "n": n,
        "mean": round(mean, 4),
        "median": round(median, 4),
        "std": round(std, 4),
        "min": round(float(np.min(arr)), 4),
        "max": round(float(np.max(arr)), 4),
        "q1": round(float(q[2]), 4),
        "q25": round(float(q[3]), 4),
        "q75": round(float(q[4]), 4),
        "q99": round(float(q[6]), 4),
        "skewness": round(skew, 4),
        "kurtosis": round(kurt, 4),
        "cv_pct": round(cv, 2) if cv is not None else None,
        "shapiro_p": round(float(shapiro_p), 4) if shapiro_p is not None else None,
        "is_normal": is_normal,
        "skew_interpretation": _interpret_skew(skew),
    }


def _interpret_skew(s: float) -> str:
    a = abs(s)
    if a < 0.5:
        return "approximately symmetric"
    if a < 1.0:
        return "moderately " + ("right" if s > 0 else "left") + " skewed"
    return "highly " + ("right" if s > 0 else "left") + " skewed"


def detect_outliers_iqr(s: pd.Series) -> dict:
    """IQR method."""
    arr = pd.to_numeric(s, errors="coerce").dropna().to_numpy(dtype=float)
    if len(arr) < 4:
        return {"count": 0, "indices": []}
    q1, q3 = np.percentile(arr, [25, 75])
    iqr = q3 - q1
    if iqr == 0:
        return {"count": 0, "indices": [], "lower": None, "upper": None}
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    mask = (arr < lower) | (arr > upper)
    return {
        "count": int(mask.sum()),
        "lower": round(float(lower), 4),
        "upper": round(float(upper), 4),
        "pct": round(float(mask.sum()) / len(arr) * 100, 2),
    }


def detect_outliers_zscore(s: pd.Series, threshold: float = 3.0) -> dict:
    """Z-score method."""
    arr = pd.to_numeric(s, errors="coerce").dropna().to_numpy(dtype=float)
    if len(arr) < 3:
        return {"count": 0}
    mean = np.mean(arr)
    std = np.std(arr, ddof=1)
    if std == 0:
        return {"count": 0, "threshold": threshold}
    z = np.abs((arr - mean) / std)
    mask = z > threshold
    return {
        "count": int(mask.sum()),
        "threshold": threshold,
        "pct": round(float(mask.sum()) / len(arr) * 100, 2),
    }


def detect_outliers_mad(s: pd.Series, threshold: float = 3.5) -> dict:
    """MAD (Median Absolute Deviation) - robust method."""
    arr = pd.to_numeric(s, errors="coerce").dropna().to_numpy(dtype=float)
    if len(arr) < 3:
        return {"count": 0}
    median = np.median(arr)
    mad = np.median(np.abs(arr - median))
    if mad == 0:
        return {"count": 0, "threshold": threshold}
    # Modified Z-score
    modified_z = 0.6745 * (arr - median) / mad
    mask = np.abs(modified_z) > threshold
    return {
        "count": int(mask.sum()),
        "threshold": threshold,
        "pct": round(float(mask.sum()) / len(arr) * 100, 2),
    }


def analyze_dataframe(df: pd.DataFrame) -> dict:
    """Full statistical analysis."""
    columns = []
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        dist = analyze_distribution(df[col])
        if "error" in dist:
            continue
        iqr = detect_outliers_iqr(df[col])
        zscore = detect_outliers_zscore(df[col])
        mad = detect_outliers_mad(df[col])
        columns.append({
            "name": str(col),
            "distribution": dist,
            "outliers_iqr": iqr,
            "outliers_zscore": zscore,
            "outliers_mad": mad,
        })
    return {
        "total_rows": int(len(df)),
        "numeric_columns": len(columns),
        "columns": columns,
    }
