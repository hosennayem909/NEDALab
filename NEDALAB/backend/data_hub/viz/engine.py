"""Visualization data engine — returns JSON for Plotly.js."""
import numpy as np
import pandas as pd


def _sf(v, d=4):
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, d)
    except (TypeError, ValueError):
        return None


def _to_py(v):
    if isinstance(v, (np.bool_,)): return bool(v)
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, (np.floating,)): return _sf(v, 6)
    if isinstance(v, np.ndarray): return [_to_py(x) for x in v.tolist()]
    if isinstance(v, list): return [_to_py(x) for x in v]
    if isinstance(v, dict): return {k: _to_py(val) for k, val in v.items()}
    if isinstance(v, float):
        if np.isnan(v) or np.isinf(v): return None
        return round(v, 6)
    if pd.isna(v): return None
    return v


def _check_cols(df, cols):
    for c in cols:
        if c not in df.columns:
            raise ValueError(f"Column '{c}' not found")


# ============================================================
# LINE CHART
# ============================================================
def line_data(df, x_col, y_cols, agg="sum"):
    """Aggregate Y columns over X (time or category)."""
    _check_cols(df, [x_col] + y_cols)

    sub = df[[x_col] + y_cols].copy()
    # Try parse x as date
    try:
        parsed = pd.to_datetime(sub[x_col], errors="coerce")
        if parsed.notna().sum() >= len(sub) * 0.5:
            sub[x_col] = parsed
    except Exception:
        pass

    for c in y_cols:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub = sub.dropna(subset=[x_col])

    # Aggregate
    try:
        grouped = sub.groupby(x_col)[y_cols].agg(agg).reset_index()
    except Exception:
        grouped = sub.sort_values(x_col)

    return {
        "chart": "line",
        "x": [str(v) for v in grouped[x_col].tolist()],
        "series": [
            {"name": c, "y": [_to_py(v) for v in grouped[c].tolist()]}
            for c in y_cols
        ],
        "n_points": int(len(grouped)),
        "aggregation": agg,
    }


# ============================================================
# BAR CHART
# ============================================================
def bar_data(df, x_col, y_col, agg="sum", top_n=None):
    """Category-wise bar chart."""
    _check_cols(df, [x_col, y_col])
    sub = df[[x_col, y_col]].copy()
    sub[y_col] = pd.to_numeric(sub[y_col], errors="coerce")
    sub = sub.dropna()

    grouped = sub.groupby(x_col)[y_col].agg(agg).reset_index()
    grouped = grouped.sort_values(y_col, ascending=False)
    if top_n:
        grouped = grouped.head(int(top_n))

    return {
        "chart": "bar",
        "x": [str(v) for v in grouped[x_col].tolist()],
        "y": [_to_py(v) for v in grouped[y_col].tolist()],
        "n_categories": int(len(grouped)),
        "aggregation": agg,
    }


# ============================================================
# SCATTER
# ============================================================
def scatter_data(df, x_col, y_col, color_col=None, max_points=2000):
    """Scatter plot X vs Y."""
    _check_cols(df, [x_col, y_col])
    cols = [x_col, y_col] + ([color_col] if color_col else [])
    sub = df[cols].copy()
    sub[x_col] = pd.to_numeric(sub[x_col], errors="coerce")
    sub[y_col] = pd.to_numeric(sub[y_col], errors="coerce")
    sub = sub.dropna(subset=[x_col, y_col])

    if len(sub) > max_points:
        sub = sub.sample(n=max_points, random_state=42)

    result = {
        "chart": "scatter",
        "x": [_to_py(v) for v in sub[x_col].tolist()],
        "y": [_to_py(v) for v in sub[y_col].tolist()],
        "x_label": str(x_col),
        "y_label": str(y_col),
        "n_points": int(len(sub)),
    }

    if color_col and color_col in sub.columns:
        result["color_values"] = [str(v) for v in sub[color_col].tolist()]
        result["color_label"] = str(color_col)

    # Fit linear regression for trend line
    try:
        x_arr = sub[x_col].to_numpy(dtype=float)
        y_arr = sub[y_col].to_numpy(dtype=float)
        m, b = np.polyfit(x_arr, y_arr, 1)
        result["trend"] = {"slope": _sf(m, 6), "intercept": _sf(b, 6)}
    except Exception:
        pass

    return result


# ============================================================
# HISTOGRAM
# ============================================================
def histogram_data(df, col, bins=30):
    """Numeric column distribution."""
    _check_cols(df, [col])
    s = pd.to_numeric(df[col], errors="coerce").dropna()

    counts, edges = np.histogram(s.to_numpy(dtype=float), bins=int(bins))
    centers = [(edges[i] + edges[i+1]) / 2 for i in range(len(edges)-1)]

    return {
        "chart": "histogram",
        "bins": [_sf(e, 4) for e in edges.tolist()],
        "counts": [int(c) for c in counts.tolist()],
        "centers": [_sf(c, 4) for c in centers],
        "n": int(len(s)),
        "mean": _sf(s.mean(), 4),
        "median": _sf(s.median(), 4),
        "std": _sf(s.std(ddof=1), 4) if len(s) > 1 else 0.0,
        "min": _sf(s.min(), 4),
        "max": _sf(s.max(), 4),
    }


# ============================================================
# BOX PLOT
# ============================================================
def box_data(df, col, group_col=None, max_groups=20):
    """Box plot — overall or grouped."""
    _check_cols(df, [col])
    sub = df[[col] + ([group_col] if group_col else [])].copy()
    sub[col] = pd.to_numeric(sub[col], errors="coerce")
    sub = sub.dropna(subset=[col])

    def _box_stats(arr):
        arr = np.asarray(arr, dtype=float)
        q1, q2, q3 = np.percentile(arr, [25, 50, 75])
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outliers = arr[(arr < lower) | (arr > upper)].tolist()
        return {
            "q1": _sf(q1, 4), "median": _sf(q2, 4), "q3": _sf(q3, 4),
            "lower_fence": _sf(lower, 4), "upper_fence": _sf(upper, 4),
            "min": _sf(arr.min(), 4), "max": _sf(arr.max(), 4),
            "outliers": [_sf(o, 4) for o in outliers[:500]],
            "n": int(len(arr)),
        }

    if group_col:
        groups = sub.groupby(group_col)[col].apply(list).items()
        group_list = list(groups)[:max_groups]
        return {
            "chart": "box_grouped",
            "y_label": str(col),
            "groups": [str(g) for g, _ in group_list],
            "stats": [_box_stats(v) for _, v in group_list],
        }
    else:
        return {
            "chart": "box",
            "y_label": str(col),
            "stats": _box_stats(sub[col].tolist()),
        }


# ============================================================
# PIE
# ============================================================
def pie_data(df, category_col, value_col=None, top_n=10):
    """Pie/donut breakdown."""
    _check_cols(df, [category_col] + ([value_col] if value_col else []))

    if value_col:
        sub = df[[category_col, value_col]].copy()
        sub[value_col] = pd.to_numeric(sub[value_col], errors="coerce")
        sub = sub.dropna()
        grouped = sub.groupby(category_col)[value_col].sum().reset_index()
        grouped.columns = ["category", "value"]
    else:
        grouped = df[category_col].value_counts().reset_index()
        grouped.columns = ["category", "value"]

    grouped = grouped.sort_values("value", ascending=False)

    if top_n and len(grouped) > top_n:
        top = grouped.head(top_n - 1)
        other = grouped.iloc[top_n - 1:]["value"].sum()
        other_row = pd.DataFrame([{"category": "Other", "value": other}])
        grouped = pd.concat([top, other_row], ignore_index=True)

    return {
        "chart": "pie",
        "labels": [str(v) for v in grouped["category"].tolist()],
        "values": [_to_py(v) for v in grouped["value"].tolist()],
        "total": _to_py(grouped["value"].sum()),
        "n_categories": int(len(grouped)),
    }


# ============================================================
# HEATMAP (Correlation)
# ============================================================
def heatmap_data(df, cols):
    """Correlation heatmap."""
    _check_cols(df, cols)
    sub = df[cols].apply(pd.to_numeric, errors="coerce").dropna()

    if len(sub) < 3:
        raise ValueError("Need at least 3 valid rows")

    corr = sub.corr(method="pearson")
    matrix = [[_sf(corr.iloc[i, j], 4) for j in range(len(cols))] for i in range(len(cols))]

    return {
        "chart": "heatmap",
        "columns": list(cols),
        "matrix": matrix,
        "n_obs": int(len(sub)),
    }


# ============================================================
# COLUMN INFO
# ============================================================
def column_info(df):
    numeric = df.select_dtypes(include="number").columns.tolist()
    categorical = [c for c in df.columns if c not in numeric]

    # Detect date columns
    date_cols = []
    for c in categorical:
        try:
            sample = df[c].dropna().head(20)
            if len(sample) == 0: continue
            parsed = pd.to_datetime(sample, errors="coerce")
            if parsed.notna().sum() >= max(1, int(len(sample) * 0.8)):
                date_cols.append(c)
        except Exception:
            pass

    return {
        "all_columns": [str(c) for c in df.columns],
        "numeric_columns": [str(c) for c in numeric],
        "categorical_columns": [str(c) for c in categorical],
        "date_columns": date_cols,
    }
