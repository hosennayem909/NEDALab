import io
import json
import shutil
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from data_hub.versioning.models import DatasetVersion
from data_hub.versioning.schemas import (
    VersionOut, CreateVersionIn, RestoreIn, CompareOut,
)

router = APIRouter(prefix="/api/versions", tags=["versioning"])

VERSION_DIR = Path("uploads/versions")
VERSION_DIR.mkdir(parents=True, exist_ok=True)


def _get_owned_dataset(db: Session, dataset_id: int, user: User) -> Dataset:
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(403, "Not your dataset")
    return ds


def _snapshot_file(ds: Dataset, version_num: int) -> str:
    """Copy current cleaned file to version snapshot folder."""
    if not ds.cleaned_path:
        raise HTTPException(400, "Dataset has no file to snapshot")
    src = Path(ds.cleaned_path)
    if not src.exists():
        raise HTTPException(404, "Source file missing")

    base = src.stem
    ext = src.suffix
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = VERSION_DIR / f"v{version_num}_{stamp}_{base}{ext}"

    shutil.copy2(src, dest)
    return str(dest)


@router.post("/create", response_model=VersionOut, status_code=201)
def create_version(
    payload: CreateVersionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ds = _get_owned_dataset(db, payload.dataset_id, user)

    # Next version number
    last = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == ds.id)
        .order_by(DatasetVersion.version_number.desc())
        .first()
    )
    next_num = (last.version_number + 1) if last else 1
    parent_id = last.id if last else None

    snapshot_path = _snapshot_file(ds, next_num)

    v = DatasetVersion(
        dataset_id=ds.id,
        version_number=next_num,
        parent_version_id=parent_id,
        snapshot_path=snapshot_path,
        row_count=ds.row_count or 0,
        column_count=ds.column_count or 0,
        change_type=payload.change_type,
        change_description=payload.change_description,
        change_details_json=json.dumps({
            "filename": ds.filename,
            "status": ds.status,
        }),
        created_by=user.email,
    )
    db.add(v); db.commit(); db.refresh(v)
    return v


@router.get("/dataset/{dataset_id}/list", response_model=list[VersionOut])
def list_versions(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ds = _get_owned_dataset(db, dataset_id, user)
    q = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == ds.id)
        .order_by(DatasetVersion.version_number.desc())
    )
    return q.all()


@router.get("/{version_id}/download")
def download_version(
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    v = db.query(DatasetVersion).filter(DatasetVersion.id == version_id).first()
    if not v:
        raise HTTPException(404, "Version not found")
    ds = _get_owned_dataset(db, v.dataset_id, user)

    p = Path(v.snapshot_path)
    if not p.exists():
        raise HTTPException(404, "Snapshot file missing")

    fname = f"{Path(ds.filename).stem}_v{v.version_number}{p.suffix}"
    return FileResponse(path=str(p), media_type="text/csv", filename=fname)


@router.post("/restore", response_model=VersionOut, status_code=201)
def restore_version(
    payload: RestoreIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    v = db.query(DatasetVersion).filter(DatasetVersion.id == payload.version_id).first()
    if not v:
        raise HTTPException(404, "Version not found")

    ds = _get_owned_dataset(db, v.dataset_id, user)

    src = Path(v.snapshot_path)
    if not src.exists():
        raise HTTPException(404, "Snapshot file missing")

    # Snapshot current state before restoring
    last = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == ds.id)
        .order_by(DatasetVersion.version_number.desc())
        .first()
    )
    next_num = (last.version_number + 1) if last else 1

    current_snapshot = _snapshot_file(ds, next_num)

    # Overwrite current cleaned file with version file
    if ds.cleaned_path:
        target = Path(ds.cleaned_path)
        shutil.copy2(src, target)

        # Update row/col counts
        try:
            df = pd.read_csv(target)
            ds.row_count = int(df.shape[0])
            ds.column_count = int(df.shape[1])
        except Exception:
            pass

    # Log a new version row (the restored state)
    new_v = DatasetVersion(
        dataset_id=ds.id,
        version_number=next_num,
        parent_version_id=v.id,
        snapshot_path=current_snapshot,
        row_count=ds.row_count or 0,
        column_count=ds.column_count or 0,
        change_type="restore",
        change_description=payload.change_description or f"Restored from v{v.version_number}",
        change_details_json=json.dumps({
            "restored_from_version_id": v.id,
            "restored_from_version_num": v.version_number,
        }),
        created_by=user.email,
    )
    db.add(new_v); db.commit(); db.refresh(new_v)
    return new_v


@router.get("/{version_id}/download-snapshot")
def download_snapshot(version_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    v = db.query(DatasetVersion).filter(DatasetVersion.id == version_id).first()
    if not v:
        raise HTTPException(404, "Version not found")
    ds = _get_owned_dataset(db, v.dataset_id, user)
    p = Path(v.snapshot_path)
    if not p.exists():
        raise HTTPException(404, "Snapshot file missing")
    return FileResponse(path=str(p), media_type="text/csv", filename=p.name)


@router.delete("/{version_id}", status_code=204)
def delete_version(version_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    v = db.query(DatasetVersion).filter(DatasetVersion.id == version_id).first()
    if not v:
        raise HTTPException(404, "Version not found")
    _get_owned_dataset(db, v.dataset_id, user)
    # Remove snapshot file
    try:
        p = Path(v.snapshot_path)
        if p.exists():
            p.unlink()
    except Exception:
        pass
    db.delete(v); db.commit()
    return None


@router.get("/compare", response_model=CompareOut)
def compare_versions(
    version_a_id: int,
    version_b_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    va = db.query(DatasetVersion).filter(DatasetVersion.id == version_a_id).first()
    vb = db.query(DatasetVersion).filter(DatasetVersion.id == version_b_id).first()
    if not va or not vb:
        raise HTTPException(404, "Version(s) not found")
    if va.dataset_id != vb.dataset_id:
        raise HTTPException(400, "Versions belong to different datasets")
    _get_owned_dataset(db, va.dataset_id, user)

    pa = Path(va.snapshot_path)
    pb = Path(vb.snapshot_path)
    if not pa.exists() or not pb.exists():
        raise HTTPException(404, "Snapshot file(s) missing")

    df_a = pd.read_csv(pa)
    df_b = pd.read_csv(pb)

    cols_a = set(df_a.columns)
    cols_b = set(df_b.columns)

    added = sorted(cols_b - cols_a)
    removed = sorted(cols_a - cols_b)
    common = sorted(cols_a & cols_b)

    # Row diff (if same row count and same index)
    rows_changed = 0
    diff_preview = []
    try:
        if df_a.shape == df_b.shape:
            for i in range(min(len(df_a), 50)):
                row_a = df_a.iloc[i]
                row_b = df_b.iloc[i]
                diff_cols = [c for c in common if str(row_a[c]) != str(row_b[c])]
                if diff_cols:
                    rows_changed += 1
                    diff_preview.append({
                        "row": i,
                        "changed_columns": diff_cols,
                        "before": {c: str(row_a[c]) for c in diff_cols[:5]},
                        "after": {c: str(row_b[c]) for c in diff_cols[:5]},
                    })
    except Exception:
        pass

    return CompareOut(
        version_a=VersionOut.model_validate(va),
        version_b=VersionOut.model_validate(vb),
        rows_changed=rows_changed,
        columns_added=added,
        columns_removed=removed,
        columns_common=common,
        diff_preview=diff_preview,
    )
