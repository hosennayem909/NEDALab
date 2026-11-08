from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from econometrics.schemas import (
    CorrelationIn, CorrelationOut,
    VIFIn, VIFOut,
    GrangerIn, GrangerOut,
    DescriptivesIn, DescriptivesOut,
)
from econometrics.stats_engine import (
    correlation_matrix, vif_test, granger_causality, descriptive_stats,
)

router = APIRouter(prefix="/api/econometrics", tags=["econometrics"])


def _get_owned(db: Session, dataset_id: int, user: User) -> Dataset:
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your dataset")
    return ds


def _load_df(ds: Dataset) -> pd.DataFrame:
    if not ds.cleaned_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No cleaned file")
    p = Path(ds.cleaned_path)
    if not p.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File missing")
    return pd.read_csv(p)


@router.post("/correlation", response_model=CorrelationOut)
def correlation(payload: CorrelationIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = _get_owned(db, payload.dataset_id, user)
    df = _load_df(ds)
    try:
        return correlation_matrix(df, payload.columns)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/vif", response_model=VIFOut)
def vif(payload: VIFIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = _get_owned(db, payload.dataset_id, user)
    df = _load_df(ds)
    try:
        return vif_test(df, payload.columns)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/granger", response_model=GrangerOut)
def granger(payload: GrangerIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = _get_owned(db, payload.dataset_id, user)
    df = _load_df(ds)
    try:
        return granger_causality(df, payload.cause, payload.effect, payload.max_lag)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/descriptives", response_model=DescriptivesOut)
def descriptives(payload: DescriptivesIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = _get_owned(db, payload.dataset_id, user)
    df = _load_df(ds)
    try:
        return descriptive_stats(df, payload.columns)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
