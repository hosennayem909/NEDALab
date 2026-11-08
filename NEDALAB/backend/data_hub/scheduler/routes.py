import traceback
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.scheduler.models import ScheduledTask, TaskRun
from data_hub.scheduler.schemas import TaskIn, TaskUpdate, TaskOut, TaskRunOut
from data_hub.scheduler.scheduler import (
    start_scheduler, register_task, unregister_task, run_task, get_next_run,
)

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(payload: TaskIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = ScheduledTask(
        user_id=user.id,
        name=payload.name.strip(),
        task_type=payload.task_type,
        dataset_id=payload.dataset_id,
        schedule=payload.schedule,
        config_json=payload.config_json,
        enabled=payload.enabled,
    )
    db.add(t); db.commit(); db.refresh(t)

    if t.enabled:
        register_task(t.id, t.schedule)
        nxt = get_next_run(t.id)
        if nxt:
            t.next_run_at = nxt
            db.commit(); db.refresh(t)

    return t


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(ScheduledTask).order_by(ScheduledTask.created_at.desc())
    if user.role != "admin":
        q = q.filter(ScheduledTask.user_id == user.id)
    return q.all()


@router.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not t:
        raise HTTPException(404, "Task not found")
    if user.role != "admin" and t.user_id != user.id:
        raise HTTPException(403, "Not your task")

    if payload.name is not None: t.name = payload.name.strip()
    if payload.schedule is not None: t.schedule = payload.schedule
    if payload.enabled is not None: t.enabled = payload.enabled
    if payload.config_json is not None: t.config_json = payload.config_json

    db.commit(); db.refresh(t)

    if t.enabled:
        register_task(t.id, t.schedule)
    else:
        unregister_task(t.id)
    return t


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not t:
        raise HTTPException(404, "Task not found")
    if user.role != "admin" and t.user_id != user.id:
        raise HTTPException(403, "Not your task")
    unregister_task(t.id)
    db.delete(t); db.commit()
    return None


@router.post("/tasks/{task_id}/run", response_model=TaskRunOut, status_code=201)
def run_task_now(task_id: int, background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not t:
        raise HTTPException(404, "Task not found")
    if user.role != "admin" and t.user_id != user.id:
        raise HTTPException(403, "Not your task")

    # Run synchronously in this request so user gets result immediately
    run_task(task_id)

    latest = (
        db.query(TaskRun)
        .filter(TaskRun.task_id == task_id)
        .order_by(TaskRun.id.desc())
        .first()
    )
    if not latest:
        raise HTTPException(500, "Run did not produce a record")
    return latest


@router.get("/tasks/{task_id}/runs", response_model=list[TaskRunOut])
def list_runs(task_id: int, limit: int = 20, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not t:
        raise HTTPException(404, "Task not found")
    if user.role != "admin" and t.user_id != user.id:
        raise HTTPException(403, "Not your task")

    q = (
        db.query(TaskRun)
        .filter(TaskRun.task_id == task_id)
        .order_by(TaskRun.id.desc())
        .limit(limit)
    )
    return q.all()
