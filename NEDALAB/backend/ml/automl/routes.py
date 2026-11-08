import json
import time
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
from ml.models import MLModel
from ml.automl.models import AutoMLRun
from ml.automl.schemas import AutoMLIn
from ml.automl.engine import run_automl
from ml.model_registry import save_model_bundle

router = APIRouter(prefix="/api/automl", tags=["automl"])


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


@router.post("/run")
def run(payload: AutoMLIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)

        # Create run record
        run_rec = AutoMLRun(
            user_id=user.id,
            dataset_id=ds.id,
            name=payload.name or f"AutoML run {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            task_type="auto",
            target_column=payload.target_column,
            feature_columns_json=json.dumps(payload.feature_columns),
            config_json=json.dumps({
                "test_size": payload.test_size,
                "random_state": payload.random_state,
                "max_models": payload.max_models,
            }),
            status="running",
            created_by=user.email,
        )
        db.add(run_rec); db.commit(); db.refresh(run_rec)

        # Run AutoML
        try:
            result = run_automl(
                df, payload.target_column, payload.feature_columns,
                task_type=payload.task_type,
                test_size=payload.test_size,
                random_state=payload.random_state,
                max_models=payload.max_models,
            )
        except Exception as e:
            run_rec.status = "failed"
            run_rec.error_message = f"{type(e).__name__}: {str(e)}"
            run_rec.completed_at = datetime.now(timezone.utc) if False else datetime.utcnow()
            db.commit()
            raise HTTPException(400, str(e))

        # Save best model to MLModel
        best_model_id = None
        if result["best_algorithm"]:
            best_alg = result["best_algorithm"]
            # Re-train best and save bundle
            from ml.trainers import train_model
            best_model_obj, best_metrics, best_fi, best_extras = train_model(
                result["data"], result["task_type"], best_alg,
            )
            metadata = {
                "algorithm": best_alg,
                "target_column": payload.target_column,
                "task_type": result["task_type"],
                "features": payload.feature_columns,
                "source": "automl",
                "automl_run_id": run_rec.id,
            }
            model_path = save_model_bundle(
                model=best_model_obj,
                preprocessor=result["data"]["preprocessor"],
                feature_names=result["data"]["feature_names"],
                task_type=result["task_type"],
                label_encoder=result["data"].get("label_encoder"),
                metadata=metadata,
            )

            m = MLModel(
                user_id=user.id,
                dataset_id=ds.id,
                name=f"AutoML Best: {best_alg}",
                task_type=result["task_type"],
                algorithm=best_alg,
                target_column=payload.target_column,
                feature_columns_json=json.dumps(payload.feature_columns),
                hyperparams_json=json.dumps({"source": "automl"}),
                metrics_json=json.dumps(best_metrics),
                feature_importance_json=json.dumps(best_fi),
                split_config_json=json.dumps({
                    "n_train": result["data"]["n_train"],
                    "n_test": result["data"]["n_test"],
                    "n_features": result["data"]["n_features"],
                }),
                model_path=model_path,
                training_samples=result["data"]["n_train"],
                trained_by=user.email,
            )
            db.add(m); db.commit(); db.refresh(m)
            best_model_id = m.id

        # Update run record
        # Remove data (not JSON serializable) before saving
        leaderboard_clean = []
        for r in result["leaderboard"]:
            r_clean = {k: v for k, v in r.items() if k != "data"}
            leaderboard_clean.append(r_clean)

        run_rec.status = "completed"
        run_rec.task_type = result["task_type"]
        run_rec.best_model_id = best_model_id
        run_rec.leaderboard_json = json.dumps(leaderboard_clean, default=str)
        run_rec.total_models_tested = result["total_models_tested"]
        run_rec.elapsed_seconds = result["elapsed_seconds"]
        run_rec.completed_at = datetime.utcnow()
        db.commit()

        return {
            "run_id": run_rec.id,
            "task_type": result["task_type"],
            "best_algorithm": result["best_algorithm"],
            "best_score": result["best_score"],
            "best_metrics": result["best_metrics"],
            "best_model_id": best_model_id,
            "total_models_tested": result["total_models_tested"],
            "total_successful": result["total_successful"],
            "total_failed": result["total_failed"],
            "elapsed_seconds": result["elapsed_seconds"],
            "leaderboard": leaderboard_clean,
        }
    except HTTPException:
        raise
    except Exception as e:
        print("AUTOML ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.get("/runs")
def list_runs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(AutoMLRun).order_by(AutoMLRun.started_at.desc()).limit(50)
    if user.role != "admin":
        q = q.filter(AutoMLRun.user_id == user.id)
    runs = q.all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "dataset_id": r.dataset_id,
            "task_type": r.task_type,
            "status": r.status,
            "best_model_id": r.best_model_id,
            "total_models_tested": r.total_models_tested,
            "elapsed_seconds": r.elapsed_seconds,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs
    ]


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = db.query(AutoMLRun).filter(AutoMLRun.id == run_id).first()
    if not r:
        raise HTTPException(404, "Run not found")
    if user.role != "admin" and r.user_id != user.id:
        raise HTTPException(403, "Not your run")

    leaderboard = []
    if r.leaderboard_json:
        try:
            leaderboard = json.loads(r.leaderboard_json)
        except Exception:
            leaderboard = []

    return {
        "id": r.id,
        "name": r.name,
        "dataset_id": r.dataset_id,
        "task_type": r.task_type,
        "target_column": r.target_column,
        "feature_columns": json.loads(r.feature_columns_json or "[]"),
        "status": r.status,
        "best_model_id": r.best_model_id,
        "total_models_tested": r.total_models_tested,
        "elapsed_seconds": r.elapsed_seconds,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "error_message": r.error_message,
        "leaderboard": leaderboard,
    }
