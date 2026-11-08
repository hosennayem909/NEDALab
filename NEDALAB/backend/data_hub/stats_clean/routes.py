from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from data_hub.stats_clean.schemas import DataFrameStatsOut
from data_hub.stats_clean.analyzer import analyze_dataframe

router = APIRouter(prefix="/api/data", tags=["stats-clean"])


def _get_owned(db: Session, dataset_id: int, user: User) -> Dataset:
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your dataset")
    return ds


@router.get("/datasets/{dataset_id}/stats-analyze", response_model=DataFrameStatsOut)
def stats_analyze(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ds = _get_owned(db, dataset_id, user)
    if not ds.cleaned_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No cleaned file")
    p = Path(ds.cleaned_path)
    if not p.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File missing")
    df = pd.read_csv(p)
    return analyze_dataframe(df)
