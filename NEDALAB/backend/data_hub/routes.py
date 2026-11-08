import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import datetime
import io
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset, CleaningReport, Aggregation
from data_hub.schemas import (
    DatasetOut, PreviewOut, StatsOut,
    CleanConfig, CleaningPreviewOut, CleaningReportOut,
    ColumnInfoOut, AggregateConfig, AggregatePreviewOut, AggregateSaveOut,
    AnalyticsOut, CustomerAnalysisIn,
)
from data_hub.cleaning import apply_cleaning
from data_hub.preview import get_preview, get_stats
from data_hub.aggregation import aggregate_dataframe, get_column_info
from data_hub.analytics import get_analytics
from data_hub.customer_analytics import analyze_customer_data
from notifications.service import create_notification

router = APIRouter(prefix="/api/data", tags=["data"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
LEGACY_UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"

ALLOWED_EXT = (".csv", ".xlsx", ".xls")


def _safe_upload_name(filename: str) -> str:
    raw_name = (filename or "").strip()
    if not raw_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid file name")

    safe_name = Path(raw_name).name.replace("\\", "/").split("/")[-1]
    safe_name = "".join(ch for ch in safe_name if ch.isalnum() or ch in "._- ")
    safe_name = safe_name.strip()

    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid file name")

    return safe_name


def _read_dataframe(filename: str, raw: bytes) -> pd.DataFrame:
    name = (filename or "").lower()
    if not name.endswith(ALLOWED_EXT):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only CSV or Excel files are allowed")
    try:
        if name.endswith(".csv"):
            return pd.read_csv(io.BytesIO(raw))
        return pd.read_excel(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Could not read file: {e}")


def _build_config(preset, drop_empty_rows, duplicates, missing, outliers, strings) -> dict:
    return {
        "preset": preset, "drop_empty_rows": drop_empty_rows,
        "duplicates": duplicates, "missing": missing,
        "outliers": outliers, "strings": strings,
    }


def _resolve_upload_path(raw_path: str | None) -> Path:
    if not raw_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Dataset file path missing")
    p = Path(raw_path)
    upload_roots = [UPLOAD_DIR.resolve(), LEGACY_UPLOAD_DIR.resolve()]
    if p.is_absolute():
        resolved = p.resolve()
        if not any(resolved.is_relative_to(root) for root in upload_roots):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid dataset storage path")
        return resolved

    has_uploads_prefix = bool(p.parts and p.parts[0].lower() == "uploads")
    if has_uploads_prefix:
        p = Path(*p.parts[1:])
    search_roots = upload_roots[::-1] if has_uploads_prefix else upload_roots
    candidates = []
    for root in search_roots:
        resolved = (root / p).resolve()
        if any(resolved.is_relative_to(allowed_root) for allowed_root in upload_roots):
            candidates.append(resolved)
            if resolved.exists():
                return resolved
    if not candidates:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid dataset storage path")
    return candidates[0]


def _safe_upload_path(prefix: str, original_name: str | None = None) -> Path:
    safe_name = _safe_upload_name(original_name or "dataset.csv")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(safe_name).stem or "dataset"
    return UPLOAD_DIR / f"{prefix}_{stamp}_{stem}.csv"


def _get_owned_dataset(db: Session, dataset_id: int, user: User) -> Dataset:
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your dataset")
    return ds


def _load_cleaned(ds: Dataset) -> pd.DataFrame:
    if not ds.cleaned_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No cleaned file for this dataset")
    p = _resolve_upload_path(ds.cleaned_path)
    if not p.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cleaned file missing on disk")
    return pd.read_csv(p)


@router.get("/analytics", response_model=AnalyticsOut)
def analytics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_analytics(db, user)


@router.post("/datasets/{dataset_id}/customer-insights")
def customer_insights(
    dataset_id: int,
    config: CustomerAnalysisIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = _get_owned_dataset(db, dataset_id, user)
    df = _load_cleaned(dataset)
    try:
        result = analyze_customer_data(
            df,
            config.customer_column,
            config.date_column,
            config.monetary_column,
            config.transaction_column,
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error))
    return {"dataset_filename": dataset.filename, **result}


@router.post("/preview-clean", response_model=CleaningPreviewOut)
async def preview_clean(
    file: UploadFile = File(...),
    preset: str = Form("standard"),
    drop_empty_rows: bool = Form(True),
    duplicates: str = Form("drop_all"),
    missing: str = Form("auto"),
    outliers: str = Form("keep"),
    strings: str = Form("trim"),
    user: User = Depends(get_current_user),
):
    raw = await file.read()
    df = _read_dataframe(file.filename or "", raw)
    if df.empty:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty")
    cfg = _build_config(preset, drop_empty_rows, duplicates, missing, outliers, strings)
    cleaned, report = apply_cleaning(df, cfg)
    prev = get_preview(cleaned, limit=30)
    return CleaningPreviewOut(
        columns=prev["columns"], rows=prev["rows"],
        total_rows=prev["total_rows"], preview_rows=prev["preview_rows"],
        report=report,
    )


@router.post("/upload-with-config", response_model=DatasetOut, status_code=201)
async def upload_with_config(
    file: UploadFile = File(...),
    preset: str = Form("standard"),
    drop_empty_rows: bool = Form(True),
    duplicates: str = Form("drop_all"),
    missing: str = Form("auto"),
    outliers: str = Form("keep"),
    strings: str = Form("trim"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    raw = await file.read()
    df = _read_dataframe(file.filename or "", raw)
    if df.empty:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty")
    cfg = _build_config(preset, drop_empty_rows, duplicates, missing, outliers, strings)
    cleaned, report = apply_cleaning(df, cfg)

    safe_name = _safe_upload_name(file.filename or "dataset.csv")
    clean_path = _safe_upload_path("cleaned", safe_name)
    cleaned.to_csv(clean_path, index=False)

    ds = Dataset(
        user_email=user.email, filename=safe_name,
        row_count=int(cleaned.shape[0]), column_count=int(cleaned.shape[1]),
        status="processed", cleaned_path=str(clean_path),
    )
    db.add(ds); db.flush()
    cr = CleaningReport(
        dataset_id=ds.id, preset=report["preset"],
        config_json=json.dumps(report["config"]),
        log_json=json.dumps(report["log"]),
        stats_json=json.dumps({
            "stats_before": report["stats_before"], "stats_after": report["stats_after"],
            "rows_removed": report["rows_removed"], "columns_removed": report["columns_removed"],
            "missing_filled": report["missing_filled"],
        }),
    )
    db.add(cr)

    create_notification(
        db, user.id, "dataset_upload",
        f"Dataset uploaded: {file.filename}",
        f"{ds.row_count} rows × {ds.column_count} cols · preset: {report['preset']}",
        f"/dataset/dataset.html?id={ds.id}",
        user.email,
    )
    db.commit(); db.refresh(ds)
    return ds


@router.post("/upload", response_model=DatasetOut, status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    raw = await file.read()
    df = _read_dataframe(file.filename or "", raw)
    if df.empty:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty")
    cleaned, report = apply_cleaning(df, {"preset": "standard"})
    safe_name = _safe_upload_name(file.filename or "dataset.csv")
    clean_path = _safe_upload_path("cleaned", safe_name)
    cleaned.to_csv(clean_path, index=False)
    ds = Dataset(
        user_email=user.email, filename=safe_name,
        row_count=int(cleaned.shape[0]), column_count=int(cleaned.shape[1]),
        status="processed", cleaned_path=str(clean_path),
    )
    db.add(ds); db.flush()
    cr = CleaningReport(
        dataset_id=ds.id, preset=report["preset"],
        config_json=json.dumps(report["config"]),
        log_json=json.dumps(report["log"]),
        stats_json=json.dumps({
            "stats_before": report["stats_before"], "stats_after": report["stats_after"],
            "rows_removed": report["rows_removed"], "columns_removed": report["columns_removed"],
            "missing_filled": report["missing_filled"],
        }),
    )
    db.add(cr)
    create_notification(
        db, user.id, "dataset_upload",
        f"Dataset uploaded: {file.filename}",
        f"{ds.row_count} rows × {ds.column_count} cols",
        f"/dataset/dataset.html?id={ds.id}",
        user.email,
    )
    db.commit(); db.refresh(ds)
    return ds


@router.get("/datasets", response_model=list[DatasetOut])
def list_datasets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Dataset).order_by(Dataset.created_at.desc())
    if user.role == "admin":
        return q.all()
    return q.filter(Dataset.user_email == user.email).all()


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_dataset(db, dataset_id, user)


@router.get("/datasets/{dataset_id}/preview", response_model=PreviewOut)
def preview_dataset(dataset_id: int, limit: int = 20, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = _get_owned_dataset(db, dataset_id, user)
    df = _load_cleaned(ds)
    limit = max(5, min(limit, 200))
    return get_preview(df, limit=limit)


@router.get("/datasets/{dataset_id}/stats", response_model=StatsOut)
def dataset_stats(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = _get_owned_dataset(db, dataset_id, user)
    df = _load_cleaned(ds)
    return get_stats(df)


@router.get("/datasets/{dataset_id}/report", response_model=CleaningReportOut)
def get_cleaning_report(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = _get_owned_dataset(db, dataset_id, user)
    cr = db.query(CleaningReport).filter(CleaningReport.dataset_id == ds.id).first()
    if not cr:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No cleaning report for this dataset")
    stats = json.loads(cr.stats_json or "{}")
    return CleaningReportOut(
        dataset_id=ds.id, preset=cr.preset,
        config=json.loads(cr.config_json or "{}"),
        log=json.loads(cr.log_json or "[]"),
        stats_before=stats.get("stats_before", {}),
        stats_after=stats.get("stats_after", {}),
        rows_removed=stats.get("rows_removed", 0),
        columns_removed=stats.get("columns_removed", 0),
        missing_filled=stats.get("missing_filled", 0),
        created_at=cr.created_at,
    )


@router.get("/datasets/{dataset_id}/download")
def download_dataset(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = _get_owned_dataset(db, dataset_id, user)
    if not ds.cleaned_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No cleaned file available")
    p = _resolve_upload_path(ds.cleaned_path)
    if not p.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File missing on disk")
    base = Path(ds.filename).stem if ds.filename else f"dataset_{ds.id}"
    return FileResponse(path=str(p), media_type="text/csv", filename=f"cleaned_{base}.csv")


@router.get("/datasets/{dataset_id}/column-info", response_model=ColumnInfoOut)
def dataset_column_info(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = _get_owned_dataset(db, dataset_id, user)
    df = _load_cleaned(ds)
    info = get_column_info(df)
    return ColumnInfoOut(**info)


@router.post("/datasets/{dataset_id}/aggregate-preview", response_model=AggregatePreviewOut)
def aggregate_preview(dataset_id: int, config: AggregateConfig, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = _get_owned_dataset(db, dataset_id, user)
    df = _load_cleaned(ds)
    try:
        agg_df, report = aggregate_dataframe(df, config.date_column, config.value_columns, config.frequency, config.method)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    prev = get_preview(agg_df, limit=50)
    return AggregatePreviewOut(
        columns=prev["columns"], rows=prev["rows"],
        total_rows=prev["total_rows"], preview_rows=prev["preview_rows"],
        report=report,
    )


@router.post("/datasets/{dataset_id}/aggregate-save", response_model=AggregateSaveOut, status_code=201)
def aggregate_save(dataset_id: int, config: AggregateConfig, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = _get_owned_dataset(db, dataset_id, user)
    df = _load_cleaned(ds)
    try:
        agg_df, report = aggregate_dataframe(df, config.date_column, config.value_columns, config.frequency, config.method)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(ds.filename).stem if ds.filename else f"dataset_{ds.id}"
    new_name = f"aggregated_{config.frequency}_{config.method}_{base}.csv"
    path = UPLOAD_DIR / f"{stamp}_{new_name}"
    agg_df.to_csv(path, index=False)

    new_ds = Dataset(
        user_email=user.email, filename=new_name,
        row_count=int(agg_df.shape[0]), column_count=int(agg_df.shape[1]),
        status="aggregated", cleaned_path=str(path),
    )
    db.add(new_ds); db.flush()

    agg_rec = Aggregation(
        source_dataset_id=ds.id, result_dataset_id=new_ds.id,
        date_column=config.date_column,
        value_columns_json=json.dumps(config.value_columns),
        frequency=config.frequency, method=config.method,
        report_json=json.dumps(report), created_by=user.email,
    )
    db.add(agg_rec)
    create_notification(
        db, user.id, "aggregation",
        f"Aggregated: {new_name}",
        f"{config.frequency} · {config.method} → {new_ds.row_count} rows",
        f"/dataset/dataset.html?id={new_ds.id}",
        user.email,
    )
    db.commit(); db.refresh(new_ds)
    return AggregateSaveOut(dataset=DatasetOut.model_validate(new_ds), report=report)


@router.delete("/datasets/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = _get_owned_dataset(db, dataset_id, user)
    if ds.cleaned_path:
        try:
            p = _resolve_upload_path(ds.cleaned_path)
            if p.exists():
                p.unlink()
        except HTTPException:
            pass
    db.delete(ds); db.commit()
    return None
