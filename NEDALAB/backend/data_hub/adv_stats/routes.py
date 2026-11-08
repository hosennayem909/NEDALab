from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from data_hub.adv_stats.schemas import (
    TransformPreviewIn, TransformPreviewOut,
    TransformApplyIn, TransformApplyOut,
    TimeSeriesAnalyzeOut, TimeSeriesFillIn, DifferenceIn,
)
from data_hub.adv_stats.transforms import preview_transform, apply_transform
from data_hub.adv_stats.timeseries import (
    analyze_time_series, fill_gaps, difference_series,
)

router = APIRouter(prefix="/api/data", tags=["adv-stats"])

UPLOAD_DIR = Path("uploads")


def _get_owned(db: Session, dataset_id: int, user: User) -> Dataset:
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your dataset")
    return ds


def _load(ds: Dataset) -> pd.DataFrame:
    if not ds.cleaned_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No cleaned file")
    p = Path(ds.cleaned_path)
    if not p.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File missing")
    return pd.read_csv(p)


def _save_new(db: Session, user: User, df: pd.DataFrame, suffix: str, source_filename: str) -> Dataset:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(source_filename).stem if source_filename else "dataset"
    name = f"{suffix}_{base}.csv"
    path = UPLOAD_DIR / f"{stamp}_{name}"
    df.to_csv(path, index=False)
    new_ds = Dataset(
        user_email=user.email,
        filename=name,
        row_count=int(df.shape[0]),
        column_count=int(df.shape[1]),
        status="transformed",
        cleaned_path=str(path),
    )
    db.add(new_ds); db.commit(); db.refresh(new_ds)
    return new_ds


@router.post("/datasets/{dataset_id}/transform-preview", response_model=TransformPreviewOut)
def transform_preview(
    dataset_id: int,
    payload: TransformPreviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ds = _get_owned(db, dataset_id, user)
    df = _load(ds)
    try:
        result = preview_transform(df, payload.column, payload.method, {
            "lower_pct": payload.lower_pct, "upper_pct": payload.upper_pct,
        })
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return TransformPreviewOut(**result)


@router.post("/datasets/{dataset_id}/transform-apply", response_model=TransformApplyOut, status_code=201)
def transform_apply(
    dataset_id: int,
    payload: TransformApplyIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ds = _get_owned(db, dataset_id, user)
    df = _load(ds)
    try:
        new_df = apply_transform(df, payload.column, payload.method, {
            "lower_pct": payload.lower_pct, "upper_pct": payload.upper_pct,
        })
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    new_ds = _save_new(db, user, new_df, f"transformed_{payload.method}", ds.filename)
    _, meta = preview_transform(df, payload.column, payload.method, {}) if False else (None, {})
    return TransformApplyOut(
        output_dataset_id=new_ds.id,
        output_filename=new_ds.filename,
        column=payload.column,
        method=payload.method,
        meta={},
    )


@router.get("/datasets/{dataset_id}/timeseries-analyze", response_model=TimeSeriesAnalyzeOut)
def timeseries_analyze(
    dataset_id: int,
    date_column: str,
    value_column: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ds = _get_owned(db, dataset_id, user)
    df = _load(ds)
    try:
        result = analyze_time_series(df, date_column, value_column)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return TimeSeriesAnalyzeOut(**result)


@router.post("/datasets/{dataset_id}/timeseries-fill", response_model=TransformApplyOut, status_code=201)
def timeseries_fill(
    dataset_id: int,
    payload: TimeSeriesFillIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ds = _get_owned(db, dataset_id, user)
    df = _load(ds)
    try:
        new_df, meta = fill_gaps(
            df, payload.date_column, payload.frequency,
            payload.method, payload.value_columns,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    new_ds = _save_new(db, user, new_df, f"filled_{payload.method}", ds.filename)
    return TransformApplyOut(
        output_dataset_id=new_ds.id,
        output_filename=new_ds.filename,
        column=payload.date_column,
        method=f"fill_{payload.method}",
        meta=meta,
    )


@router.post("/datasets/{dataset_id}/difference", response_model=TransformApplyOut, status_code=201)
def difference_apply(
    dataset_id: int,
    payload: DifferenceIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ds = _get_owned(db, dataset_id, user)
    df = _load(ds)
    if payload.column not in df.columns:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Column '{payload.column}' not found")

    new_col, meta = difference_series(df[payload.column], payload.order)
    new_df = df.copy()
    new_df[payload.column] = new_col
    new_df = new_df.dropna(subset=[payload.column]).reset_index(drop=True)

    new_ds = _save_new(db, user, new_df, f"diff{payload.order}", ds.filename)
    return TransformApplyOut(
        output_dataset_id=new_ds.id,
        output_filename=new_ds.filename,
        column=payload.column,
        method=f"difference_{payload.order}",
        meta=meta,
    )
