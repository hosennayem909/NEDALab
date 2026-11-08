import numpy as np
import pandas as pd


def _prepare_series(df: pd.DataFrame, target_column: str) -> np.ndarray:
    if target_column not in df.columns:
        raise ValueError(f"Column '{target_column}' not found in dataset")
    series = pd.to_numeric(df[target_column], errors="coerce").dropna().reset_index(drop=True)
    if len(series) < 10:
        raise ValueError("Not enough numeric data points (min 10 required)")
    return series.to_numpy(dtype=float)


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    mask = y_true != 0
    mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100) if mask.any() else None
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 4) if mape is not None else None,
    }


# ---- Trainers ----

def train_linear(series):
    n = len(series)
    x = np.arange(n, dtype=float)
    a, b = np.polyfit(x, series, 1)
    y_pred = a * x + b
    return {"slope": float(a), "intercept": float(b)}, _metrics(series, y_pred), y_pred


def train_moving_average(series, window=3):
    n = len(series)
    y_pred = np.zeros(n)
    for i in range(n):
        start = max(0, i - window)
        y_pred[i] = float(np.mean(series[start:i])) if i > 0 else series[i]
    return {"window": window}, _metrics(series, y_pred), y_pred


def train_arima(series):
    from statsmodels.tsa.arima.model import ARIMA
    order = (1, 1, 1)
    model = ARIMA(series, order=order)
    fit = model.fit()
    y_pred = np.asarray(fit.fittedvalues, dtype=float)
    return {"order": list(order)}, _metrics(series, y_pred), y_pred


def train_polynomial(series, degree=2):
    n = len(series)
    x = np.arange(n, dtype=float)
    coeffs = np.polyfit(x, series, degree)
    y_pred = np.polyval(coeffs, x)
    return {
        "degree": degree,
        "coefficients": [float(c) for c in coeffs],
    }, _metrics(series, y_pred), y_pred


def train_exponential_smoothing(series, alpha=0.3):
    n = len(series)
    y_pred = np.zeros(n)
    y_pred[0] = series[0]
    for i in range(1, n):
        y_pred[i] = alpha * series[i - 1] + (1 - alpha) * y_pred[i - 1]
    return {"alpha": alpha}, _metrics(series, y_pred), y_pred


def train_model(series, model_type):
    if model_type == "linear":
        return train_linear(series)
    if model_type == "moving_average":
        return train_moving_average(series)
    if model_type == "arima":
        return train_arima(series)
    if model_type == "polynomial":
        return train_polynomial(series)
    if model_type == "exponential_smoothing":
        return train_exponential_smoothing(series)
    raise ValueError(f"Unknown model type: {model_type}")


# ---- Future prediction ----

def predict_future(series, model_type, params, horizon):
    if model_type == "linear":
        a = params["slope"]; b = params["intercept"]; n = len(series)
        return [round(float(a * (n + i) + b), 4) for i in range(horizon)]

    if model_type == "moving_average":
        window = params["window"]; history = list(series.astype(float)); preds = []
        for _ in range(horizon):
            nxt = float(np.mean(history[-window:]))
            preds.append(round(nxt, 4)); history.append(nxt)
        return preds

    if model_type == "arima":
        from statsmodels.tsa.arima.model import ARIMA
        order = tuple(params["order"])
        model = ARIMA(series, order=order); fit = model.fit()
        forecast = fit.forecast(steps=horizon)
        return [round(float(v), 4) for v in forecast]

    if model_type == "polynomial":
        degree = params["degree"]
        coeffs = np.array(params["coefficients"])
        n = len(series)
        return [round(float(np.polyval(coeffs, n + i)), 4) for i in range(horizon)]

    if model_type == "exponential_smoothing":
        alpha = params["alpha"]
        s = float(series[0])
        for v in series[1:]:
            s = alpha * float(v) + (1 - alpha) * s
        return [round(s, 4)] * horizon

    raise ValueError(f"Unknown model type: {model_type}")
