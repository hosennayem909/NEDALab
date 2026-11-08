import traceback
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from data_hub.feature_eng.engine import apply_engineering
from data_hub.feature_eng.schemas import FeatureEngConfig

router = APIRouter(prefix="/api/feature-eng", tags=["feature-engineering"])

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


def _config_to_dict(cfg: FeatureEngConfig) -> dict:
    return {
        "lag": cfg.lag.model_dump(),
        "rolling": cfg.rolling.model_dump(),
        "diff": cfg.diff.model_dump(),
        "interaction": cfg.interaction.model_dump(),
        "polynomial": cfg.polynomial.model_dump(),
        "date": cfg.date.model_dump(),
        "binning": cfg.binning.model_dump(),
        "onehot": cfg.onehot.model_dump(),
    }


@router.post("/preview")
def preview(payload: FeatureEngConfig, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        config = _config_to_dict(payload)
        new_df, report = apply_engineering(df, config)

        preview_df = new_df.head(20).fillna("").astype(str)
        return {
            "report": report,
            "preview": preview_df.to_dict(orient="records"),
            "columns": [str(c) for c in new_df.columns],
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("FEATURE-ENG PREVIEW ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/apply", status_code=201)
def apply(payload: FeatureEngConfig, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        config = _config_to_dict(payload)
        new_df, report = apply_engineering(df, config)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = Path(ds.filename).stem if ds.filename else f"dataset_{ds.id}"
        name = payload.output_name or f"engineered_{base}.csv"
        if not name.endswith(".csv"):
            name += ".csv"
        path = UPLOAD_DIR / f"{stamp}_{name}"
        new_df.to_csv(path, index=False)

        new_ds = Dataset(
            user_email=user.email,
            filename=name,
            row_count=int(new_df.shape[0]),
            column_count=int(new_df.shape[1]),
            status="engineered",
            cleaned_path=str(path),
        )
        db.add(new_ds)
        db.commit()
        db.refresh(new_ds)

        return {
            "output_dataset_id": new_ds.id,
            "output_filename": new_ds.filename,
            "report": report,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("FEATURE-ENG APPLY ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.get("/suggest/{dataset_id}")
def suggest(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Auto-suggest features based on column types."""
    try:
        ds = _get_owned(db, dataset_id, user)
        df = _load(ds)

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        categorical_cols = [c for c in df.columns if c not in numeric_cols]

        date_cols = []
        for c in df.columns:
            if c in numeric_cols:
                continue
            try:
                sample = df[c].dropna().head(20)
                if len(sample) == 0:
                    continue
                parsed = pd.to_datetime(sample, errors="coerce")
                if parsed.notna().sum() >= max(1, int(len(sample) * 0.8)):
                    date_cols.append(c)
            except Exception:
                continue

        # Auto-detect low-cardinality categoricals for one-hot
        onehot_candidates = []
        for c in categorical_cols:
            if c in date_cols:
                continue
            n_unique = df[c].nunique()
            if 2 <= n_unique <= 20:
                onehot_candidates.append(c)

        return {
            "dataset_id": ds.id,
            "n_rows": int(df.shape[0]),
            "n_columns": int(df.shape[1]),
            "numeric_columns": numeric_cols,
            "categorical_columns": categorical_cols,
            "date_columns": date_cols,
            "suggestions": {
                "lag": {"columns": numeric_cols, "lags": [1, 2, 3]},
                "rolling": {"columns": numeric_cols, "windows": [3, 7], "stats": ["mean", "std"]},
                "diff": {"columns": numeric_cols},
                "polynomial": {"columns": numeric_cols, "degrees": [2]},
                "date": {"columns": date_cols, "features": ["year", "month", "day", "weekday", "quarter"]},
                "onehot": {"columns": onehot_candidates, "max_categories": 20},
                "binning": {"columns": numeric_cols, "n_bins": 5, "strategy": "equal_width"},
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        print("SUGGEST ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")
