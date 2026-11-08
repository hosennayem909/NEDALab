import io
import json
import traceback
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset, CleaningReport
from data_hub.preview import get_stats
from data_hub.quality.engine import scan_quality
from data_hub.quality.imputation import impute_advanced
from data_hub.quality.schemas import ImputeIn
from data_hub.export.word import export_word_report

router = APIRouter(prefix="/api/data", tags=["quality"])

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


@router.get("/quality/{dataset_id}")
def quality_report(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, dataset_id, user)
        df = _load(ds)
        report = scan_quality(df)
        report["dataset_id"] = ds.id
        report["filename"] = ds.filename
        return report
    except HTTPException:
        raise
    except Exception as e:
        print("QUALITY ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/impute")
def impute(payload: ImputeIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)

        new_df, report = impute_advanced(
            df, payload.method, payload.columns,
            payload.n_neighbors, payload.max_iter,
        )

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = Path(ds.filename).stem if ds.filename else f"dataset_{ds.id}"
        name = payload.output_name or f"imputed_{payload.method}_{base}.csv"
        if not name.endswith(".csv"):
            name += ".csv"
        path = UPLOAD_DIR / f"{stamp}_{name}"
        new_df.to_csv(path, index=False)

        new_ds = Dataset(
            user_email=user.email,
            filename=name,
            row_count=int(new_df.shape[0]),
            column_count=int(new_df.shape[1]),
            status="imputed",
            cleaned_path=str(path),
        )
        db.add(new_ds); db.commit(); db.refresh(new_ds)

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
        print("IMPUTE ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.get("/datasets/{dataset_id}/export-word")
def export_word(dataset_id: int, include_quality: bool = True, include_stats: bool = True, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, dataset_id, user)
        df = _load(ds)

        quality = None
        if include_quality:
            try:
                quality = scan_quality(df)
            except Exception:
                pass

        stats = None
        if include_stats:
            try:
                stats = get_stats(df)
            except Exception:
                pass

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

        docx_bytes = export_word_report(
            ds.filename, df.shape, list(df.columns),
            quality, stats, cleaning, None,
        )
        base = Path(ds.filename).stem if ds.filename else f"dataset_{ds.id}"
        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{base}_report.docx"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        print("WORD ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")
