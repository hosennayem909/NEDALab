"""Panel data regression: Fixed Effects, Random Effects, Pooled OLS + diagnostics."""
import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS, RandomEffects, PooledOLS
from scipy import stats


def _sf(v, d=6):
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, d)
    except (TypeError, ValueError):
        return None


def _prep_panel(df, entity_col, time_col, dep, indep):
    """Prepare MultiIndex DataFrame for panel models."""
    cols = [entity_col, time_col, dep] + indep
    for c in cols:
        if c not in df.columns:
            raise ValueError(f"Column '{c}' not found")

    sub = df[cols].copy()
    sub[time_col] = pd.to_datetime(sub[time_col], errors="coerce")
    sub = sub.dropna(subset=[time_col])

    for c in [dep] + indep:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub = sub.dropna()

    if len(sub) < (len(indep) + 2) * 5:
        raise ValueError(f"Need at least {(len(indep) + 2) * 5} valid rows, got {len(sub)}")

    n_entities = sub[entity_col].nunique()
    n_periods = sub[time_col].nunique()
    if n_entities < 2:
        raise ValueError(f"Need at least 2 unique entities in '{entity_col}', got {n_entities}")
    if n_periods < 2:
        raise ValueError(f"Need at least 2 unique periods in '{time_col}', got {n_periods}")

    sub = sub.set_index([entity_col, time_col])
    return sub, n_entities, n_periods


def train_panel(df, entity_col, time_col, dep, indep, model_type="fixed"):
    """Panel regression: fixed / random / pooled."""
    sub, n_entities, n_periods = _prep_panel(df, entity_col, time_col, dep, indep)

    y = sub[dep]
    X = sub[indep]

    try:
        if model_type == "fixed":
            model = PanelOLS(y, X, entity_effects=True, time_effects=False)
            fit_kwargs = {"cov_type": "clustered", "cluster_entity": True}
        elif model_type == "random":
            model = RandomEffects(y, X)
            fit_kwargs = {"cov_type": "clustered", "cluster_entity": True}
        elif model_type == "pooled":
            model = PooledOLS(y, X)
            fit_kwargs = {"cov_type": "clustered", "cluster_entity": True}
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

        result = model.fit(**fit_kwargs)
    except Exception as e:
        raise ValueError(f"Panel estimation failed: {e}")

    coeffs = []
    for var in result.params.index:
        p = result.pvalues[var]
        p_val = _sf(p, 6) or 1.0
        coeffs.append({
            "variable": str(var),
            "coef": _sf(result.params[var], 6),
            "std_err": _sf(result.std_errors[var], 6),
            "t_stat": _sf(result.tstats[var], 4),
            "p_value": p_val,
            "ci_lower": _sf(result.conf_int().loc[var, "lower"], 6),
            "ci_upper": _sf(result.conf_int().loc[var, "upper"], 6),
            "significance": "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "." if p_val < 0.1 else "",
        })

    metrics = {
        "n_obs": int(result.nobs),
        "n_entities": int(n_entities),
        "n_periods": int(n_periods),
        "r_squared": _sf(result.rsquared, 6),
        "r_squared_within": _sf(getattr(result, "rsquared_within", None), 6),
        "r_squared_between": _sf(getattr(result, "rsquared_between", None), 6),
        "r_squared_overall": _sf(getattr(result, "rsquared_overall", None), 6),
        "f_statistic": None,
        "f_pvalue": None,
    }

    try:
        fstat = result.f_statistic
        if fstat is not None:
            metrics["f_statistic"] = _sf(fstat.stat, 4)
            metrics["f_pvalue"] = _sf(fstat.pval, 6)
    except Exception:
        pass

    return {
        "coefficients": coeffs,
        "metrics": metrics,
        "model_type": model_type,
    }


def hausman_test(df, entity_col, time_col, dep, indep):
    """Hausman test: FE vs RE. H0: RE is consistent (prefer RE)."""
    try:
        fe_result = train_panel(df, entity_col, time_col, dep, indep, "fixed")
        re_result = train_panel(df, entity_col, time_col, dep, indep, "random")
    except ValueError as e:
        raise ValueError(str(e))

    fe_coefs = {c["variable"]: c for c in fe_result["coefficients"]}
    re_coefs = {c["variable"]: c for c in re_result["coefficients"]}

    common = [v for v in fe_coefs.keys() if v in re_coefs.keys()]
    if not common:
        raise ValueError("No common coefficients between FE and RE")

    b_diff = []
    var_diff = []
    for v in common:
        b_fe = fe_coefs[v]["coef"]
        b_re = re_coefs[v]["coef"]
        se_fe = fe_coefs[v]["std_err"]
        se_re = re_coefs[v]["std_err"]
        if b_fe is None or b_re is None or se_fe is None or se_re is None:
            continue
        b_diff.append(b_fe - b_re)
        var_diff.append(max(se_fe**2 - se_re**2, 1e-12))

    if not b_diff:
        raise ValueError("Could not compute Hausman statistic")

    b_arr = np.array(b_diff)
    v_arr = np.array(var_diff)
    chi2 = float(np.sum(b_arr**2 / v_arr))
    df_h = len(b_diff)

    try:
        p_value = float(1 - stats.chi2.cdf(chi2, df_h))
    except Exception:
        p_value = None

    if p_value is None:
        recommendation = "unknown"
        interpretation = "Could not compute p-value"
    elif p_value < 0.05:
        recommendation = "fixed"
        interpretation = "Reject H0 — Fixed Effects preferred (consistent under both)"
    else:
        recommendation = "random"
        interpretation = "Fail to reject H0 — Random Effects preferred (more efficient)"

    return {
        "chi2_statistic": round(chi2, 4),
        "df": df_h,
        "p_value": round(p_value, 6) if p_value is not None else None,
        "recommendation": recommendation,
        "interpretation": interpretation,
        "common_coefficients": common,
    }


# ============================================================
# NEW: F-test for Poolability (Pooled OLS vs Fixed Effects)
# ============================================================
def ftest_poolability(df, entity_col, time_col, dep, indep):
    """
    F-test for poolability.
    H0: Pooled OLS is adequate (all entity effects are zero).
    If p < 0.05 → reject Pooled OLS → Fixed Effects preferred.
    """
    try:
        pooled = train_panel(df, entity_col, time_col, dep, indep, "pooled")
        fe = train_panel(df, entity_col, time_col, dep, indep, "fixed")
    except ValueError as e:
        raise ValueError(str(e))

    n = pooled["metrics"]["n_obs"]
    N = fe["metrics"]["n_entities"]
    K = len(indep)

    r2_pooled = pooled["metrics"].get("r_squared") or 0.0
    r2_fe = fe["metrics"].get("r_squared") or 0.0

    df_num = N - 1
    df_den = n - N - K

    if df_den <= 0:
        raise ValueError("Not enough observations for F-test (df_den <= 0)")

    # F-statistic formula
    numerator = max(r2_fe - r2_pooled, 0.0) / df_num
    denominator = max(1 - r2_fe, 1e-12) / df_den
    f_stat = numerator / denominator

    try:
        p_value = float(1 - stats.f.cdf(f_stat, df_num, df_den))
    except Exception:
        p_value = None

    if p_value is not None and p_value < 0.05:
        recommendation = "fixed"
        interpretation = "Reject H0 — Fixed Effects preferred over Pooled OLS (significant entity effects)"
    else:
        recommendation = "pooled"
        interpretation = "Fail to reject H0 — Pooled OLS is adequate (no significant entity effects)"

    return {
        "test": "F-test for Poolability",
        "f_statistic": round(f_stat, 4),
        "df_num": int(df_num),
        "df_den": int(df_den),
        "p_value": round(p_value, 6) if p_value is not None else None,
        "r_squared_pooled": r2_pooled,
        "r_squared_fe": r2_fe,
        "recommendation": recommendation,
        "interpretation": interpretation,
    }


# ============================================================
# NEW: Breusch-Pagan LM Test (Pooled OLS vs Random Effects)
# ============================================================
def breusch_pagan_lm(df, entity_col, time_col, dep, indep):
    """
    Breusch-Pagan LM test for random effects.
    H0: No random effects (sigma_u^2 = 0) → Pooled OLS adequate.
    If p < 0.05 → reject Pooled OLS → Random Effects preferred.
    """
    sub, N, T = _prep_panel(df, entity_col, time_col, dep, indep)

    y = sub[dep]
    X = sub[indep]

    # Fit pooled OLS
    try:
        pooled_model = PooledOLS(y, X)
        pooled_result = pooled_model.fit()
    except Exception as e:
        raise ValueError(f"Pooled OLS failed for BP-LM: {e}")

    resid = pooled_result.resids  # Series indexed by (entity, time)

    # Group residuals by entity
    entity_index = resid.index.get_level_values(0)
    resid_df = pd.DataFrame({"resid": resid.values, "entity": entity_index.values})

    # Sum of residuals per entity
    grouped = resid_df.groupby("entity")["resid"]
    sum_per_entity = grouped.sum()
    n_obs_per_entity = grouped.count()

    sum_sq_resid = float((resid_df["resid"] ** 2).sum())

    if sum_sq_resid <= 0:
        raise ValueError("Residual sum of squares is zero — cannot compute BP-LM")

    # BP-LM formula (balanced panels); we use a robust unbalanced variant
    # LM = (N*T / (2*(T-1))) * [ (sum_i (sum_t e_it)^2) / (sum_i sum_t e_it^2) - 1 ]^2
    # For unbalanced, use total n = sum(n_i)
    n_total = int(n_obs_per_entity.sum())
    if n_total <= N:
        raise ValueError("Not enough observations for BP-LM test")

    numerator = float((sum_per_entity ** 2).sum())
    ratio = numerator / sum_sq_resid - 1.0

    # Use average T for the multiplier (robust approximation)
    T_avg = n_total / N
    if T_avg <= 1:
        raise ValueError("Average periods per entity must be > 1 for BP-LM")

    lm_stat = (n_total * T_avg / (2.0 * (T_avg - 1.0))) * (ratio ** 2)
    # Simpler & common form: LM = (n*T)/(2*(T-1)) * ratio^2 — we use balanced form:
    lm_stat_alt = (n_total * T_avg / (2.0 * (T_avg - 1.0))) * (ratio ** 2)

    # Use the standard balanced form with T = average
    lm_stat_final = lm_stat_alt

    try:
        p_value = float(1 - stats.chi2.cdf(lm_stat_final, 1))
    except Exception:
        p_value = None

    if p_value is not None and p_value < 0.05:
        recommendation = "random"
        interpretation = "Reject H0 — Random Effects preferred (significant variance across entities)"
    else:
        recommendation = "pooled"
        interpretation = "Fail to reject H0 — Pooled OLS is adequate (no significant random effects)"

    return {
        "test": "Breusch-Pagan LM Test for Random Effects",
        "lm_statistic": round(lm_stat_final, 4),
        "df": 1,
        "p_value": round(p_value, 6) if p_value is not None else None,
        "n_entities": int(N),
        "n_periods": int(T),
        "n_obs": n_total,
        "recommendation": recommendation,
        "interpretation": interpretation,
    }