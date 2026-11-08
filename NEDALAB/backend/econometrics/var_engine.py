"""VAR: Vector Autoregression with IRF and FEVD."""
import numpy as np
import pandas as pd
from statsmodels.tsa.api import VAR
from statsmodels.tsa.stattools import adfuller


def _sf(v, d=6):
    """Safe float conversion — NaN/Inf/array → None or float."""
    try:
        if v is None:
            return None
        # Handle numpy arrays and pandas objects
        if isinstance(v, (list, tuple, np.ndarray)):
            if len(v) == 0:
                return None
            v = v[0] if len(v) == 1 else v
            if isinstance(v, np.ndarray):
                v = v.item() if v.size == 1 else None
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, d)
    except (TypeError, ValueError, AttributeError):
        return None


def _select_lag(data, maxlags=10):
    """Auto-select optimal lag via AIC/BIC/HQIC/FPE."""
    try:
        model = VAR(data)
        result = model.select_order(maxlags=maxlags)
        aic = result.aic
        bic = result.bic
        hqic = result.hqic
        fpe = result.fpe
        return {
            "aic": int(aic) if aic is not None else None,
            "bic": int(bic) if bic is not None else None,
            "hqic": int(hqic) if hqic is not None else None,
            "fpe": int(fpe) if fpe is not None else None,
        }
    except Exception:
        return {"aic": 1, "bic": 1, "hqic": 1, "fpe": 1}


def train_var(df, variables, max_lags=5, lag_order=None):
    """Fit VAR model with diagnostics."""
    if len(variables) < 2:
        raise ValueError("VAR needs at least 2 variables")

    for v in variables:
        if v not in df.columns:
            raise ValueError(f"Column '{v}' not found")

    sub = df[variables].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < max_lags * 3 + 10:
        raise ValueError(
            f"Need at least {max_lags * 3 + 10} valid rows, got {len(sub)}"
        )

    data = sub.to_numpy(dtype=float)

    # ---------- Stationarity (ADF per variable) ----------
    stationarity = []
    for i, v in enumerate(variables):
        try:
            adf = adfuller(data[:, i], autolag="AIC")
            stationarity.append({
                "variable": v,
                "adf_stat": _sf(adf[0], 4),
                "p_value": _sf(adf[1], 6),
                "is_stationary": bool(adf[1] < 0.05),
            })
        except Exception:
            stationarity.append({"variable": v, "error": "test failed"})

    # ---------- Fit VAR ----------
    try:
        model = VAR(sub)
    except Exception as e:
        raise ValueError(f"VAR init failed: {e}")

    if lag_order is None:
        lag_order = max_lags
    lag_order = max(1, min(int(lag_order), max_lags))

    try:
        result = model.fit(lag_order)
    except Exception as e:
        raise ValueError(f"VAR fit failed: {e}")

    k_ar = int(result.k_ar)
    n_obs = int(result.nobs)
    n_vars = len(variables)

    # ---------- Coefficients + R² per equation ----------
    equations = []
    for eq_idx, eq_var in enumerate(variables):
        # Params
        try:
            if isinstance(result.params, pd.DataFrame):
                params_s = result.params[eq_var]
            else:
                params_s = pd.Series(result.params)
        except Exception:
            params_s = None

        if params_s is None:
            equations.append({
                "equation": eq_var,
                "params": [],
                "r_squared": None,
                "r_squared_adj": None,
            })
            continue

        # Standard errors
        try:
            if hasattr(result, "stderr"):
                stderr_s = (
                    result.stderr[eq_var]
                    if isinstance(result.stderr, pd.DataFrame)
                    else result.stderr
                )
            else:
                stderr_s = None
        except Exception:
            stderr_s = None

        # t-values
        try:
            tvalues_s = (
                result.tvalues[eq_var]
                if isinstance(result.tvalues, pd.DataFrame)
                else result.tvalues
            )
        except Exception:
            tvalues_s = None

        # p-values
        try:
            pvalues_s = (
                result.pvalues[eq_var]
                if isinstance(result.pvalues, pd.DataFrame)
                else result.pvalues
            )
        except Exception:
            pvalues_s = None

        # Param list
        params_list = []
        for name in params_s.index:
            coef = params_s.get(name)
            se = (
                stderr_s.get(name)
                if stderr_s is not None and hasattr(stderr_s, "get")
                else None
            )
            tv = (
                tvalues_s.get(name)
                if tvalues_s is not None and hasattr(tvalues_s, "get")
                else None
            )
            pv = (
                pvalues_s.get(name)
                if pvalues_s is not None and hasattr(pvalues_s, "get")
                else None
            )

            params_list.append({
                "term": str(name),
                "coef": _sf(coef, 6),
                "std_err": _sf(se, 6),
                "t_stat": _sf(tv, 4),
                "p_value": _sf(pv, 6),
            })

        # ---------- ⭐ R² extraction (ROBUST, 3 methods) ----------
        r2 = None
        r2_adj = None

        # === Method 1: Manual computation from residuals (most reliable) ===
        try:
            # y data for this equation (full)
            endog = np.asarray(result.model.endog)
            if endog.ndim == 2:
                y_full = endog[:, eq_idx]
            else:
                y_full = endog

            # Residuals (length = nobs = T - p)
            resid = result.resid
            if hasattr(resid, "iloc"):
                resid_arr = resid.iloc[:, eq_idx].values
            else:
                resid_arr = np.asarray(resid)
                if resid_arr.ndim == 2:
                    resid_arr = resid_arr[:, eq_idx]

            # Align: drop first p observations (used as initial conditions)
            y_actual = y_full[k_ar:]
            y_mean = float(np.mean(y_actual))
            ss_tot = float(np.sum((y_actual - y_mean) ** 2))
            ss_res = float(np.sum(resid_arr ** 2))

            if ss_tot > 0:
                r2_val = 1.0 - ss_res / ss_tot
                r2 = _sf(r2_val, 6)

                n = len(y_actual)
                k = len(params_s)
                if n - k - 1 > 0:
                    r2_adj = _sf(
                        1.0 - (1.0 - r2_val) * (n - 1) / (n - k - 1),
                        6,
                    )
        except Exception:
            r2 = None
            r2_adj = None

        # === Method 2: Fallback — result.rsquared (numpy array) ===
        if r2 is None:
            try:
                if hasattr(result, "rsquared"):
                    rs = result.rsquared
                    if isinstance(rs, (list, tuple, np.ndarray)):
                        r2 = _sf(float(rs[eq_idx]), 6)
                    elif isinstance(rs, (dict, pd.Series)):
                        r2 = _sf(rs.get(eq_var), 6)
                    else:
                        r2 = _sf(rs, 6)
            except Exception:
                pass

        if r2_adj is None:
            try:
                if hasattr(result, "rsquared_adj"):
                    rs_adj = result.rsquared_adj
                    if isinstance(rs_adj, (list, tuple, np.ndarray)):
                        r2_adj = _sf(float(rs_adj[eq_idx]), 6)
                    elif isinstance(rs_adj, (dict, pd.Series)):
                        r2_adj = _sf(rs_adj.get(eq_var), 6)
                    else:
                        r2_adj = _sf(rs_adj, 6)
            except Exception:
                pass

        # === Method 3: Fallback — result.equations[eq_var] ===
        if r2 is None:
            try:
                if hasattr(result, "equations"):
                    eqs = result.equations
                    if eq_var in eqs:
                        eq_data = eqs[eq_var]
                        if isinstance(eq_data, dict):
                            if "r2" in eq_data:
                                r2 = _sf(eq_data["r2"], 6)
                            if "r2_adj" in eq_data:
                                r2_adj = _sf(eq_data["r2_adj"], 6)
            except Exception:
                pass

        equations.append({
            "equation": eq_var,
            "params": params_list,
            "r_squared": r2,
            "r_squared_adj": r2_adj,
        })

    # ---------- Lag selection info ----------
    lag_info = _select_lag(sub, maxlags=max_lags)

    # ---------- Residual covariance (robust) ----------
    resid_cov = {}
    try:
        # Try multiple attribute names
        rc = None
        if hasattr(result, "sigma_u"):
            rc = result.sigma_u
        elif hasattr(result, "resid_cov"):
            rc = result.resid_cov
        else:
            # Compute manually
            resid = result.resid
            if hasattr(resid, "values"):
                resid = resid.values
            rc = np.cov(np.asarray(resid).T)

        rc = np.asarray(rc)
        for i, v1 in enumerate(variables):
            resid_cov[v1] = {}
            for j, v2 in enumerate(variables):
                try:
                    resid_cov[v1][v2] = _sf(rc[i, j], 6)
                except Exception:
                    resid_cov[v1][v2] = None
    except Exception:
        pass

    return {
        "variables": variables,
        "lag_order": k_ar,
        "n_obs": n_obs,
        "aic": _sf(result.aic, 4),
        "bic": _sf(result.bic, 4),
        "hqic": _sf(result.hqic, 4),
        "lag_selection": lag_info,
        "stationarity": stationarity,
        "equations": equations,
        "resid_cov": resid_cov,
    }


def impulse_response(df, variables, max_lags=5, lag_order=None,
                     periods=10, shock_var=None):
    """Compute IRF."""
    if len(variables) < 2:
        raise ValueError("Need at least 2 variables")

    sub = df[variables].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < max_lags * 3 + 10:
        raise ValueError(f"Too few rows, need at least {max_lags * 3 + 10}")

    model = VAR(sub)
    if lag_order is None:
        lag_order = max_lags
    lag_order = max(1, min(int(lag_order), max_lags))
    result = model.fit(lag_order)

    try:
        irf = result.irf(periods=periods)
    except Exception as e:
        raise ValueError(f"IRF failed: {e}")

    irf_arr = irf.irfs
    periods_axis = list(range(irf_arr.shape[0]))

    results = {}
    for shock_idx, shock_name in enumerate(variables):
        if shock_var and shock_name != shock_var:
            continue
        responses = []
        for resp_idx, resp_name in enumerate(variables):
            values = [float(irf_arr[t, resp_idx, shock_idx]) for t in periods_axis]
            responses.append({
                "response_var": resp_name,
                "values": [_sf(v, 6) for v in values],
            })
        results[shock_name] = responses

    return {
        "variables": variables,
        "lag_order": int(result.k_ar),
        "periods": periods_axis,
        "irf": results,
    }


def fevd(df, variables, max_lags=5, lag_order=None, periods=10):
    """Forecast Error Variance Decomposition."""
    if len(variables) < 2:
        raise ValueError("Need at least 2 variables")

    sub = df[variables].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < max_lags * 3 + 10:
        raise ValueError(f"Too few rows, need at least {max_lags * 3 + 10}")

    model = VAR(sub)
    if lag_order is None:
        lag_order = max_lags
    lag_order = max(1, min(int(lag_order), max_lags))
    result = model.fit(lag_order)

    try:
        f = result.fevd(periods=periods)
    except Exception as e:
        raise ValueError(f"FEVD failed: {e}")

    decomp = f.decomp
    results = []
    for resp_idx, resp_name in enumerate(variables):
        rows = []
        for t in range(decomp.shape[1]):
            row = {"period": t + 1}
            for shock_idx, shock_name in enumerate(variables):
                row[shock_name] = _sf(decomp[resp_idx, t, shock_idx] * 100, 4)
            rows.append(row)
        results.append({"variable": resp_name, "decomposition": rows})

    return {
        "variables": variables,
        "lag_order": int(result.k_ar),
        "periods": list(range(1, periods + 1)),
        "fevd": results,
    }