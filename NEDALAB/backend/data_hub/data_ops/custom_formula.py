"""Safe custom formula engine using pandas.eval."""
import pandas as pd
import numpy as np
import re


# Allowed functions in formulas
SAFE_FUNCTIONS = {
    "abs": np.abs,
    "round": np.round,
    "sqrt": np.sqrt,
    "log": np.log,
    "log10": np.log10,
    "exp": np.exp,
    "min": np.minimum,
    "max": np.maximum,
    "floor": np.floor,
    "ceil": np.ceil,
    "sign": np.sign,
    "where": np.where,
}

# Regex to detect column references (identifiers not followed by parenthesis)
IDENT_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_ ]*)\b(?!\s*\()")


def _norm(s: str) -> str:
    return str(s).strip()


def validate_formula(formula: str, columns: list):
    """Validate formula: check column refs and balance."""
    if not formula or not formula.strip():
        raise ValueError("Formula is empty")

    formula = formula.strip()

    # Check balanced parentheses
    depth = 0
    for ch in formula:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                raise ValueError("Unbalanced parentheses")

    if depth != 0:
        raise ValueError("Unbalanced parentheses")

    # Extract identifiers
    tokens = IDENT_RE.findall(formula)

    # Filter out function names and Python keywords
    keywords = {"and", "or", "not", "in", "is", "True", "False", "None"}
    column_set = {_norm(c) for c in columns}

    used_columns = []
    unknown = []
    for t in tokens:
        t_norm = t.strip()
        if t_norm in SAFE_FUNCTIONS or t_norm in keywords:
            continue
        if t_norm in column_set:
            used_columns.append(t_norm)
        else:
            # Try case-insensitive match
            match = [c for c in column_set if c.lower() == t_norm.lower()]
            if match:
                used_columns.append(match[0])
            else:
                # Could be a variable not in columns → error
                unknown.append(t_norm)

    # Filter unknown that look like actual column refs
    # Numbers aren't matched by IDENT_RE anyway
    if unknown:
        raise ValueError(
            f"Unknown identifier(s) in formula: {', '.join(set(unknown))}. "
            f"Available columns: {', '.join(sorted(column_set))}"
        )

    return sorted(set(used_columns))


def evaluate_formula(df: pd.DataFrame, formula: str, new_column: str) -> tuple:
    """Safely evaluate formula on df and return (new_df, stats)."""
    if not new_column or not new_column.strip():
        raise ValueError("New column name is required")

    formula = formula.strip()
    columns = list(df.columns)

    used_cols = validate_formula(formula, columns)

    # Build a clean env — no builtins
    env = {}
    for c in columns:
        env[c] = df[c]

    # Local dict for eval with restricted globals
    local_vars = {**env, **SAFE_FUNCTIONS}

    try:
        result = eval(formula, {"__builtins__": {}}, local_vars)
    except Exception as e:
        raise ValueError(f"Formula evaluation failed: {type(e).__name__}: {e}")

    # Coerce to Series
    if isinstance(result, (int, float)):
        series = pd.Series([result] * len(df), index=df.index)
    elif isinstance(result, np.ndarray):
        series = pd.Series(result, index=df.index)
    elif isinstance(result, pd.Series):
        series = result
    else:
        raise ValueError(f"Formula returned unsupported type: {type(result).__name__}")

    # Replace inf with NaN
    series = series.replace([np.inf, -np.inf], np.nan)

    new_df = df.copy()
    new_df[new_column.strip()] = series

    # Stats
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    stats = {
        "new_column": new_column.strip(),
        "formula": formula,
        "used_columns": used_cols,
        "total_rows": int(len(new_df)),
        "valid_values": int(len(numeric)),
        "nan_count": int(series.isna().sum()),
    }
    if len(numeric) > 0:
        stats["mean"] = round(float(numeric.mean()), 4)
        stats["min"] = round(float(numeric.min()), 4)
        stats["max"] = round(float(numeric.max()), 4)
        stats["std"] = round(float(numeric.std()), 4) if len(numeric) > 1 else 0.0

    # Sample rows for preview
    preview = new_df.head(20).fillna("").astype(str).to_dict(orient="records")

    return new_df, stats, preview
