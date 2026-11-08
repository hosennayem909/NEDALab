import traceback
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from data_hub.data_ops.schemas import FormulaIn, JoinIn
from data_hub.data_ops.custom_formula import evaluate_formula
from data_hub.data_ops.join import join_datasets

router = APIRouter(prefix="/api/data", tags=["data-ops"])

UPLOAD_DIR = Path("uploads")


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


def _save_new(db, user, df, suffix, source_name):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(source_name).stem if source_name else "dataset"
    name = f"{suffix}_{base}.csv"
    path = UPLOAD_DIR / f"{stamp}_{name}"
    df.to_csv(path, index=False)
    new_ds = Dataset(
        user_email=user.email,
        filename=name,
        row_count=int(df.shape[0]),
        column_count=int(df.shape[1]),
        status="processed",
        cleaned_path=str(path),
    )
    db.add(new_ds); db.commit(); db.refresh(new_ds)
    return new_ds


@router.post("/formula/preview")
def formula_preview(payload: FormulaIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        _, stats, preview = evaluate_formula(df, payload.formula, payload.new_column)
        return {"stats": stats, "preview": preview, "columns": list(df.columns) + [payload.new_column]}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("FORMULA ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/formula/apply", status_code=201)
def formula_apply(payload: FormulaIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        new_df, stats, _ = evaluate_formula(df, payload.formula, payload.new_column)
        suffix = payload.output_name or f"formula_{payload.new_column}"
        new_ds = _save_new(db, user, new_df, suffix, ds.filename)
        return {
            "output_dataset_id": new_ds.id,
            "output_filename": new_ds.filename,
            "stats": stats,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("FORMULA APPLY ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/join/preview")
def join_preview(payload: JoinIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        left_ds = _get_owned(db, payload.left_dataset_id, user)
        right_ds = _get_owned(db, payload.right_dataset_id, user)
        if left_ds.id == right_ds.id:
            raise ValueError("Left and right datasets must be different")

        left = _load(left_ds)
        right = _load(right_ds)

        _, stats, preview = join_datasets(
            left, right,
            payload.left_key, payload.right_key, payload.join_type,
        )
        return {
            "stats": stats,
            "preview": preview,
            "left_columns": list(left.columns),
            "right_columns": list(right.columns),
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("JOIN ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/join/apply", status_code=201)
def join_apply(payload: JoinIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        left_ds = _get_owned(db, payload.left_dataset_id, user)
        right_ds = _get_owned(db, payload.right_dataset_id, user)
        if left_ds.id == right_ds.id:
            raise ValueError("Left and right datasets must be different")

        left = _load(left_ds)
        right = _load(right_ds)

        result, stats, _ = join_datasets(
            left, right,
            payload.left_key, payload.right_key, payload.join_type,
        )
        suffix = payload.output_name or f"joined_{payload.join_type}"
        new_ds = _save_new(db, user, result, suffix, f"{left_ds.filename}_{right_ds.filename}")
        return {
            "output_dataset_id": new_ds.id,
            "output_filename": new_ds.filename,
            "stats": stats,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("JOIN APPLY ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")
