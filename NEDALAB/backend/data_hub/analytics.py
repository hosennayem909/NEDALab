from collections import Counter
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
import json

from auth.models import User
from data_hub.models import Dataset
from workspace.models import Workspace, Member
from forecasting.models import ForecastModel


def get_analytics(db: Session, user: User) -> dict:
    """Return all data needed for dashboard charts."""
    now = datetime.now(timezone.utc)
    is_admin = user.role == "admin"

    dataset_query = db.query(
        func.date(Dataset.created_at),
        func.count(Dataset.id),
    )
    if not is_admin:
        dataset_query = dataset_query.filter(Dataset.user_email == user.email)
    dataset_days = dataset_query.group_by(func.date(Dataset.created_at)).all()

    model_query = db.query(
        func.date(ForecastModel.created_at),
        ForecastModel.model_type,
        func.count(ForecastModel.id),
    )
    if not is_admin:
        model_query = model_query.filter(ForecastModel.trained_by == user.email)
    model_days = model_query.group_by(
        func.date(ForecastModel.created_at),
        ForecastModel.model_type,
    ).all()

    model_details_query = db.query(
        ForecastModel.name,
        ForecastModel.model_type,
        ForecastModel.metrics_json,
    )
    if not is_admin:
        model_details_query = model_details_query.filter(ForecastModel.trained_by == user.email)
    model_details = model_details_query.all()

    # Aggregate daily database counts into monthly charts and cumulative growth.
    dataset_counts_by_day = {
        str(day)[:10]: count for day, count in dataset_days if day is not None
    }
    dataset_counts_by_month = Counter()
    for day, count in dataset_counts_by_day.items():
        dataset_counts_by_month[day[:7]] += count

    model_counts_by_month = Counter()
    model_counts_by_type = Counter()
    for day, model_type, count in model_days:
        if day is not None:
            model_counts_by_month[str(day)[:7]] += count
        model_counts_by_type[model_type] += count

    month_starts = []
    current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for months_ago in range(5, -1, -1):
        month_index = current_month.year * 12 + current_month.month - 1 - months_ago
        month_starts.append(datetime(month_index // 12, month_index % 12 + 1, 1, tzinfo=timezone.utc))
    activity = [
        {
            "month": month.strftime("%b %Y"),
            "datasets": dataset_counts_by_month[month.strftime("%Y-%m")],
            "models": model_counts_by_month[month.strftime("%Y-%m")],
        }
        for month in month_starts
    ]

    model_distribution = [
        {"type": model_type, "count": count}
        for model_type, count in sorted(model_counts_by_type.items())
    ]

    growth = []
    cumulative = 0
    for day in sorted(dataset_counts_by_day):
        cumulative += dataset_counts_by_day[day]
        growth.append({"date": day, "cumulative": cumulative})

    # ============ Top 5 Best Models (by RMSE) ============
    models_with_rmse = []
    for name, model_type, metrics_json in model_details:
        try:
            metrics = json.loads(metrics_json or "{}")
            rmse = metrics.get("rmse")
            if rmse is not None:
                models_with_rmse.append({
                    "name": name[:30],
                    "rmse": rmse,
                    "model_type": model_type,
                })
        except Exception:
            continue

    models_with_rmse.sort(key=lambda x: x["rmse"])
    best_models = models_with_rmse[:5]

    if is_admin:
        ws_total = db.query(func.count(Workspace.id)).scalar() or 0
    else:
        ws_total = db.query(func.count(Member.id)).filter(Member.user_id == user.id).scalar() or 0

    return {
        "activity": activity,
        "model_distribution": model_distribution,
        "growth": growth,
        "best_models": best_models,
        "totals": {
            "datasets": sum(count for _, count in dataset_days),
            "models": sum(model_counts_by_type.values()),
            "workspaces": ws_total,
        },
    }
