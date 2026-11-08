import json
import traceback
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from econometrics.models import RegressionModel
from econometrics.schemas import PanelTrainIn, HausmanIn
from econometrics.panel_engine import (
    train_panel,
    hausman_test,
    ftest_poolability,
    breusch_pagan_lm,
)

router = APIRouter(prefix="/api/econometrics", tags=["panel"])


def _get_owned(db, dataset_id, user):
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(403, "Not your dataset")
    return ds


def _load_df(ds):
    if not ds.cleaned_path:
        raise HTTPException(400, "No cleaned file")
    p = Path(ds.cleaned_path)
    if not p.exists():
        raise HTTPException(404, "File missing")
    return pd.read_csv(p)


@router.post("/panel/train", status_code=201)
def panel_train(payload: PanelTrainIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load_df(ds)
        result = train_panel(
            df, payload.entity_col, payload.time_col,
            payload.dependent_var, payload.independent_vars,
            payload.model_type,
        )

        name = payload.name or (
            f"Panel {payload.model_type.upper()}: {payload.dependent_var} ~ "
            f"{' + '.join(payload.independent_vars)}"
        )

        m = RegressionModel(
            dataset_id=ds.id,
            name=name,
            model_type=f"panel_{payload.model_type}",
            dependent_var=payload.dependent_var,
            independent_vars_json=json.dumps({
                "indep": payload.independent_vars,
                "entity": payload.entity_col,
                "time": payload.time_col,
            }),
            params_json=json.dumps(result["coefficients"], default=str),
            metrics_json=json.dumps(result["metrics"], default=str),
            diagnostics_json=json.dumps({}, default=str),
            trained_by=user.email,
        )
        db.add(m); db.commit(); db.refresh(m)

        return {
            "model_id": m.id,
            "model_type": result["model_type"],
            "entity_col": payload.entity_col,
            "time_col": payload.time_col,
            "dependent_var": payload.dependent_var,
            "independent_vars": payload.independent_vars,
            "coefficients": result["coefficients"],
            **result["metrics"],
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("PANEL ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/panel/hausman")
def panel_hausman(payload: HausmanIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load_df(ds)
        result = hausman_test(
            df, payload.entity_col, payload.time_col,
            payload.dependent_var, payload.independent_vars,
        )
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("HAUSMAN ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


# ============================================================
# NEW Endpoints: F-test for Poolability & Breusch-Pagan LM
# ============================================================
@router.post("/panel/ftest-poolability")
def panel_ftest(payload: HausmanIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load_df(ds)
        return ftest_poolability(
            df, payload.entity_col, payload.time_col,
            payload.dependent_var, payload.independent_vars,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("FTEST ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/panel/bp-lm")
def panel_bp_lm(payload: HausmanIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load_df(ds)
        return breusch_pagan_lm(
            df, payload.entity_col, payload.time_col,
            payload.dependent_var, payload.independent_vars,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("BP-LM ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")