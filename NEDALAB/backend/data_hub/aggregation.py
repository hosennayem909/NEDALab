import pandas as pd
import numpy as np


FREQ_MAP = {
    "day": "D",
    "week": "W",
    "month": "MS",   # month start
}

AGG_MAP = {
    "sum": "sum",
    "mean": "mean",
    "count": "count",
    "max": "max",
    "min": "min",
    "median": "median",
}


def detect_datetime_columns(df: pd.DataFrame) -> list:
    """Try to detect which columns look like dates."""
    date_cols = []
    for col in df.columns:
        # Already datetime
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            date_cols.append(col)
            continue
        # Try parsing a sample
        sample = df[col].dropna().head(20)
        if len(sample) == 0:
            continue
        try:
            parsed = pd.to_datetime(sample, errors="coerce")
            # If >80% parsed successfully, treat as date
            if parsed.notna().sum() >= max(1, int(len(sample) * 0.8)):
                date_cols.append(col)
        except Exception:
            pass
    return date_cols


def detect_numeric_columns(df: pd.DataFrame) -> list:
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


def aggregate_dataframe(
    df: pd.DataFrame,
    date_column: str,
    value_columns: list,
    frequency: str,
    method: str,
) -> tuple[pd.DataFrame, dict]:
    """
    Aggregate df by date_column into time-series.
    Returns (aggregated_df, report).
    """
    if df is None or df.empty:
        raise ValueError("Input DataFrame is empty")
    if date_column not in df.columns:
        raise ValueError(f"Date column '{date_column}' not found")
    if not value_columns:
        raise ValueError("At least one value column required")

    cleaned_values = []
    for vc in value_columns:
        if vc not in df.columns:
            raise ValueError(f"Value column '{vc}' not found")
        if df[vc].isna().all():
            raise ValueError(f"Value column '{vc}' is entirely null")
        if not pd.api.types.is_numeric_dtype(df[vc]):
            raise ValueError(f"Column '{vc}' is not numeric")
        cleaned_values.append(vc)

    value_columns = cleaned_values

    freq_code = FREQ_MAP.get(frequency)
    agg_func = AGG_MAP.get(method)
    if not freq_code:
        raise ValueError(f"Unknown frequency: {frequency}")
    if not agg_func:
        raise ValueError(f"Unknown method: {method}")

    # Parse date column
    work = df.copy()
    parsed = pd.to_datetime(work[date_column], errors="coerce")
    valid_mask = parsed.notna()
    dropped = int((~valid_mask).sum())

    work = work[valid_mask].copy()
    work["__date__"] = parsed[valid_mask]

    if work.empty:
        raise ValueError("No rows with valid dates after parsing")

    # Group by frequency
    work = work.set_index("__date__")
    grouped = work[value_columns].resample(freq_code).agg(agg_func)
    grouped = grouped.fillna(0).reset_index()
    grouped = grouped.rename(columns={"__date__": date_column})

    # Sort ascending by date
    grouped = grouped.sort_values(date_column).reset_index(drop=True)

    report = {
        "date_column": date_column,
        "value_columns": value_columns,
        "frequency": frequency,
        "method": method,
        "source_rows": int(len(df)),
        "valid_dates": int(valid_mask.sum()),
        "dropped_invalid_dates": dropped,
        "aggregated_rows": int(len(grouped)),
        "date_range": [
            str(grouped[date_column].min().date()) if not grouped.empty else None,
            str(grouped[date_column].max().date()) if not grouped.empty else None,
        ],
    }
    return grouped, report


def get_column_info(df: pd.DataFrame) -> dict:
    """Return detected date and numeric columns for the UI."""
    return {
        "all_columns": [str(c) for c in df.columns],
        "date_columns": [str(c) for c in detect_datetime_columns(df)],
        "numeric_columns": [str(c) for c in detect_numeric_columns(df)],
    }
