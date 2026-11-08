from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from core.config import settings
from core.database import Base, engine
from auth import models as auth_models
from data_hub import models as data_models
from data_hub.versioning import models as version_models
from data_hub.scheduler import models as sched_models
from ml import models as ml_models
from ml.automl import models as automl_models
from workspace import models as ws_models
from forecasting import models as forecast_models
from notifications import models as notif_models
from entity import models as entity_models
from econometrics import models as econ_models
from auth.routes import router as auth_router
from data_hub.routes import router as data_router
from data_hub.stats_clean.routes import router as stats_router
from data_hub.adv_stats.routes import router as adv_stats_router
from data_hub.data_ops.routes import router as data_ops_router
from data_hub.export.routes import router as export_router
from data_hub.versioning.routes import router as version_router
from data_hub.scheduler.routes import router as scheduler_router
from data_hub.feature_eng.routes import router as feature_eng_router
from data_hub.quality.routes import router as quality_router
from data_hub.viz.routes import router as viz_router
from ml.routes import router as ml_router
from ml.prediction_routes import router as ml_pred_router
from ml.unsupervised_routes import router as ml_unsup_router
from ml.automl.routes import router as automl_router
from ml.automl.public_api_routes import router as public_api_router
from ml.online_routes import router as online_learning_router  # ⭐ নতুন
from workspace.routes import router as workspace_router
from forecasting.routes import router as forecast_router
from notifications.routes import router as notifications_router
from entity.routes import router as entity_router
from econometrics.routes import router as econ_router
from econometrics.stats_routes import router as stats_tests_router
from econometrics.panel_routes import router as panel_router
from econometrics.var_routes import router as var_router
from econometrics.deepen_routes import router as econ_deepen_router
from econometrics.hypothesis_routes import router as hypothesis_router
from data_hub.scheduler.scheduler import start_scheduler

Base.metadata.create_all(bind=engine)


def _ensure_optional_ml_columns() -> None:
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("SELECT 1 FROM ml_models LIMIT 1"))
            except Exception:
                return

            db_name = str(engine.url).lower()
            if "sqlite" in db_name:
                cols = conn.execute(text("PRAGMA table_info(ml_models)")).fetchall()
                has_model_path = any(row[1] == "model_path" for row in cols)
                if not has_model_path:
                    conn.execute(text("ALTER TABLE ml_models ADD COLUMN model_path VARCHAR(500)"))
            else:
                conn.execute(text("ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS model_path VARCHAR(500)"))
            conn.commit()
        print("[NEDA LAB] ml_models migration OK")
    except Exception as e:
        print(f"[NEDA LAB] migration warning: {e}")


_ensure_optional_ml_columns()

app = FastAPI(title="NEDA LAB API", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(data_router)
app.include_router(stats_router)
app.include_router(adv_stats_router)
app.include_router(data_ops_router)
app.include_router(export_router)
app.include_router(version_router)
app.include_router(scheduler_router)
app.include_router(feature_eng_router)
app.include_router(quality_router)
app.include_router(viz_router)
app.include_router(ml_router)
app.include_router(ml_pred_router)
app.include_router(ml_unsup_router)
app.include_router(automl_router)
app.include_router(public_api_router)
app.include_router(online_learning_router)  # ⭐ নতুন — Online Learning
app.include_router(workspace_router)
app.include_router(forecast_router)
app.include_router(notifications_router)
app.include_router(entity_router)
app.include_router(econ_router)
app.include_router(stats_tests_router)
app.include_router(panel_router)
app.include_router(var_router)
app.include_router(econ_deepen_router)
app.include_router(hypothesis_router)


@app.on_event("startup")
def _start_scheduler():
    try:
        start_scheduler()
        print("[NEDA LAB] Scheduler started")
    except Exception as e:
        print(f"[NEDA LAB] Scheduler failed to start: {e}")


@app.get("/")
def root():
    return {"status": "ok", "service": "NEDA LAB API", "version": "4.0.0"}