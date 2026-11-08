import pandas as pd


def get_preview(df: pd.DataFrame, limit: int = 20) -> dict:
    columns = []
    for col in df.columns:
        s = df[col]
        columns.append({
            "name": str(col),
            "dtype": str(s.dtype),
            "null_count": int(s.isna().sum()),
            "unique_count": int(s.nunique(dropna=True)),
        })

    rows = []
    for _, row in df.head(limit).iterrows():
        rows.append({str(k): (None if pd.isna(v) else v) for k, v in row.items()})

    return {
        "columns": columns,
        "rows": rows,
        "total_rows": int(len(df)),
        "preview_rows": len(rows),
    }


def get_stats(df: pd.DataFrame) -> dict:
    numeric = {}
    for col in df.select_dtypes(include="number").columns:
        s = df[col].dropna()
        if len(s) == 0:
            continue
        numeric[str(col)] = {
            "count": int(len(s)),
            "mean": round(float(s.mean()), 4),
            "std": round(float(s.std()), 4) if len(s) > 1 else 0.0,
            "min": round(float(s.min()), 4),
            "max": round(float(s.max()), 4),
            "q1": round(float(s.quantile(0.25)), 4),
            "median": round(float(s.median()), 4),
            "q3": round(float(s.quantile(0.75)), 4),
        }
    return {
        "numeric": numeric,
        "total_rows": int(len(df)),
        "total_columns": int(len(df.columns)),
    }
