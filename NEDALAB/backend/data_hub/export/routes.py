import json
import io
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset, CleaningReport
from data_hub.export.excel import export_dataset_excel
from data_hub.export.pdf import export_dataset_pdf
from data_hub.preview import get_stats

router = APIRouter(prefix="/api/export", tags=["export"])


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


@router.get("/dataset/{dataset_id}/excel")
def export_excel(dataset_id: int, include_stats: bool = True, include_report: bool = True, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = _get_owned(db, dataset_id, user)
    df = _load(ds)

    stats = None
    if include_stats:
        try:
            stats = get_stats(df)
        except Exception:
            pass

    cleaning = None
    if include_report:
        cr = db.query(CleaningReport).filter(CleaningReport.dataset_id == ds.id).first()
        if cr:
            try:
                s = json.loads(cr.stats_json or "{}")
                cleaning = {
                    "preset": cr.preset,
                    "log": json.loads(cr.log_json or "[]"),
                    "stats_before": s.get("stats_before", {}),
                    "stats_after": s.get("stats_after", {}),
                }
            except Exception:
                pass

    xls_bytes = export_dataset_excel(df, ds.filename, cleaning, stats)
    base = Path(ds.filename).stem if ds.filename else f"dataset_{ds.id}"
    return StreamingResponse(
        io.BytesIO(xls_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{base}_export.xlsx"'},
    )


@router.get("/dataset/{dataset_id}/pdf")
def export_pdf(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = _get_owned(db, dataset_id, user)
    df = _load(ds)

    try:
        stats = get_stats(df)
    except Exception:
        stats = None

    cleaning = None
    cr = db.query(CleaningReport).filter(CleaningReport.dataset_id == ds.id).first()
    if cr:
        try:
            s = json.loads(cr.stats_json or "{}")
            cleaning = {
                "preset": cr.preset,
                "log": json.loads(cr.log_json or "[]"),
                "stats_before": s.get("stats_before", {}),
                "stats_after": s.get("stats_after", {}),
            }
        except Exception:
            pass

    pdf_bytes = export_dataset_pdf(
        ds.filename,
        df.shape,
        list(df.columns),
        stats,
        cleaning,
    )
    base = Path(ds.filename).stem if ds.filename else f"dataset_{ds.id}"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{base}_report.pdf"'},
    )


@router.get("/model/{model_id}/pdf")
def export_model_pdf(model_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from econometrics.models import RegressionModel
    m = db.query(RegressionModel).filter(RegressionModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "Model not found")
    if user.role != "admin" and m.trained_by != user.email:
        raise HTTPException(403, "Not your model")

    ds = db.query(Dataset).filter(Dataset.id == m.dataset_id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")

    df = _load(ds)

    try:
        coeffs = json.loads(m.params_json or "[]")
        metrics = json.loads(m.metrics_json or "{}")
        diag = json.loads(m.diagnostics_json or "{}")
    except Exception:
        coeffs, metrics, diag = [], {}, {}

    model_result = {
        "model_type": m.model_type,
        "dependent_var": m.dependent_var,
        "n_obs": metrics.get("n_obs", 0),
        "r_squared": metrics.get("r_squared", ""),
        "adj_r_squared": metrics.get("adj_r_squared", ""),
        "f_statistic": metrics.get("f_statistic", ""),
        "durbin_watson": diag.get("residual_stats", {}).get("durbin_watson", ""),
        "coefficients": coeffs,
        "interpretation": diag.get("interpretation", {}),
    }

    pdf_bytes = export_dataset_pdf(
        ds.filename,
        df.shape,
        list(df.columns),
        None,
        None,
        model_result,
    )
    safe = m.name.replace(" ", "_").replace("/", "_")[:40]
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe}_report.pdf"'},
    )
