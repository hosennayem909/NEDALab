import json
import time
import secrets
import hashlib
import traceback
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from ml.models import MLModel
from ml.automl.models import ModelAPIKey, PredictionLog
from ml.automl.schemas import APIKeyCreateIn, PredictExternalIn, DriftCheckIn
from ml.predictors import predict_single
from ml.automl.monitoring import detect_drift
from data_hub.models import Dataset
from pathlib import Path
import pandas as pd

router = APIRouter(prefix="/api", tags=["public-api"])


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _get_owned_model(db, model_id, user):
    m = db.query(MLModel).filter(MLModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "Model not found")
    if user.role != "admin" and m.user_id != user.id:
        raise HTTPException(403, "Not your model")
    return m


# ---------- API Key Management ----------

@router.post("/api-keys")
def create_api_key(payload: APIKeyCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = _get_owned_model(db, payload.model_id, user)
    if not m.model_path:
        raise HTTPException(400, "Model not yet saved to disk")

    raw_key = "nl_" + secrets.token_urlsafe(32)
    key_hash = _hash_key(raw_key)
    key_prefix = raw_key[:12]

    k = ModelAPIKey(
        model_id=m.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=payload.name or f"Key for {m.name}",
        active=True,
    )
    db.add(k); db.commit(); db.refresh(k)

    return {
        "id": k.id,
        "model_id": k.model_id,
        "api_key": raw_key,  # ONLY returned once
        "key_prefix": k.key_prefix,
        "name": k.name,
        "message": "Save this key now. It will not be shown again.",
    }


@router.get("/models/{model_id}/api-keys")
def list_api_keys(model_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = _get_owned_model(db, model_id, user)
    keys = db.query(ModelAPIKey).filter(ModelAPIKey.model_id == m.id).all()
    return [
        {
            "id": k.id,
            "key_prefix": k.key_prefix,
            "name": k.name,
            "active": k.active,
            "call_count": k.call_count,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        }
        for k in keys
    ]


@router.delete("/api-keys/{key_id}", status_code=204)
def revoke_api_key(key_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    k = db.query(ModelAPIKey).filter(ModelAPIKey.id == key_id).first()
    if not k:
        raise HTTPException(404, "Key not found")
    _get_owned_model(db, k.model_id, user)
    k.active = False
    db.commit()
    return None


# ---------- Public Prediction API ----------

@router.post("/predict/{model_id}")
def public_predict(
    model_id: int,
    payload: PredictExternalIn,
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Public prediction endpoint authenticated by API key."""
    if not x_api_key:
        raise HTTPException(401, "Missing X-API-Key header")

    key_hash = _hash_key(x_api_key)
    k = db.query(ModelAPIKey).filter(
        ModelAPIKey.key_hash == key_hash,
        ModelAPIKey.model_id == model_id,
        ModelAPIKey.active == True,  # noqa: E712
    ).first()
    if not k:
        raise HTTPException(401, "Invalid or inactive API key")

    m = db.query(MLModel).filter(MLModel.id == model_id).first()
    if not m or not m.model_path:
        raise HTTPException(404, "Model not available")

    started = time.time()
    try:
        result = predict_single(m.model_path, payload.features)
        latency = int((time.time() - started) * 1000)

        # Log
        log = PredictionLog(
            model_id=m.id,
            source="api",
            input_json=json.dumps(payload.features),
            output_json=json.dumps(result),
            success=True,
            latency_ms=latency,
        )
        db.add(log)
        k.call_count = (k.call_count or 0) + 1
        k.last_used_at = datetime.utcnow()
        db.commit()

        return {
            "model_id": m.id,
            "model_name": m.name,
            "latency_ms": latency,
            **result,
        }
    except Exception as e:
        latency = int((time.time() - started) * 1000)
        log = PredictionLog(
            model_id=m.id, source="api",
            input_json=json.dumps(payload.features),
            output_json=json.dumps({}),
            success=False,
            error_message=f"{type(e).__name__}: {str(e)}",
            latency_ms=latency,
        )
        db.add(log); db.commit()
        raise HTTPException(400, str(e))


# ---------- Prediction Logs ----------

@router.get("/models/{model_id}/prediction-logs")
def get_prediction_logs(model_id: int, limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = _get_owned_model(db, model_id, user)
    logs = db.query(PredictionLog).filter(
        PredictionLog.model_id == m.id
    ).order_by(PredictionLog.created_at.desc()).limit(limit).all()

    return [
        {
            "id": l.id,
            "source": l.source,
            "success": l.success,
            "latency_ms": l.latency_ms,
            "created_at": l.created_at.isoformat() if l.created_at else None,
            "error_message": l.error_message,
        }
        for l in logs
    ]


# ---------- Drift Detection ----------

@router.post("/models/{model_id}/drift-check")
def drift_check(model_id: int, payload: DriftCheckIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        m = _get_owned_model(db, model_id, user)

        # Reference data (original training dataset)
        ref_ds = db.query(Dataset).filter(Dataset.id == m.dataset_id).first()
        cur_ds = db.query(Dataset).filter(Dataset.id == payload.dataset_id).first()
        if not ref_ds or not cur_ds:
            raise HTTPException(404, "Dataset not found")

        if not ref_ds.cleaned_path or not cur_ds.cleaned_path:
            raise HTTPException(400, "Missing cleaned file")

        ref_df = pd.read_csv(ref_ds.cleaned_path)
        cur_df = pd.read_csv(cur_ds.cleaned_path)

        feature_cols = json.loads(m.feature_columns_json or "[]")
        result = detect_drift(ref_df, cur_df, feature_cols)
        result["model_id"] = m.id
        result["model_name"] = m.name
        result["reference_dataset"] = ref_ds.filename
        result["current_dataset"] = cur_ds.filename
        return result
    except HTTPException:
        raise
    except Exception as e:
        print("DRIFT ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")
