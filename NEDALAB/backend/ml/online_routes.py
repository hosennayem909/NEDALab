"""Online Learning API routes."""
import traceback
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset

from ml.online_schemas import (
    OnlineInitIn, OnlineStepIn, OnlineBatchIn, OnlineSessionOut,
)
from ml import online_engine


router = APIRouter(prefix="/api/ml/online", tags=["online-learning"])


def _get_owned_dataset(db: Session, dataset_id: int, user: User) -> Dataset:
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(403, "Not your dataset")
    return ds


def _get_dataset_path(ds: Dataset) -> Path:
    """Try multiple common attribute names for the data file path."""
    # Try several attribute names commonly used
    for attr in ("cleaned_path", "file_path", "path", "storage_path"):
        val = getattr(ds, attr, None)
        if val:
            p = Path(val)
            if p.exists():
                return p
    # Fallback: check if there's a 'filename' + common dir
    raise HTTPException(400, "Dataset file path not found on disk")


def _load_df(ds: Dataset) -> pd.DataFrame:
    p = _get_dataset_path(ds)
    return pd.read_csv(p)


@router.post("/init", response_model=OnlineSessionOut)
def init_session(
    payload: OnlineInitIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        ds = _get_owned_dataset(db, payload.dataset_id, user)
        df = _load_df(ds)

        for f in payload.features:
            if f not in df.columns:
                raise HTTPException(400, f"Feature not found: {f}")
        if payload.target not in df.columns:
            raise HTTPException(400, f"Target not found: {payload.target}")

        return online_engine.init_session(
            dataset_id=payload.dataset_id,
            target=payload.target,
            features=payload.features,
            task=payload.task,
            model=payload.model,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("ONLINE INIT ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.get("/sessions")
def list_sessions(user: User = Depends(get_current_user)):
    return {"sessions": online_engine.list_sessions()}


@router.get("/session/{session_id}")
def get_session_info(session_id: str, user: User = Depends(get_current_user)):
    info = online_engine.get_session(session_id)
    if info is None:
        raise HTTPException(404, "Session not found")
    return online_engine._session_info(session_id)


@router.delete("/session/{session_id}")
def delete_session(session_id: str, user: User = Depends(get_current_user)):
    ok = online_engine.delete_session(session_id)
    if not ok:
        raise HTTPException(404, "Session not found")
    return {"success": True}


@router.post("/step")
def step(
    payload: OnlineStepIn,
    user: User = Depends(get_current_user),
):
    try:
        return online_engine.step(
            payload.session_id, payload.x, payload.y, payload.learn,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("ONLINE STEP ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/batch")
def batch_step(
    payload: OnlineBatchIn,
    user: User = Depends(get_current_user),
):
    try:
        return online_engine.batch_step(
            payload.session_id, payload.samples, payload.learn,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("ONLINE BATCH ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/train-from-dataset")
def train_from_dataset(
    payload: OnlineInitIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create session + feed all rows from dataset incrementally."""
    try:
        ds = _get_owned_dataset(db, payload.dataset_id, user)
        df = _load_df(ds)

        session_info = online_engine.init_session(
            dataset_id=payload.dataset_id,
            target=payload.target,
            features=payload.features,
            task=payload.task,
            model=payload.model,
        )
        session_id = session_info["session_id"]

        cols = payload.features + [payload.target]
        sub = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
        if len(sub) == 0:
            raise HTTPException(400, "No valid numeric rows")

        samples = sub.to_dict(orient="records")
        result = online_engine.batch_step(session_id, samples, learn=True)

        return {
            **session_info,
            "trained_rows": len(samples),
            "final_metric": result["metric_value"],
            "rolling_metric": result["rolling_metric"],
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("ONLINE TRAIN ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/session/{session_id}/save")
def save_session(session_id: str, user: User = Depends(get_current_user)):
    try:
        path = online_engine.save_session(session_id)
        return {"success": True, "path": path}
    except ValueError as e:
        raise HTTPException(400, str(e))