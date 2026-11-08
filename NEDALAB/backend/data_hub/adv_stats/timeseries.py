"""Time-series specific cleaning."""
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller


def parse_dates_safe(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def detect_gaps(df: pd.DataFrame, date_col: str, frequency: str = "day") -> dict:
    """Detect missing dates in a time series (handles duplicates)."""
    if date_col not in df.columns:
        raise ValueError(f"Column '{date_col}' not found")

    dates = parse_dates_safe(df[date_col]).dropna()
    if len(dates) < 2:
        return {"gap_count": 0, "expected": 0, "actual": int(len(dates)), "gaps_preview": []}

    unique_dates = dates.dt.normalize().drop_duplicates().sort_values()

    freq_map = {"day": "D", "week": "W", "month": "MS"}
    pd_freq = freq_map.get(frequency, "D")

    full_range = pd.date_range(start=unique_dates.min(), end=unique_dates.max(), freq=pd_freq)
    existing = set(unique_dates.tolist())
    missing = [d for d in full_range if d.normalize() not in existing]

    return {
        "gap_count": len(missing),
        "expected": len(full_range),
        "actual": int(len(unique_dates)),
        "date_min": str(unique_dates.min().date()),
        "date_max": str(unique_dates.max().date()),
        "frequency": frequency,
        "gaps_preview": [str(d.date()) for d in missing[:20]],
    }


def fill_gaps(
    df: pd.DataFrame,
    date_col: str,
    frequency: str = "day",
    method: str = "ffill",
    value_cols: list | None = None,
) -> tuple:
    """Insert missing dates. Aggregates duplicates by sum first."""
    if date_col not in df.columns:
        raise ValueError(f"Column '{date_col}' not found")

    freq_map = {"day": "D", "week": "W", "month": "MS"}
    pd_freq = freq_map.get(frequency, "D")

    df = df.copy()
    df[date_col] = parse_dates_safe(df[date_col])
    df = df.dropna(subset=[date_col])

    if df.empty:
        raise ValueError("No valid dates found")

    # Aggregate duplicates by date (sum numeric, first for text)
    df["__date__"] = df[date_col].dt.normalize()

    if value_cols is None:
        value_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c != "__date__"]

    agg_dict = {c: "sum" for c in value_cols}
    other_cols = [c for c in df.columns if c not in value_cols and c not in (date_col, "__date__")]
    for c in other_cols:
        agg_dict[c] = "first"

    grouped = df.groupby("__date__", as_index=True).agg(agg_dict).sort_index()

    # Reindex to full range
    full_range = pd.date_range(start=grouped.index.min(), end=grouped.index.max(), freq=pd_freq)
    grouped = grouped.reindex(full_range)
    grouped.index.name = date_col

    if method == "ffill":
        grouped[value_cols] = grouped[value_cols].ffill().bfill()
    elif method == "bfill":
        grouped[value_cols] = grouped[value_cols].bfill().ffill()
    elif method == "zero":
        grouped[value_cols] = grouped[value_cols].fillna(0)
    elif method == "mean":
        grouped[value_cols] = grouped[value_cols].fillna(grouped[value_cols].mean())

    grouped = grouped.reset_index()
    added_rows = len(grouped) - len(df["__date__"].unique())

    return grouped, {
        "original_unique_dates": int(len(df["__date__"].unique())),
        "filled_dates": int(added_rows),
        "total_rows": int(len(grouped)),
        "method": method,
        "frequency": frequency,
    }


def adf_test(s: pd.Series) -> dict:
    """Augmented Dickey-Fuller stationarity test."""
    parsed = pd.to_numeric(s, errors="coerce").dropna()
    if len(parsed) < 10:
        return {"error": "Need at least 10 data points"}

    try:
        result = adfuller(parsed.to_numpy(dtype=float), autolag="AIC")
    except Exception as e:
        return {"error": str(e)}

    adf_stat, p_value, used_lag, n_obs, crit_values, icbest = result[:6]
    is_stationary = p_value < 0.05

    return {
        "adf_statistic": round(float(adf_stat), 4),
        "p_value": round(float(p_value), 4),
        "used_lag": int(used_lag),
        "n_observations": int(n_obs),
        "critical_values": {k: round(float(v), 4) for k, v in crit_values.items()},
        "is_stationary": is_stationary,
        "interpretation": (
            "Data is stationary (reject H0). Safe for ARIMA."
            if is_stationary
            else "Data is non-stationary (fail to reject H0). Consider differencing."
        ),
    }


def difference_series(s: pd.Series, order: int = 1) -> tuple:
    """Apply differencing."""
    parsed = pd.to_numeric(s, errors="coerce")
    original = parsed.copy()
    new = parsed.copy()
    for _ in range(order):
        new = new.diff()
    return new, {
        "order": order,
        "original_nan": int(original.isna().sum()),
        "diff_nan": int(new.isna().sum()),
    }


def analyze_time_series(df: pd.DataFrame, date_col: str, value_col: str) -> dict:
    """Full time-series analysis (safe for duplicates)."""
    if date_col not in df.columns:
        raise ValueError(f"Date column '{date_col}' not found")
    if value_col not in df.columns:
        raise ValueError(f"Value column '{value_col}' not found")

    # Try to parse dates; if 0 valid → error out clearly
    dates = parse_dates_safe(df[date_col])
    if dates.notna().sum() == 0:
        raise ValueError(
            f"Column '{date_col}' does not contain valid dates. "
            "Please select a real date column."
        )

    gaps = detect_gaps(df, date_col, "day")
    adf = adf_test(df[value_col])
    return {"gaps": gaps, "stationarity": adf, "value_column": value_col}
