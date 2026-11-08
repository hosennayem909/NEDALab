import traceback
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from data_hub.viz.engine import (
    line_data, bar_data, scatter_data, histogram_data,
    box_data, pie_data, heatmap_data, column_info,
)
from data_hub.viz.schemas import (
    LineIn, BarIn, ScatterIn, HistogramIn, BoxIn, PieIn, HeatmapIn,
)

router = APIRouter(prefix="/api/viz", tags=["visualization"])


def _get_owned(db, dataset_id, user):
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(403, "Not your dataset")
    return ds


def _load(ds):
    if not ds.cleaned_path:
        raise HTTPException(400, "No cleaned file")
    p = Path(ds.cleaned_path)
    if not p.exists():
        raise HTTPException(404, "File missing")
    return pd.read_csv(p)


def _handle(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("VIZ ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.get("/columns/{dataset_id}")
def get_columns(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, dataset_id, user)
        df = _load(ds)
        return _handle(column_info, df)
    except HTTPException:
        raise


@router.post("/line")
def viz_line(payload: LineIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return _handle(line_data, df, payload.x_col, payload.y_cols, payload.agg)
    except HTTPException:
        raise


@router.post("/bar")
def viz_bar(payload: BarIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return _handle(bar_data, df, payload.x_col, payload.y_col, payload.agg, payload.top_n)
    except HTTPException:
        raise


@router.post("/scatter")
def viz_scatter(payload: ScatterIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return _handle(scatter_data, df, payload.x_col, payload.y_col, payload.color_col)
    except HTTPException:
        raise


@router.post("/histogram")
def viz_histogram(payload: HistogramIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return _handle(histogram_data, df, payload.col, payload.bins)
    except HTTPException:
        raise


@router.post("/box")
def viz_box(payload: BoxIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return _handle(box_data, df, payload.col, payload.group_col)
    except HTTPException:
        raise


@router.post("/pie")
def viz_pie(payload: PieIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return _handle(pie_data, df, payload.category_col, payload.value_col, payload.top_n)
    except HTTPException:
        raise


@router.post("/heatmap")
def viz_heatmap(payload: HeatmapIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return _handle(heatmap_data, df, payload.cols)
    except HTTPException:
        raise
