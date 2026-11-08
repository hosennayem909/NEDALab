"""Multi-dataset join operations."""
import pandas as pd


def join_datasets(
    left: pd.DataFrame,
    right: pd.DataFrame,
    left_key: str,
    right_key: str,
    join_type: str = "inner",
) -> tuple:
    """Join two dataframes on specified keys."""
    if left_key not in left.columns:
        raise ValueError(f"Left key '{left_key}' not in left dataset")
    if right_key not in right.columns:
        raise ValueError(f"Right key '{right_key}' not in right dataset")

    join_type = join_type.lower()
    if join_type not in ("inner", "left", "right", "outer"):
        raise ValueError(f"Invalid join_type: {join_type}")

    # Rename right key to match left for consistent joining (if different)
    right_renamed = right
    if left_key != right_key:
        right_renamed = right.rename(columns={right_key: left_key})

    # Rename overlapping non-key columns to avoid collision
    common = [c for c in left.columns if c in right_renamed.columns and c != left_key]
    rename_map = {c: f"{c}_right" for c in common}
    if rename_map:
        right_renamed = right_renamed.rename(columns=rename_map)

    try:
        result = left.merge(right_renamed, on=left_key, how=join_type)
    except Exception as e:
        raise ValueError(f"Join failed: {e}")

    # Drop exact duplicate columns
    result = result.loc[:, ~result.columns.duplicated()]

    stats = {
        "left_rows": int(len(left)),
        "right_rows": int(len(right)),
        "result_rows": int(len(result)),
        "result_columns": int(len(result.columns)),
        "join_type": join_type,
        "key": left_key,
        "match_rate_left": round(len(result) / len(left) * 100, 2) if len(left) > 0 else 0,
    }

    preview = result.head(20).fillna("").astype(str).to_dict(orient="records")

    return result, stats, preview
