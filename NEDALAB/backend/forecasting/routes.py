import csv
import io
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from forecasting.models import ForecastModel, Forecast
from forecasting.schemas import TrainIn, ModelOut, PredictIn, PredictOut
from forecasting.engine import _prepare_series, train_model, predict_future
from notifications.service import create_notification

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


def _load_dataset_df(ds: Dataset) -> pd.DataFrame:
    if not ds.cleaned_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Dataset has no cleaned file")
    path = Path(ds.cleaned_path)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cleaned file missing on disk")
    return pd.read_csv(path)


def _check_owner(model: ForecastModel, user: User):
    if user.role != "admin" and model.trained_by != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your model")


@router.post("/train", response_model=ModelOut, status_code=201)
def train(payload: TrainIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = db.query(Dataset).filter(Dataset.id == payload.dataset_id).first()
    if not ds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your dataset")

    df = _load_dataset_df(ds)
    try:
        series = _prepare_series(df, payload.target_column)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    try:
        params, metrics, _ = train_model(series, payload.model_type)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Training failed: {e}")

    name = payload.name or f"{payload.model_type} on {payload.target_column}"
    m = ForecastModel(
        dataset_id=ds.id, name=name,
        model_type=payload.model_type, target_column=payload.target_column,
        params_json=json.dumps(params), metrics_json=json.dumps(metrics),
        trained_by=user.email,
    )
    db.add(m); db.flush()
    create_notification(
        db, user.id, "model_train",
        f"Model trained: {name}",
        f"{payload.model_type} · RMSE {metrics.get('rmse', '—')} · target: {payload.target_column}",
        "/forecast/forecast.html",
        user.email,
    )
    db.commit(); db.refresh(m)
    return m


@router.get("/models", response_model=list[ModelOut])
def list_models(dataset_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(ForecastModel).order_by(ForecastModel.created_at.desc())
    if dataset_id is not None:
        q = q.filter(ForecastModel.dataset_id == dataset_id)
    if user.role != "admin":
        q = q.filter(ForecastModel.trained_by == user.email)
    return q.all()


@router.get("/models/{model_id}", response_model=ModelOut)
def get_model(model_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = db.query(ForecastModel).filter(ForecastModel.id == model_id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    _check_owner(m, user)
    return m


@router.post("/models/{model_id}/predict", response_model=PredictOut)
def predict(model_id: int, payload: PredictIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = db.query(ForecastModel).filter(ForecastModel.id == model_id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    _check_owner(m, user)

    ds = db.query(Dataset).filter(Dataset.id == m.dataset_id).first()
    if not ds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")

    df = _load_dataset_df(ds)
    series = _prepare_series(df, m.target_column)
    params = json.loads(m.params_json or "{}")
    metrics = json.loads(m.metrics_json or "{}")

    try:
        preds = predict_future(series, m.model_type, params, payload.horizon)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Prediction failed: {e}")

    f = Forecast(model_id=m.id, horizon=payload.horizon, predictions_json=json.dumps(preds))
    db.add(f); db.commit()
    return PredictOut(model_id=m.id, horizon=payload.horizon, predictions=preds, model_type=m.model_type, metrics=metrics)


@router.post("/models/{model_id}/export-csv")
def export_predictions_csv(model_id: int, payload: PredictIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = db.query(ForecastModel).filter(ForecastModel.id == model_id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    _check_owner(m, user)
    ds = db.query(Dataset).filter(Dataset.id == m.dataset_id).first()
    df = _load_dataset_df(ds)
    series = _prepare_series(df, m.target_column)
    params = json.loads(m.params_json or "{}")
    try:
        preds = predict_future(series, m.model_type, params, payload.horizon)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Prediction failed: {e}")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["step", "predicted_value"])
    for i, v in enumerate(preds, start=1):
        w.writerow([f"+{i}", v])
    buf.seek(0)
    safe_name = m.name.replace(" ", "_").replace("/", "_")
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{safe_name}_forecast.csv"'})


@router.get("/report/{dataset_id}")
def comparison_report(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your dataset")
    q = db.query(ForecastModel).filter(ForecastModel.dataset_id == dataset_id)
    if user.role != "admin":
        q = q.filter(ForecastModel.trained_by == user.email)
    models = q.all()
    rows = []
    for m in models:
        try:
            metrics = json.loads(m.metrics_json or "{}")
        except Exception:
            metrics = {}
        rows.append({
            "id": m.id, "name": m.name, "model_type": m.model_type,
            "mae": metrics.get("mae"), "rmse": metrics.get("rmse"), "mape": metrics.get("mape"),
            "trained_by": m.trained_by,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    rows.sort(key=lambda r: (r["rmse"] is None, r["rmse"]))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rank", "id", "name", "model_type", "mae", "rmse", "mape", "trained_by", "created_at"])
    for i, r in enumerate(rows, start=1):
        w.writerow([i, r["id"], r["name"], r["model_type"], r["mae"], r["rmse"], r["mape"], r["trained_by"], r["created_at"]])
    buf.seek(0)
    safe = ds.filename.replace("/", "_").replace("\\", "_")
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="report_{safe}.csv"'})


@router.delete("/models/{model_id}", status_code=204)
def delete_model(model_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = db.query(ForecastModel).filter(ForecastModel.id == model_id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    _check_owner(m, user)
    db.delete(m); db.commit()
    return None
