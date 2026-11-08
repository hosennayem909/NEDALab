import json
import re
import pandas as pd
from rapidfuzz import fuzz


def _normalize(s: str, case_sensitive: bool) -> str:
    s = str(s).strip()
    return s if case_sensitive else s.lower()


def find_best_match(value, rules):
    """Find best matching rule for a value. Returns (rule, keyword, score) or (None, None, 0)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None, None, 0.0

    raw = str(value).strip()
    if not raw:
        return None, None, 0.0

    best_rule, best_kw, best_score = None, None, 0.0

    for rule in rules:
        if not rule.get("active", True):
            continue
        case_sensitive = rule.get("case_sensitive", False)
        norm_value = _normalize(raw, case_sensitive)
        match_type = rule.get("match_type", "fuzzy")
        threshold = rule.get("match_threshold", 80)

        for kw in rule.get("keywords", []):
            norm_kw = _normalize(kw, case_sensitive)
            if not norm_kw:
                continue

            if match_type == "exact":
                if norm_value == norm_kw:
                    score = 100.0
                else:
                    score = 0.0
            elif match_type == "contains":
                if norm_kw in norm_value:
                    score = 100.0
                else:
                    score = 0.0
            elif match_type == "regex":
                try:
                    if re.search(kw, raw, 0 if case_sensitive else re.IGNORECASE):
                        score = 100.0
                    else:
                        score = 0.0
                except re.error:
                    score = 0.0
            else:  # fuzzy
                score = float(fuzz.ratio(norm_value, norm_kw))

            if score >= threshold and score > best_score:
                best_rule = rule
                best_kw = kw
                best_score = score

    if best_rule is None:
        return None, None, 0.0
    return best_rule, best_kw, best_score


def apply_mapping(df: pd.DataFrame, column: str, rules: list) -> tuple:
    """Apply entity mapping to a dataframe column. Returns (new_df, summary)."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")

    df = df.copy()
    changed = 0
    summary = {}

    for idx, val in df[column].items():
        rule, kw, score = find_best_match(val, rules)
        if rule is not None:
            new_val = rule["standard_value"]
            if str(val) != new_val:
                df.at[idx, column] = new_val
                changed += 1
                key = rule["name"]
                summary[key] = summary.get(key, 0) + 1

    summary_list = [
        {"rule": k, "rows_changed": v} for k, v in sorted(summary.items(), key=lambda x: -x[1])
    ]
    return df, {"total_rows": len(df), "changed_rows": changed, "summary": summary_list}


def test_values(values: list, rules: list) -> list:
    """Test matching against a list of values."""
    results = []
    for v in values:
        rule, kw, score = find_best_match(v, rules)
        results.append({
            "original": str(v),
            "matched": rule is not None,
            "standard_value": rule["standard_value"] if rule else None,
            "matched_keyword": kw,
            "score": round(float(score), 2),
            "rule_name": rule["name"] if rule else None,
        })
    return results
