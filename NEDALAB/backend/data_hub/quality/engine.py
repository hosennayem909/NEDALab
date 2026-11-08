"""Data quality report engine."""
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


def scan_quality(df: pd.DataFrame) -> dict:
    """Full data quality scan."""
    n_rows = len(df)
    n_cols = len(df.columns)
    if n_rows == 0 or n_cols == 0:
        return {"error": "Empty dataframe"}

    total_cells = n_rows * n_cols
    total_missing = int(df.isna().sum().sum())
    missing_pct = round(total_missing / total_cells * 100, 2) if total_cells else 0

    duplicate_rows = int(df.duplicated().sum())

    # Column-level analysis
    columns = []
    issues = []

    for col in df.columns:
        s = df[col]
        n_null = int(s.isna().sum())
        null_pct = round(n_null / n_rows * 100, 2)
        n_unique = int(s.nunique(dropna=True))
        dtype = str(s.dtype)

        # Detect actual type
        actual_type = "unknown"
        if pd.api.types.is_numeric_dtype(s):
            actual_type = "numeric"
        elif pd.api.types.is_datetime64_any_dtype(s):
            actual_type = "datetime"
        else:
            # Try date parse
            try:
                sample = s.dropna().head(20)
                if len(sample) > 0:
                    parsed = pd.to_datetime(sample, errors="coerce")
                    if parsed.notna().sum() >= max(1, int(len(sample) * 0.8)):
                        actual_type = "date"
                    else:
                        # Try numeric
                        parsed_num = pd.to_numeric(sample, errors="coerce")
                        if parsed_num.notna().sum() >= max(1, int(len(sample) * 0.8)):
                            actual_type = "numeric_string"
                        else:
                            actual_type = "categorical" if n_unique < 30 else "text"
                else:
                    actual_type = "empty"
            except Exception:
                actual_type = "text"

        col_info = {
            "name": str(col),
            "dtype": dtype,
            "detected_type": actual_type,
            "null_count": n_null,
            "null_pct": null_pct,
            "unique_count": n_unique,
        }

        # Column-specific stats
        if actual_type == "numeric" or actual_type == "numeric_string":
            try:
                num = pd.to_numeric(s, errors="coerce").dropna()
                if len(num) > 0:
                    col_info["mean"] = _sf(num.mean(), 4)
                    col_info["std"] = _sf(num.std(ddof=1), 4) if len(num) > 1 else 0.0
                    col_info["min"] = _sf(num.min(), 4)
                    col_info["max"] = _sf(num.max(), 4)
                    # Outliers (IQR)
                    if len(num) >= 4:
                        q1, q3 = num.quantile(0.25), num.quantile(0.75)
                        iqr = q3 - q1
                        if iqr > 0:
                            lower = q1 - 1.5 * iqr
                            upper = q3 + 1.5 * iqr
                            n_outliers = int(((num < lower) | (num > upper)).sum())
                            col_info["outlier_count"] = n_outliers
                            col_info["outlier_pct"] = round(n_outliers / len(num) * 100, 2)
            except Exception:
                pass

        columns.append(col_info)

        # Add issues
        if null_pct > 50:
            issues.append({"column": str(col), "severity": "high", "issue": f"{null_pct}% missing"})
        elif null_pct > 10:
            issues.append({"column": str(col), "severity": "medium", "issue": f"{null_pct}% missing"})

        if n_unique == 1 and n_rows > 1:
            issues.append({"column": str(col), "severity": "medium", "issue": "Constant column"})

        if n_unique == n_rows and actual_type in ("categorical", "text"):
            issues.append({"column": str(col), "severity": "low", "issue": "All unique (possible ID)"})

    # Overall health score
    score = 100.0
    # Missing penalty
    score -= min(missing_pct * 0.5, 30)
    # Duplicate penalty
    if n_rows > 0:
        dup_pct = duplicate_rows / n_rows * 100
        score -= min(dup_pct * 0.5, 20)
    # Issue penalty
    for iss in issues:
        score -= {"high": 5, "medium": 2, "low": 1}.get(iss["severity"], 1)

    score = max(0.0, round(score, 1))

    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "n_rows": n_rows,
        "n_columns": n_cols,
        "total_cells": total_cells,
        "total_missing": total_missing,
        "missing_pct": missing_pct,
        "duplicate_rows": duplicate_rows,
        "duplicate_pct": round(duplicate_rows / n_rows * 100, 2) if n_rows else 0,
        "health_score": score,
        "grade": grade,
        "n_issues": len(issues),
        "issues": issues,
        "columns": columns,
    }
