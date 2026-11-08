"""Model monitoring: data drift, prediction drift detection."""
import numpy as np
import pandas as pd
from scipy import stats


def _sf(v, d=6):
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, d)
    except (TypeError, ValueError):
        return None


def compute_psi(expected: np.ndarray, actual: np.ndarray, buckets: int = 10) -> float:
    """Population Stability Index."""
    try:
        # Create bins from expected
        breakpoints = np.percentile(expected, np.linspace(0, 100, buckets + 1))
        breakpoints = np.unique(breakpoints)
        if len(breakpoints) < 2:
            return 0.0

        expected_counts, _ = np.histogram(expected, bins=breakpoints)
        actual_counts, _ = np.histogram(actual, bins=breakpoints)

        expected_pct = expected_counts / max(len(expected), 1)
        actual_pct = actual_counts / max(len(actual), 1)

        # Avoid zeros
        expected_pct = np.where(expected_pct == 0, 0.0001, expected_pct)
        actual_pct = np.where(actual_pct == 0, 0.0001, actual_pct)

        psi = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
        return float(psi)
    except Exception:
        return 0.0


def detect_drift(reference_df: pd.DataFrame, current_df: pd.DataFrame, columns: list) -> dict:
    """Detect drift across features using KS test + PSI."""
    results = []
    for col in columns:
        if col not in reference_df.columns or col not in current_df.columns:
            continue

        ref = pd.to_numeric(reference_df[col], errors="coerce").dropna()
        cur = pd.to_numeric(current_df[col], errors="coerce").dropna()

        if len(ref) < 10 or len(cur) < 10:
            continue

        try:
            ks_stat, ks_p = stats.ks_2samp(ref.to_numpy(), cur.to_numpy())
            psi = compute_psi(ref.to_numpy(), cur.to_numpy())

            # Interpretation
            if psi < 0.1:
                psi_label = "no_drift"
            elif psi < 0.25:
                psi_label = "moderate_drift"
            else:
                psi_label = "significant_drift"

            results.append({
                "column": str(col),
                "ref_n": int(len(ref)),
                "cur_n": int(len(cur)),
                "ref_mean": _sf(ref.mean(), 4),
                "cur_mean": _sf(cur.mean(), 4),
                "ref_std": _sf(ref.std(ddof=1), 4),
                "cur_std": _sf(cur.std(ddof=1), 4),
                "ks_statistic": _sf(ks_stat, 4),
                "ks_pvalue": _sf(ks_p, 6),
                "is_significant": bool(ks_p < 0.05),
                "psi": _sf(psi, 4),
                "psi_label": psi_label,
            })
        except Exception:
            continue

    # Overall status
    sig_drift = sum(1 for r in results if r.get("is_significant"))
    if sig_drift == 0:
        overall = "healthy"
    elif sig_drift <= len(results) / 3:
        overall = "warning"
    else:
        overall = "critical"

    return {
        "overall_status": overall,
        "columns_analyzed": len(results),
        "columns_with_drift": sig_drift,
        "details": results,
    }
