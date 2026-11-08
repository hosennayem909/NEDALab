import json
import traceback
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from econometrics.deepen_engine import (
    iv_regression, diff_in_diff, johansen_test, vecm_fit,
)
from econometrics.deepen_schemas import IVIn, DiDIn, JohansenIn, VECMIn

router = APIRouter(prefix="/api/econometrics", tags=["econ-deepen"])


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


@router.post("/iv")
def iv_endpoint(payload: IVIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return iv_regression(
            df, payload.dependent, payload.endogenous,
            payload.instruments, payload.exogenous,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("IV ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/did")
def did_endpoint(payload: DiDIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return diff_in_diff(df, payload.outcome, payload.treatment_col, payload.time_col, payload.post_period)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("DID ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/johansen")
def johansen_endpoint(payload: JohansenIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return johansen_test(df, payload.variables, payload.det_order, payload.k_ar_diff)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("JOHANSEN ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/vecm")
def vecm_endpoint(payload: VECMIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return vecm_fit(df, payload.variables, payload.coint_rank, payload.k_ar_diff)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("VECM ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")
