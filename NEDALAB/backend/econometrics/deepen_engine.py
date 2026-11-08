"""Advanced econometrics: IV (2SLS), Difference-in-Differences, Cointegration."""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.vector_ar.vecm import coint_johansen, VECM
from linearmodels.iv import IV2SLS


def _py(v, d=6):
    try:
        if v is None:
            return None
        if isinstance(v, (np.bool_,)):
            return bool(v)
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            f = float(v)
            if np.isnan(f) or np.isinf(f):
                return None
            return round(f, d)
        if isinstance(v, np.ndarray):
            return [_py(x, d) for x in v.tolist()]
    except Exception:
        pass
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, d)
    except (TypeError, ValueError):
        return v
    return v


# ============================================================
# IV Regression (2SLS)
# ============================================================
def iv_regression(df, dependent, endogenous, instruments, exog=None):
    """Two-Stage Least Squares.

    dependent: Y
    endogenous: list of endogenous regressors (correlated with error)
    instruments: list of instruments (Z, correlated with endogenous, not with error)
    exog: list of exogenous controls (X, included directly)
    """
    if endogenous is None or not endogenous:
        raise ValueError("At least one endogenous variable required")
    if instruments is None or not instruments:
        raise ValueError("At least one instrument required")

    all_cols = [dependent] + list(endogenous) + list(instruments)
    if exog:
        all_cols += list(exog)

    for c in all_cols:
        if c not in df.columns:
            raise ValueError(f"Column '{c}' not found")

    sub = df[all_cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 20:
        raise ValueError(f"Need at least 20 valid rows, got {len(sub)}")

    y = sub[dependent]
    endog = sub[endogenous]
    instr = sub[instruments]
    exog_df = sub[exog] if exog else None

    try:
        if exog_df is not None and len(exog_df.columns) > 0:
            model = IV2SLS(y, exog_df, endog, instr)
        else:
            model = IV2SLS(y, None, endog, instr)
        result = model.fit(cov_type="robust")
    except Exception as e:
        raise ValueError(f"IV estimation failed: {e}")

    # Coefficients
    params = result.params
    std_errs = result.std_errors
    tstats = result.tstats
    pvalues = result.pvalues
    ci = result.conf_int()

    coefficients = []
    for var in params.index:
        coefficients.append({
            "variable": str(var),
            "coef": _py(params[var]),
            "std_err": _py(std_errs[var]),
            "t_stat": _py(tstats[var], 4),
            "p_value": _py(pvalues[var]),
            "ci_lower": _py(ci.loc[var, "lower"]),
            "ci_upper": _py(ci.loc[var, "upper"]),
            "significance": _sig(pvalues[var]),
        })

    # First-stage diagnostics
    diagnostics = {}
    try:
        # For single endogenous: first-stage F-stat
        if len(endogenous) == 1:
            fs = result.first_stage
            diagnostics["first_stage_f_stat"] = _py(fs.f_statistic.stat, 4)
            diagnostics["first_stage_f_pvalue"] = _py(fs.f_statistic.pval)
            diagnostics["weak_instruments"] = bool(fs.f_statistic.stat < 10)
    except Exception:
        pass

    # Sargan / J-stat (overid test)
    try:
        diag = result.sargan
        diagnostics["sargan_stat"] = _py(diag.stat, 4)
        diagnostics["sargan_pvalue"] = _py(diag.pval)
        diagnostics["overid_valid"] = bool(diag.pval > 0.05)
    except Exception:
        diagnostics["sargan_stat"] = None

    # Wu-Hausman (endogeneity test)
    try:
        wu = result.wooldridge_regression
        diagnostics["wooldridge_stat"] = _py(wu.stat, 4)
        diagnostics["wooldridge_pvalue"] = _py(wu.pval)
    except Exception:
        pass

    return {
        "n_obs": int(result.nobs),
        "dependent": dependent,
        "endogenous": endogenous,
        "instruments": instruments,
        "exogenous": exog or [],
        "coefficients": coefficients,
        "r_squared": _py(result.rsquared),
        "diagnostics": diagnostics,
        "interpretation": {
            "weak_instrument_note": (
                "⚠ Weak instruments detected (first-stage F < 10)"
                if diagnostics.get("weak_instruments") else
                "✓ First-stage F-stat suggests strong instruments"
            ),
        },
    }


def _sig(p):
    if p is None:
        return ""
    if p < 0.001: return "***"
    if p < 0.01: return "**"
    if p < 0.05: return "*"
    if p < 0.1: return "."
    return ""


# ============================================================
# Difference-in-Differences
# ============================================================
def diff_in_diff(df, outcome, treatment_col, time_col, post_period=None):
    """Two-way DiD: Y = α + β1·Treated + β2·Post + β3·(Treated×Post) + ε."""
    for c in [outcome, treatment_col, time_col]:
        if c not in df.columns:
            raise ValueError(f"Column '{c}' not found")

    sub = df[[outcome, treatment_col, time_col]].copy()
    sub[outcome] = pd.to_numeric(sub[outcome], errors="coerce")
    sub = sub.dropna(subset=[outcome])

    # Coerce treatment to 0/1
    uniq_t = sorted(sub[treatment_col].dropna().unique().tolist())
    if len(uniq_t) != 2:
        raise ValueError(f"Treatment column must have exactly 2 values, got {len(uniq_t)}")
    sub["treated"] = (sub[treatment_col] == uniq_t[1]).astype(int)

    # Determine post from time column
    sub[time_col] = pd.to_datetime(sub[time_col], errors="coerce")
    sub = sub.dropna(subset=[time_col])

    unique_times = sorted(sub[time_col].unique())
    if len(unique_times) < 2:
        raise ValueError("Time column needs at least 2 distinct periods")

    if post_period is None:
        median_time = unique_times[len(unique_times) // 2]
        post_period = median_time

    post_ts = pd.to_datetime(post_period)
    sub["post"] = (sub[time_col] >= post_ts).astype(int)

    # Interaction
    sub["interaction"] = sub["treated"] * sub["post"]

    # Regression
    X = sm.add_constant(sub[["treated", "post", "interaction"]])
    y = sub[outcome]
    try:
        model = sm.OLS(y, X).fit(cov_type="HC3")
    except Exception as e:
        raise ValueError(f"DiD regression failed: {e}")

    coefs = []
    for var in model.params.index:
        coefs.append({
            "variable": str(var),
            "coef": _py(model.params[var]),
            "std_err": _py(model.bse[var]),
            "t_stat": _py(model.tvalues[var], 4),
            "p_value": _py(model.pvalues[var]),
            "ci_lower": _py(model.conf_int().loc[var, 0]),
            "ci_upper": _py(model.conf_int().loc[var, 1]),
            "significance": _sig(model.pvalues[var]),
        })

    # Group means (2x2 table)
    group_means = {}
    for t_val in [0, 1]:
        for p_val in [0, 1]:
            key = ("Treated" if t_val else "Control") + "_" + ("Post" if p_val else "Pre")
            vals = sub[(sub["treated"] == t_val) & (sub["post"] == p_val)][outcome]
            group_means[key] = _py(vals.mean()) if len(vals) else None

    did_effect = None
    try:
        treat_post = group_means.get("Treated_Post")
        treat_pre = group_means.get("Treated_Pre")
        ctrl_post = group_means.get("Control_Post")
        ctrl_pre = group_means.get("Control_Pre")
        if all(v is not None for v in [treat_post, treat_pre, ctrl_post, ctrl_pre]):
            did_effect = round((treat_post - treat_pre) - (ctrl_post - ctrl_pre), 6)
    except Exception:
        pass

    return {
        "n_obs": int(model.nobs),
        "outcome": outcome,
        "treatment_col": treatment_col,
        "time_col": time_col,
        "treatment_values": [str(u) for u in uniq_t],
        "post_threshold": str(post_ts.date()),
        "group_means": group_means,
        "did_effect": did_effect,
        "coefficients": coefs,
        "r_squared": _py(model.rsquared),
        "interpretation": {
            "did_note": (
                f"DiD estimate (interaction term) = {coefs[3]['coef']} "
                f"({'significant' if coefs[3]['p_value'] is not None and coefs[3]['p_value'] < 0.05 else 'not significant'})"
            ),
        },
    }


# ============================================================
# Cointegration (Johansen)
# ============================================================
def johansen_test(df, variables, det_order=0, k_ar_diff=1):
    """Johansen cointegration test."""
    if not variables or len(variables) < 2:
        raise ValueError("Need at least 2 variables for cointegration")

    for v in variables:
        if v not in df.columns:
            raise ValueError(f"Column '{v}' not found")

    sub = df[variables].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 30:
        raise ValueError(f"Need at least 30 rows, got {len(sub)}")

    data = sub.to_numpy(dtype=float)

    try:
        result = coint_johansen(data, det_order=det_order, k_ar_diff=k_ar_diff)
    except Exception as e:
        raise ValueError(f"Johansen test failed: {e}")

    # Trace statistic
    trace_stat = result.lr1  # r=0, r<=1, ...
    trace_crit = result.cvt  # critical values (90%, 95%, 99%)
    maxeig_stat = result.lr2
    maxeig_crit = result.cvm

    n = len(variables)
    trace_results = []
    maxeig_results = []

    for i in range(n):
        trace_results.append({
            "H0": f"r <= {i}",
            "trace_stat": _py(trace_stat[i], 4),
            "crit_90": _py(trace_crit[i, 0], 4),
            "crit_95": _py(trace_crit[i, 1], 4),
            "crit_99": _py(trace_crit[i, 2], 4),
            "reject_5pct": bool(trace_stat[i] > trace_crit[i, 1]),
        })
        maxeig_results.append({
            "H0": f"r <= {i}",
            "maxeig_stat": _py(maxeig_stat[i], 4),
            "crit_90": _py(maxeig_crit[i, 0], 4),
            "crit_95": _py(maxeig_crit[i, 1], 4),
            "crit_99": _py(maxeig_crit[i, 2], 4),
            "reject_5pct": bool(maxeig_stat[i] > maxeig_crit[i, 1]),
        })

    # Determine cointegration rank (at 95%)
    rank = 0
    for i, r in enumerate(trace_results):
        if r["reject_5pct"]:
            rank = i + 1
        else:
            break

    # Eigenvectors (first rank rows)
    eigenvectors = result.evec[:, :max(1, rank)]
    eigvec_list = []
    for j in range(eigenvectors.shape[1]):
        vec = eigenvectors[:, j]
        eigvec_list.append({
            "rank": j + 1,
            "weights": {v: _py(vec[i]) for i, v in enumerate(variables)},
        })

    return {
        "n_obs": int(len(sub)),
        "variables": variables,
        "det_order": det_order,
        "k_ar_diff": k_ar_diff,
        "trace_results": trace_results,
        "maxeig_results": maxeig_results,
        "cointegration_rank": int(rank),
        "eigenvectors": eigvec_list,
        "interpretation": {
            "cointegration_note": (
                f"Found {rank} cointegrating relationship(s) at 5% level"
                if rank > 0
                else "No cointegration detected at 5% level"
            ),
        },
    }


def vecm_fit(df, variables, coint_rank, k_ar_diff=1, deterministic="ci"):
    """VECM (Vector Error Correction Model) - requires cointegration."""
    for v in variables:
        if v not in df.columns:
            raise ValueError(f"Column '{v}' not found")

    sub = df[variables].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 30:
        raise ValueError("Need at least 30 rows")

    data = sub.to_numpy(dtype=float)

    try:
        model = VECM(data, k_ar_diff=k_ar_diff, coint_rank=coint_rank, deterministic=deterministic)
        result = model.fit()
    except Exception as e:
        raise ValueError(f"VECM failed: {e}")

    # Coefficients
    params = result.params
    alpha = params[:len(variables) * coint_rank]

    return {
        "n_obs": int(len(sub)),
        "variables": variables,
        "coint_rank": coint_rank,
        "k_ar_diff": k_ar_diff,
        "alpha": [_py(x) for x in alpha.tolist()],
        "log_likelihood": _py(result.llf, 4),
        "aic": _py(result.aic, 4),
        "bic": _py(result.bic, 4),
        "hqic": _py(result.hqic, 4),
    }
