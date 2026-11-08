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
from ml.models import MLModel
from ml.schemas import TrainIn, ModelOut, TrainResult
from ml.preprocessing import prepare_data
from ml.trainers import train_model, list_algorithms
from ml.model_registry import save_model_bundle, delete_model_file
from ml.eval_engine import (
    cross_validate, roc_data, pr_curve_data, learning_curve_data, regression_diagnostics,
)
from ml.schemas import (
    MLCrossValIn, MLROCCurveIn, MLLearningCurveIn, MLDiagnosticsIn,
)

router = APIRouter(prefix="/api/ml", tags=["machine-learning"])


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


@router.get("/algorithms")
def algorithms():
    return list_algorithms()


@router.post("/train", response_model=TrainResult, status_code=201)
def train(payload: TrainIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)

        data = prepare_data(
            df,
            payload.target_column,
            payload.feature_columns,
            task_type=payload.task_type,
            test_size=payload.test_size,
            random_state=payload.random_state,
        )

        actual_task = data["task_type"]

        model, metrics, feature_importance, extras = train_model(
            data, actual_task, payload.algorithm,
        )

        # Persist model + preprocessor to disk
        metadata_for_save = {
            "algorithm": payload.algorithm,
            "target_column": payload.target_column,
            "task_type": actual_task,
            "features": payload.feature_columns,
        }
        model_path = save_model_bundle(
            model=model,
            preprocessor=data["preprocessor"],
            feature_names=data["feature_names"],
            task_type=actual_task,
            label_encoder=data.get("label_encoder"),
            metadata=metadata_for_save,
        )

        name = payload.name or f"{payload.algorithm} on {payload.target_column}"

        record = MLModel(
            user_id=user.id,
            dataset_id=ds.id,
            name=name,
            task_type=actual_task,
            algorithm=payload.algorithm,
            target_column=payload.target_column,
            feature_columns_json=json.dumps(payload.feature_columns),
            hyperparams_json=json.dumps({
                "test_size": payload.test_size,
                "random_state": payload.random_state,
            }),
            metrics_json=json.dumps(metrics),
            feature_importance_json=json.dumps(feature_importance),
            split_config_json=json.dumps({
                "n_train": data["n_train"],
                "n_test": data["n_test"],
                "n_features": data["n_features"],
                "numeric_features": data["numeric_features"],
                "categorical_features": data["categorical_features"],
            }),
            model_path=model_path,
            training_samples=data["n_train"],
            trained_by=user.email,
        )
        db.add(record); db.commit(); db.refresh(record)

        return TrainResult(
            model_id=record.id,
            name=name,
            task_type=actual_task,
            algorithm=payload.algorithm,
            target_column=payload.target_column,
            feature_columns=payload.feature_columns,
            n_train=data["n_train"],
            n_test=data["n_test"],
            n_features=data["n_features"],
            metrics=metrics,
            feature_importance=feature_importance,
            confusion_matrix=extras.get("confusion_matrix"),
            classification_report=extras.get("classification_report"),
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("ML TRAIN ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.get("/models", response_model=list[ModelOut])
def list_models(dataset_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(MLModel).order_by(MLModel.created_at.desc())
    if dataset_id is not None:
        q = q.filter(MLModel.dataset_id == dataset_id)
    if user.role != "admin":
        q = q.filter(MLModel.user_id == user.id)
    return q.all()


@router.get("/models/{model_id}", response_model=ModelOut)
def get_model(model_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = db.query(MLModel).filter(MLModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "Model not found")
    if user.role != "admin" and m.user_id != user.id:
        raise HTTPException(403, "Not your model")
    return m


@router.delete("/models/{model_id}", status_code=204)
def delete_model(model_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = db.query(MLModel).filter(MLModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "Model not found")
    if user.role != "admin" and m.user_id != user.id:
        raise HTTPException(403, "Not your model")
    if m.model_path:
        delete_model_file(m.model_path)
    db.delete(m); db.commit()
    return None


# ============ Advanced Evaluation Endpoints ============

@router.post("/cross-validate")
def cross_validate_endpoint(payload: MLCrossValIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return cross_validate(
            df, payload.target_column, payload.feature_columns,
            payload.algorithm, payload.task_type, payload.n_folds,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("CV ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/roc-curve")
def roc_curve_endpoint(payload: MLROCCurveIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return roc_data(df, payload.target_column, payload.feature_columns, payload.algorithm, payload.task_type)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("ROC ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/pr-curve")
def pr_curve_endpoint(payload: MLROCCurveIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return pr_curve_data(df, payload.target_column, payload.feature_columns, payload.algorithm, payload.task_type)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("PR ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/learning-curve")
def learning_curve_endpoint(payload: MLLearningCurveIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return learning_curve_data(
            df, payload.target_column, payload.feature_columns,
            payload.algorithm, payload.task_type, payload.n_folds,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("LC ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/regression-diagnostics")
def regression_diag_endpoint(payload: MLDiagnosticsIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return regression_diagnostics(df, payload.target_column, payload.feature_columns, payload.algorithm)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("DIAG ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")
