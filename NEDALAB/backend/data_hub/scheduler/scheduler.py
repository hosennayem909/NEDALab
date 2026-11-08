"""Background scheduler using APScheduler."""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timezone
from pathlib import Path
import shutil
import json

from sqlalchemy.orm import Session
from core.database import SessionLocal
from data_hub.models import Dataset
from data_hub.versioning.models import DatasetVersion
from data_hub.scheduler.models import ScheduledTask, TaskRun
from data_hub.export.excel import export_dataset_excel
from data_hub.preview import get_stats
import pandas as pd


_scheduler: BackgroundScheduler | None = None
VERSION_DIR = Path("uploads/versions")
VERSION_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR = Path("uploads/exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def parse_schedule(schedule: str) -> CronTrigger:
    s = schedule.strip().lower()
    if s == "daily":
        return CronTrigger(hour=9, minute=0)
    if s == "weekly":
        return CronTrigger(day_of_week="mon", hour=9, minute=0)
    if s == "monthly":
        return CronTrigger(day=1, hour=9, minute=0)
    if s == "hourly":
        return CronTrigger(minute=0)
    # cron expression "min hour day month dow"
    parts = s.split()
    if len(parts) == 5:
        return CronTrigger(minute=parts[0], hour=parts[1], day=parts[2],
                           month=parts[3], day_of_week=parts[4])
    # default fallback
    return CronTrigger(hour=9, minute=0)


def run_task(task_id: int):
    """Execute a task. Called by scheduler or manually."""
    db: Session = SessionLocal()
    try:
        task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
        if not task:
            return

        run = TaskRun(task_id=task.id, status="running")
        db.add(run); db.commit(); db.refresh(run)

        try:
            if task.task_type == "snapshot":
                _run_snapshot(db, task)
            elif task.task_type == "export_excel":
                _run_export_excel(db, task)
            elif task.task_type == "export_pdf":
                _run_export_pdf(db, task)
            else:
                raise ValueError(f"Unknown task_type: {task.task_type}")

            run.status = "success"
            run.message = "Completed successfully"
        except Exception as e:
            run.status = "failed"
            run.message = f"{type(e).__name__}: {str(e)}"

        run.completed_at = datetime.now(timezone.utc)
        task.last_run_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def _run_snapshot(db: Session, task: ScheduledTask):
    if not task.dataset_id:
        raise ValueError("Snapshot task requires dataset_id")
    ds = db.query(Dataset).filter(Dataset.id == task.dataset_id).first()
    if not ds or not ds.cleaned_path:
        raise ValueError("Dataset or file not found")

    src = Path(ds.cleaned_path)
    if not src.exists():
        raise ValueError("Dataset file missing")

    last = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == ds.id)
        .order_by(DatasetVersion.version_number.desc())
        .first()
    )
    next_num = (last.version_number + 1) if last else 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = VERSION_DIR / f"v{next_num}_auto_{stamp}_{src.name}"
    shutil.copy2(src, dest)

    v = DatasetVersion(
        dataset_id=ds.id,
        version_number=next_num,
        parent_version_id=last.id if last else None,
        snapshot_path=str(dest),
        row_count=ds.row_count or 0,
        column_count=ds.column_count or 0,
        change_type="scheduled_snapshot",
        change_description=f"Auto snapshot by task '{task.name}'",
        change_details_json=json.dumps({"task_id": task.id}),
        created_by="scheduler@nedalab.local",
    )
    db.add(v); db.commit()


def _run_export_excel(db: Session, task: ScheduledTask):
    if not task.dataset_id:
        raise ValueError("Export task requires dataset_id")
    ds = db.query(Dataset).filter(Dataset.id == task.dataset_id).first()
    if not ds or not ds.cleaned_path:
        raise ValueError("Dataset not found")

    df = pd.read_csv(ds.cleaned_path)
    try:
        stats = get_stats(df)
    except Exception:
        stats = None

    xls_bytes = export_dataset_excel(df, ds.filename, None, stats)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = EXPORT_DIR / f"auto_export_{task.id}_{stamp}.xlsx"
    out.write_bytes(xls_bytes)


def _run_export_pdf(db: Session, task: ScheduledTask):
    from data_hub.export.pdf import export_dataset_pdf
    if not task.dataset_id:
        raise ValueError("Export task requires dataset_id")
    ds = db.query(Dataset).filter(Dataset.id == task.dataset_id).first()
    if not ds or not ds.cleaned_path:
        raise ValueError("Dataset not found")

    df = pd.read_csv(ds.cleaned_path)
    try:
        stats = get_stats(df)
    except Exception:
        stats = None

    pdf_bytes = export_dataset_pdf(ds.filename, df.shape, list(df.columns), stats)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = EXPORT_DIR / f"auto_export_{task.id}_{stamp}.pdf"
    out.write_bytes(pdf_bytes)


def start_scheduler():
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.start()

    db = SessionLocal()
    try:
        tasks = db.query(ScheduledTask).filter(ScheduledTask.enabled == True).all()  # noqa: E712
        for t in tasks:
            try:
                trigger = parse_schedule(t.schedule)
                _scheduler.add_job(
                    run_task,
                    trigger=trigger,
                    args=[t.id],
                    id=f"task_{t.id}",
                    replace_existing=True,
                )
            except Exception as e:
                print(f"[scheduler] Failed to schedule task {t.id}: {e}")
    finally:
        db.close()


def register_task(task_id: int, schedule: str):
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        start_scheduler()

    try:
        if _scheduler.get_job(f"task_{task_id}"):
            _scheduler.remove_job(f"task_{task_id}")

        trigger = parse_schedule(schedule)
        _scheduler.add_job(
            run_task,
            trigger=trigger,
            args=[task_id],
            id=f"task_{task_id}",
            replace_existing=True,
        )
    except Exception as e:
        print(f"[scheduler] register failed: {e}")


def unregister_task(task_id: int):
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.remove_job(f"task_{task_id}")
    except Exception:
        pass


def get_next_run(task_id: int):
    global _scheduler
    if _scheduler is None:
        return None
    try:
        job = _scheduler.get_job(f"task_{task_id}")
        return job.next_run_time if job else None
    except Exception:
        return None
