import io
import json
import traceback
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from ml.models import MLModel
from ml.schemas import SinglePredictIn, SinglePredictOut, BatchPredictOut
from ml.schemas import TuneIn, ShapIn
from ml.predictors import predict_single, predict_batch
from ml.tuning_engine import tune_model
from ml.shap_engine import compute_shap
from ml.preprocessing import prepare_data

router = APIRouter(prefix="/api/ml", tags=["ml-prediction"])

PRED_DIR = Path("uploads/ml_predictions")
PRED_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Helpers
# ============================================================
def _get_owned(db: Session, dataset_id: int, user: User) -> Dataset:
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(403, "Not your dataset")
    return ds


def _load(ds: Dataset) -> pd.DataFrame:
    if not ds.cleaned_path:
        raise HTTPException(400, "No cleaned file")
    p = Path(ds.cleaned_path)
    if not p.exists():
        raise HTTPException(404, "File missing")
    return pd.read_csv(p)


def _get_model(db: Session, model_id: int, user: User) -> MLModel:
    m = db.query(MLModel).filter(MLModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "Model not found")
    if user.role != "admin" and m.user_id != user.id:
        raise HTTPException(403, "Not your model")
    if not m.model_path:
        raise HTTPException(400, "Model not saved to disk. Re-train to enable predictions.")
    p = Path(m.model_path)
    if not p.exists():
        raise HTTPException(410, "Model file missing on disk")
    return m


# ============================================================
# Prediction endpoints
# ============================================================
@router.get("/models/{model_id}/features")
def model_features(model_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = _get_model(db, model_id, user)
    feats = json.loads(m.feature_columns_json or "[]")
    return {
        "model_id": m.id,
        "feature_columns": feats,
        "target_column": m.target_column,
        "task_type": m.task_type,
        "algorithm": m.algorithm,
    }


@router.post("/models/{model_id}/predict", response_model=SinglePredictOut)
def predict_one(
    model_id: int,
    payload: SinglePredictIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        m = _get_model(db, model_id, user)
        return predict_single(m.model_path, payload.input_data)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("PREDICT ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/models/{model_id}/predict-batch")
async def predict_batch_endpoint(
    model_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        m = _get_model(db, model_id, user)
        name = (file.filename or "").lower()
        if not (name.endswith(".csv") or name.endswith(".xlsx")):
            raise HTTPException(400, "Only CSV or Excel files allowed")

        raw = await file.read()
        try:
            if name.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(raw))
            else:
                df = pd.read_excel(io.BytesIO(raw))
        except Exception as e:
            raise HTTPException(400, f"Could not read file: {e}")

        if df.empty:
            raise HTTPException(400, "Uploaded file is empty")

        try:
            out_df, stats = predict_batch(m.model_path, df)
        except ValueError as e:
            raise HTTPException(400, str(e))

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = PRED_DIR / f"predictions_{m.id}_{stamp}.csv"
        out_df.to_csv(out_path, index=False)

        preview = out_df.head(20).fillna("").astype(str).to_dict(orient="records")
        return {
            "model_id": m.id,
            "n_rows": int(len(out_df)),
            "stats": stats,
            "preview": preview,
            "download_filename": out_path.name,
        }
    except HTTPException:
        raise
    except Exception as e:
        print("BATCH PREDICT ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.get("/predictions/{filename}")
def download_predictions(filename: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    safe_name = Path(filename).name
    p = PRED_DIR / safe_name
    if not p.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path=str(p), media_type="text/csv", filename=safe_name)


@router.get("/models/{model_id}/download")
def download_model_file(model_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = _get_model(db, model_id, user)
    p = Path(m.model_path)
    return FileResponse(path=str(p), media_type="application/octet-stream", filename=f"model_{m.id}.joblib")


# ============================================================
# Tuning + SHAP endpoints (Batch 5)
# ============================================================
@router.post("/tune")
def tune_endpoint(payload: TuneIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)

        data = prepare_data(
            df, payload.target_column, payload.feature_columns,
            task_type=payload.task_type,
        )
        actual_task = data["task_type"]

        return tune_model(
            data, actual_task, payload.algorithm,
            payload.method, payload.n_iter, payload.cv_folds,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("TUNE ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/shap")
def shap_endpoint(payload: ShapIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        m = _get_model(db, payload.model_id, user)
        ds = db.query(Dataset).filter(Dataset.id == m.dataset_id).first()
        if not ds or not ds.cleaned_path:
            raise HTTPException(404, "Dataset not found")
        df = pd.read_csv(ds.cleaned_path)
        return compute_shap(m.model_path, df, payload.max_samples)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("SHAP ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")
