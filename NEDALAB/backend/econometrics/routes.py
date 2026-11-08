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
from econometrics.schemas import OLSTrainIn, OLSResult, ModelOut, CoefficientRow
from econometrics.engine import train_ols

router = APIRouter(prefix="/api/econometrics", tags=["econometrics"])


def _get_owned(db: Session, dataset_id: int, user: User) -> Dataset:
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your dataset")
    return ds


def _load_df(ds: Dataset) -> pd.DataFrame:
    if not ds.cleaned_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No cleaned file")
    p = Path(ds.cleaned_path)
    if not p.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File missing")
    return pd.read_csv(p)


def _build_result(model_id, dep, indep, result) -> OLSResult:
    """Build OLSResult safely, removing duplicates from metrics."""
    metrics = dict(result["metrics"])
    n_obs = metrics.pop("n_obs", result.get("n_obs", 0))

    # Remove keys not in OLSResult schema
    for k in ["k_params", "df_resid", "log_likelihood"]:
        metrics.pop(k, None)

    # Combine interpretation + robust_se + advanced diagnostics into interpretation
    # (residual_stats and interpretation are flexible dicts in the schema)
    interpretation = dict(result["interpretation"])
    interpretation["robust_se"] = result.get("robust_se", [])

    # Add VIF & BG data to residual_stats for frontend to display
    residual_stats = dict(result["residual_stats"])

    return OLSResult(
        model_id=model_id,
        dependent_var=dep,
        independent_vars=indep,
        n_obs=n_obs,
        coefficients=[CoefficientRow(**c) for c in result["coefficients"]],
        durbin_watson=residual_stats.get("durbin_watson") or 0.0,
        residual_stats=residual_stats,
        interpretation=interpretation,
        **metrics,
    )


@router.post("/ols/train", response_model=OLSResult, status_code=201)
def train(payload: OLSTrainIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load_df(ds)

        result = train_ols(df, payload.dependent_var, payload.independent_vars, payload.add_constant)

        name = payload.name or f"OLS: {payload.dependent_var} ~ {' + '.join(payload.independent_vars)}"

        # Persist model — store advanced diagnostics in diagnostics_json
        m = RegressionModel(
            dataset_id=ds.id,
            name=name,
            model_type="ols",
            dependent_var=payload.dependent_var,
            independent_vars_json=json.dumps(payload.independent_vars),
            params_json=json.dumps(result["coefficients"], default=str),
            metrics_json=json.dumps(result["metrics"], default=str),
            diagnostics_json=json.dumps({
                "residual_stats": result["residual_stats"],
                "interpretation": result["interpretation"],
                "robust_se": result.get("robust_se", []),
            }, default=str),
            trained_by=user.email,
        )
        db.add(m)
        db.commit()
        db.refresh(m)

        return _build_result(m.id, payload.dependent_var, payload.independent_vars, result)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:
        tb = traceback.format_exc()
        print("=" * 60)
        print("OLS TRAIN ERROR:")
        print(tb)
        print("=" * 60)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"{type(e).__name__}: {str(e)}",
        )


@router.get("/models", response_model=list[ModelOut])
def list_models(dataset_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(RegressionModel).order_by(RegressionModel.created_at.desc())
    if dataset_id is not None:
        q = q.filter(RegressionModel.dataset_id == dataset_id)
    if user.role != "admin":
        q = q.filter(RegressionModel.trained_by == user.email)
    return q.all()


@router.get("/models/{model_id}", response_model=ModelOut)
def get_model(model_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = db.query(RegressionModel).filter(RegressionModel.id == model_id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    if user.role != "admin" and m.trained_by != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your model")
    return m


@router.get("/models/{model_id}/result", response_model=OLSResult)
def get_result(model_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = db.query(RegressionModel).filter(RegressionModel.id == model_id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    if user.role != "admin" and m.trained_by != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your model")

    coeffs = json.loads(m.params_json)
    metrics = json.loads(m.metrics_json)
    diag = json.loads(m.diagnostics_json or "{}")
    indep = json.loads(m.independent_vars_json)

    n_obs = metrics.pop("n_obs", 0)
    for k in ["k_params", "df_resid", "log_likelihood"]:
        metrics.pop(k, None)

    interpretation = dict(diag.get("interpretation", {}))
    interpretation["robust_se"] = diag.get("robust_se", [])

    return OLSResult(
        model_id=m.id,
        dependent_var=m.dependent_var,
        independent_vars=indep,
        n_obs=n_obs,
        coefficients=[CoefficientRow(**c) for c in coeffs],
        durbin_watson=diag.get("residual_stats", {}).get("durbin_watson") or 0.0,
        residual_stats=diag.get("residual_stats", {}),
        interpretation=interpretation,
        **metrics,
    )


@router.delete("/models/{model_id}", status_code=204)
def delete_model(model_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = db.query(RegressionModel).filter(RegressionModel.id == model_id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    if user.role != "admin" and m.trained_by != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your model")
    db.delete(m)
    db.commit()
    return None