"""OLS regression engine using statsmodels with advanced diagnostics."""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import (
    het_breuschpagan,
    acorr_breusch_godfrey,
)
from statsmodels.stats.stattools import durbin_watson
from statsmodels.stats.outliers_influence import variance_inflation_factor


def _py(v):
    """Convert numpy types to native Python types for JSON."""
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
        return f
    if isinstance(v, np.ndarray):
        return [_py(x) for x in v.tolist()]
    if isinstance(v, (list, tuple)):
        return [_py(x) for x in v]
    if isinstance(v, dict):
        return {k: _py(val) for k, val in v.items()}
    if isinstance(v, float):
        if np.isnan(v) or np.isinf(v):
            return None
    return v


def _safe_float(v, decimals=6):
    """Convert to float and round, handling None/NaN."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return round(f, decimals)


def _sig(p: float) -> str:
    if p is None:
        return ""
    if p < 0.001: return "***"
    if p < 0.01: return "**"
    if p < 0.05: return "*"
    if p < 0.1: return "."
    return ""


def _compute_vif(X: pd.DataFrame) -> list:
    """Compute VIF for each independent variable (excluding const)."""
    vif_data = []
    try:
        # VIF only works on numeric columns; skip constant
        cols_no_const = [c for c in X.columns if c != "const"]
        if len(cols_no_const) < 2:
            # VIF is only meaningful with 2+ predictors
            for c in cols_no_const:
                vif_data.append({"variable": str(c), "vif": None, "warning": None})
            return vif_data

        X_vif = X[cols_no_const].astype(float)
        for i, col in enumerate(X_vif.columns):
            try:
                vif_val = float(variance_inflation_factor(X_vif.values, i))
                if np.isnan(vif_val) or np.isinf(vif_val):
                    vif_val = None
                warning = None
                if vif_val is not None:
                    if vif_val > 10:
                        warning = "Severe multicollinearity"
                    elif vif_val > 5:
                        warning = "Moderate multicollinearity"
                vif_data.append({
                    "variable": str(col),
                    "vif": _safe_float(vif_val, 4),
                    "warning": warning,
                })
            except Exception:
                vif_data.append({"variable": str(col), "vif": None, "warning": None})
    except Exception:
        pass
    return vif_data


def _robust_se_table(model, X: pd.DataFrame, y: pd.Series) -> list:
    """Compute HC1-robust standard errors for coefficients."""
    try:
        robust = model.get_robustcov_results(cov_type="HC1")
        rows = []
        for i, var in enumerate(model.params.index):
            p_val = _safe_float(robust.pvalues[i], 6) if robust.pvalues is not None else None
            rows.append({
                "variable": str(var),
                "robust_std_err": _safe_float(robust.bse[i], 6),
                "robust_t_stat": _safe_float(robust.tvalues[i], 4),
                "robust_p_value": p_val if p_val is not None else None,
                "robust_significance": _sig(p_val),
            })
        return rows
    except Exception:
        return []


def train_ols(df: pd.DataFrame, dep: str, indep: list, add_constant: bool = True) -> dict:
    """Run OLS regression with advanced econometric diagnostics."""
    if dep not in df.columns:
        raise ValueError(f"Dependent variable '{dep}' not found")
    for v in indep:
        if v not in df.columns:
            raise ValueError(f"Independent variable '{v}' not found")

    cols = [dep] + indep
    sub = df[cols].apply(pd.to_numeric, errors="coerce").dropna()

    if len(sub) < len(indep) + 2:
        raise ValueError(f"Need at least {len(indep) + 2} rows after removing NaN, got {len(sub)}")

    y = sub[dep].astype(float)
    X = sub[indep].astype(float)
    if add_constant:
        X = sm.add_constant(X, has_constant="add")

    try:
        model = sm.OLS(y, X).fit()
    except Exception as e:
        raise ValueError(f"OLS failed: {e}")

    # ============ Standard Coefficients ============
    coeffs = []
    for var in model.params.index:
        p_val = _safe_float(model.pvalues[var], 6)
        coeffs.append({
            "variable": str(var),
            "coef": _safe_float(model.params[var], 6),
            "std_err": _safe_float(model.bse[var], 6),
            "t_stat": _safe_float(model.tvalues[var], 4),
            "p_value": p_val if p_val is not None else 1.0,
            "ci_lower": _safe_float(model.conf_int().loc[var, 0], 6),
            "ci_upper": _safe_float(model.conf_int().loc[var, 1], 6),
            "significance": _sig(p_val),
        })

    # ============ Robust Standard Errors (HC1) ============
    robust_se = _robust_se_table(model, X, y)

    # ============ Residual Diagnostics ============
    resid = np.asarray(model.resid, dtype=float)

    # Jarque-Bera (Normality)
    jb_stat = jb_p = jb_skew = jb_kurt = None
    try:
        jb = sm.stats.stattools.jarque_bera(resid)
        jb_stat = _safe_float(jb[0], 4)
        jb_p = _safe_float(jb[1], 6)
        jb_skew = _safe_float(jb[2], 4)
        jb_kurt = _safe_float(jb[3], 4)
    except Exception:
        pass

    # Breusch-Pagan (Heteroskedasticity)
    bp_lm = bp_lm_p = bp_f = bp_f_p = None
    try:
        bp = het_breuschpagan(resid, model.model.exog)
        bp_lm = _safe_float(bp[0], 4)
        bp_lm_p = _safe_float(bp[1], 6)
        bp_f = _safe_float(bp[2], 4)
        bp_f_p = _safe_float(bp[3], 6)
    except Exception:
        pass

    # Breusch-Godfrey (Autocorrelation) - default lags=1
    bg_lm = bg_lm_p = bg_f = bg_f_p = None
    try:
        bg = acorr_breusch_godfrey(model, nlags=1)
        bg_lm = _safe_float(bg[0], 4)
        bg_lm_p = _safe_float(bg[1], 6)
        bg_f = _safe_float(bg[2], 4)
        bg_f_p = _safe_float(bg[3], 6)
    except Exception:
        pass

    # Durbin-Watson
    dw = None
    try:
        dw = _safe_float(durbin_watson(resid), 4)
    except Exception:
        pass

    # VIF (Multicollinearity)
    vif_data = _compute_vif(X)

    # Flags
    is_normal = bool(jb_p > 0.05) if jb_p is not None else None
    is_homosced = bool(bp_lm_p > 0.05) if bp_lm_p is not None else None
    no_autocorr_bg = bool(bg_lm_p > 0.05) if bg_lm_p is not None else None

    # Find high VIF variables
    high_vif = [v["variable"] for v in vif_data if v.get("vif") is not None and v["vif"] > 10]

    residual_stats = {
        "mean": _safe_float(np.mean(resid), 6),
        "std": _safe_float(np.std(resid, ddof=1), 6),
        "skewness": jb_skew,
        "kurtosis": jb_kurt,
        "jarque_bera_stat": jb_stat,
        "jarque_bera_p": jb_p,
        "is_normal_resid": is_normal,
        "bp_lm_stat": bp_lm,
        "bp_lm_p": bp_lm_p,
        "bp_f_stat": bp_f,
        "bp_f_p": bp_f_p,
        "is_homoscedastic": is_homosced,
        "bg_lm_stat": bg_lm,
        "bg_lm_p": bg_lm_p,
        "bg_f_stat": bg_f,
        "bg_f_p": bg_f_p,
        "no_autocorrelation_bg": no_autocorr_bg,
        "durbin_watson": dw,
        "vif": vif_data,
        "high_vif_variables": high_vif,
    }

    r2 = _safe_float(model.rsquared, 6) or 0.0
    f_p = _safe_float(model.f_pvalue, 8)

    interpretation = {
        "r_squared_note": _interpret_r2(r2),
        "f_test_note": (
            "Model is significant (F p-value < 0.05)"
            if f_p is not None and f_p < 0.05
            else "Model is NOT significant (F p-value > 0.05)"
        ),
        "normality_note": (
            "Residuals are normally distributed (Jarque-Bera p > 0.05)"
            if is_normal is True
            else "Residuals are NOT normally distributed"
        ),
        "heteroskedasticity_note": (
            "Homoscedastic (constant variance)"
            if is_homosced is True
            else "Heteroskedastic — consider robust standard errors (HC1)"
        ),
        "autocorrelation_note": _interpret_dw(dw),
        "breusch_godfrey_note": (
            "No autocorrelation detected (BG p > 0.05)"
            if no_autocorr_bg is True
            else "Autocorrelation detected (BG p < 0.05)"
        ),
        "multicollinearity_note": (
            f"Severe multicollinearity detected in: {', '.join(high_vif)} (VIF > 10)"
            if high_vif
            else "No severe multicollinearity (all VIF < 10)"
        ),
        "significant_vars": [
            c["variable"] for c in coeffs
            if c["p_value"] is not None and c["p_value"] < 0.05 and c["variable"] != "const"
        ],
        "significant_vars_robust": [
            r["variable"] for r in robust_se
            if r.get("robust_p_value") is not None
            and r["robust_p_value"] < 0.05
            and r["variable"] != "const"
        ],
    }

    metrics = {
        "n_obs": int(model.nobs),
        "k_params": int(len(model.params)),
        "df_resid": int(model.df_resid),
        "r_squared": r2,
        "adj_r_squared": _safe_float(model.rsquared_adj, 6) or 0.0,
        "f_statistic": _safe_float(model.fvalue, 4) or 0.0,
        "f_pvalue": f_p if f_p is not None else 1.0,
        "aic": _safe_float(model.aic, 4) or 0.0,
        "bic": _safe_float(model.bic, 4) or 0.0,
        "log_likelihood": _safe_float(model.llf, 4) or 0.0,
    }

    return {
        "coefficients": coeffs,
        "robust_se": robust_se,
        "metrics": metrics,
        "residual_stats": residual_stats,
        "interpretation": interpretation,
        "n_obs": int(model.nobs),
    }


def _interpret_r2(r2: float) -> str:
    if r2 >= 0.9: return "Excellent fit"
    if r2 >= 0.7: return "Good fit"
    if r2 >= 0.5: return "Moderate fit"
    if r2 >= 0.3: return "Weak fit"
    return "Poor fit"


def _interpret_dw(dw) -> str:
    if dw is None: return "Not available"
    if dw < 1.5: return "Positive autocorrelation (DW < 1.5)"
    if dw > 2.5: return "Negative autocorrelation (DW > 2.5)"
    return "No significant autocorrelation (1.5 <= DW <= 2.5)"