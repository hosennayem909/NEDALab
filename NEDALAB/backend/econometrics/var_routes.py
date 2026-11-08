"""VAR API routes — /api/econometrics/var/*"""
import traceback
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from econometrics.schemas import VARIn, IRFIn, FEVDIn
from econometrics.var_engine import train_var, impulse_response, fevd


router = APIRouter(prefix="/api/econometrics", tags=["var"])


def _get_owned(db: Session, dataset_id: int, user: User) -> Dataset:
    """Verify dataset exists and user owns it."""
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(403, "Not your dataset")
    return ds


def _load_df(ds: Dataset) -> pd.DataFrame:
    """Load cleaned CSV from dataset path."""
    if not ds.cleaned_path:
        raise HTTPException(400, "No cleaned file")
    p = Path(ds.cleaned_path)
    if not p.exists():
        raise HTTPException(404, "File missing")
    return pd.read_csv(p)


@router.post("/var/train")
def var_train(
    payload: VARIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fit VAR model and return diagnostics."""
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load_df(ds)
        return train_var(
            df,
            payload.variables,
            payload.max_lags,
            payload.lag_order,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("VAR ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/var/irf")
def var_irf(
    payload: IRFIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Compute Impulse Response Functions."""
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load_df(ds)
        return impulse_response(
            df,
            payload.variables,
            payload.max_lags,
            payload.lag_order,
            payload.periods,
            payload.shock_var,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("IRF ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/var/fevd")
def var_fevd(
    payload: FEVDIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Compute Forecast Error Variance Decomposition."""
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load_df(ds)
        return fevd(
            df,
            payload.variables,
            payload.max_lags,
            payload.lag_order,
            payload.periods,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("FEVD ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")