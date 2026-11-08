import pandas as pd
import numpy as np


# ============================================================
# PRESETS
# ============================================================

PRESETS = {
    "minimal": {
        "drop_empty_rows": True,
        "duplicates": "keep",
        "missing": "keep",
        "outliers": "keep",
        "strings": "trim",
    },
    "standard": {
        "drop_empty_rows": True,
        "duplicates": "drop_all",
        "missing": "auto",       # numeric → mean, categorical → mode
        "outliers": "keep",
        "strings": "trim",
    },
    "aggressive": {
        "drop_empty_rows": True,
        "duplicates": "drop_all",
        "missing": "drop_rows",
        "outliers": "iqr",
        "strings": "trim_lower",
    },
}


def resolve_config(config: dict) -> dict:
    """If preset is set and not 'custom', use preset values."""
    preset = str(config.get("preset", "standard") or "standard").strip().lower()
    if preset in PRESETS:
        return {**PRESETS[preset], "_preset": preset}

    allowed = {"drop_empty_rows": bool, "duplicates": {"keep", "drop_all"}, "missing": {"keep", "drop_rows", "drop_columns", "auto", "mean", "median", "mode", "zero", "ffill", "bfill"}, "outliers": {"keep", "iqr", "zscore"}, "strings": {"keep", "trim", "trim_lower"}}
    out = {
        "drop_empty_rows": bool(config.get("drop_empty_rows", True)),
        "duplicates": config.get("duplicates", "drop_all"),
        "missing": config.get("missing", "auto"),
        "outliers": config.get("outliers", "keep"),
        "strings": config.get("strings", "trim"),
        "_preset": "custom",
    }

    if out["duplicates"] not in allowed["duplicates"]:
        out["duplicates"] = "drop_all"
    if out["missing"] not in allowed["missing"]:
        out["missing"] = "auto"
    if out["outliers"] not in allowed["outliers"]:
        out["outliers"] = "keep"
    if out["strings"] not in allowed["strings"]:
        out["strings"] = "trim"

    return out


# ============================================================
# STRATEGY FUNCTIONS
# ============================================================

def _snapshot(df: pd.DataFrame) -> dict:
    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "missing": int(df.isna().sum().sum()),
        "duplicates": int(df.duplicated().sum()),
        "empty_rows": int(df.isna().all(axis=1).sum()),
    }


def _drop_empty_rows(df: pd.DataFrame, log: list) -> pd.DataFrame:
    before = len(df)
    df = df.dropna(how="all").reset_index(drop=True)
    removed = before - len(df)
    if removed:
        log.append(f"Dropped {removed} completely empty row(s)")
    return df


def _handle_duplicates(df: pd.DataFrame, strategy: str, log: list) -> pd.DataFrame:
    if strategy != "drop_all":
        return df
    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    removed = before - len(df)
    if removed:
        log.append(f"Removed {removed} duplicate row(s)")
    return df


def _handle_missing(df: pd.DataFrame, strategy: str, log: list) -> pd.DataFrame:
    if strategy == "keep" or df.empty:
        return df

    if strategy == "drop_rows":
        before = len(df)
        df = df.dropna().reset_index(drop=True)
        removed = before - len(df)
        if removed:
            log.append(f"Dropped {removed} row(s) with missing values")
        return df

    if strategy == "drop_columns":
        before = len(df.columns)
        df = df.dropna(axis=1, how="any")
        removed = before - len(df.columns)
        if removed:
            log.append(f"Dropped {removed} column(s) with missing values")
        return df

    # Fill strategies
    filled_cols = 0
    if strategy == "auto":
        for col in df.columns:
            if not df[col].isna().any():
                continue
            filled_cols += 1
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(df[col].mean())
            else:
                mode = df[col].mode(dropna=True)
                df[col] = df[col].fillna(mode.iloc[0] if len(mode) else "Unknown")
        log.append(f"Filled missing values in {filled_cols} column(s): numeric → mean, categorical → mode")
        return df

    if strategy == "mean":
        for col in df.select_dtypes(include="number").columns:
            if df[col].isna().any():
                df[col] = df[col].fillna(df[col].mean())
                filled_cols += 1
        log.append(f"Filled missing numeric values with column mean ({filled_cols} column(s))")
        return df

    if strategy == "median":
        for col in df.select_dtypes(include="number").columns:
            if df[col].isna().any():
                df[col] = df[col].fillna(df[col].median())
                filled_cols += 1
        log.append(f"Filled missing numeric values with column median ({filled_cols} column(s))")
        return df

    if strategy == "mode":
        for col in df.columns:
            if df[col].isna().any():
                m = df[col].mode(dropna=True)
                if len(m):
                    df[col] = df[col].fillna(m.iloc[0])
                    filled_cols += 1
        log.append(f"Filled missing values with column mode ({filled_cols} column(s))")
        return df

    if strategy == "zero":
        for col in df.select_dtypes(include="number").columns:
            if df[col].isna().any():
                df[col] = df[col].fillna(0)
                filled_cols += 1
        log.append(f"Filled missing numeric values with 0 ({filled_cols} column(s))")
        return df

    if strategy in ("ffill", "bfill"):
        method = strategy
        before_missing = int(df.isna().sum().sum())
        df = df.ffill() if method == "ffill" else df.bfill()
        after_missing = int(df.isna().sum().sum())
        log.append(f"Filled missing values ({method}): {before_missing - after_missing} value(s) filled")
        return df

    return df


def _handle_outliers(df: pd.DataFrame, strategy: str, log: list) -> pd.DataFrame:
    if strategy == "keep":
        return df

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if not numeric_cols:
        return df

    if strategy == "iqr":
        before = len(df)
        mask = pd.Series(True, index=df.index)
        for col in numeric_cols:
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            mask &= (df[col] >= lower) & (df[col] <= upper)
        df = df[mask].reset_index(drop=True)
        removed = before - len(df)
        if removed:
            log.append(f"Removed {removed} outlier row(s) using IQR method ({len(numeric_cols)} numeric column(s))")
        return df

    if strategy == "zscore":
        before = len(df)
        mask = pd.Series(True, index=df.index)
        for col in numeric_cols:
            s = df[col].dropna()
            if len(s) < 3 or s.std() == 0:
                continue
            z = np.abs((df[col] - s.mean()) / s.std())
            mask &= (z <= 3) | df[col].isna()
        df = df[mask].reset_index(drop=True)
        removed = before - len(df)
        if removed:
            log.append(f"Removed {removed} outlier row(s) using Z-score > 3 ({len(numeric_cols)} numeric column(s))")
        return df

    return df


def _handle_strings(df: pd.DataFrame, strategy: str, log: list) -> pd.DataFrame:
    if strategy == "keep":
        return df

    obj_cols = df.select_dtypes(include="object").columns.tolist()
    if not obj_cols:
        return df

    for col in obj_cols:
        df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)

    if strategy == "trim_lower":
        for col in obj_cols:
            df[col] = df[col].apply(lambda x: x.lower() if isinstance(x, str) else x)
        log.append(f"Trimmed whitespace and lowercased {len(obj_cols)} text column(s)")
    else:
        log.append(f"Trimmed whitespace from {len(obj_cols)} text column(s)")

    return df


# ============================================================
# MAIN ENTRY
# ============================================================

def apply_cleaning(df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, dict]:
    """
    Applies the requested cleaning steps to df.
    Returns (cleaned_df, report_dict).
    """
    cfg = resolve_config(config)
    log = []
    stats_before = _snapshot(df)

    if cfg["drop_empty_rows"]:
        df = _drop_empty_rows(df, log)
    df = _handle_duplicates(df, cfg["duplicates"], log)
    df = _handle_missing(df, cfg["missing"], log)
    df = _handle_outliers(df, cfg["outliers"], log)
    df = _handle_strings(df, cfg["strings"], log)

    stats_after = _snapshot(df)

    report = {
        "preset": cfg.get("_preset", "standard"),
        "config": {k: v for k, v in cfg.items() if not k.startswith("_")},
        "log": log if log else ["No changes applied — data was already clean"],
        "stats_before": stats_before,
        "stats_after": stats_after,
        "rows_removed": stats_before["rows"] - stats_after["rows"],
        "columns_removed": stats_before["columns"] - stats_after["columns"],
        "missing_filled": stats_before["missing"] - stats_after["missing"],
    }
    return df, report


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Legacy helper used by old routes. Uses standard preset."""
    df, report = apply_cleaning(df, {"preset": "standard"})
    return df, {"duplicates_removed": report["stats_before"]["duplicates"],
                "missing_before": report["stats_before"]["missing"],
                "missing_after": report["stats_after"]["missing"],
                "rows_after": report["stats_after"]["rows"],
                "columns_after": report["stats_after"]["columns"]}
