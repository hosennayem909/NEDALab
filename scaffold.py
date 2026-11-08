"""
NEDA LAB - Project Scaffold Generator
"""

from pathlib import Path

ROOT_NAME = "NEDALAB"

PROTECTED = {
    "backend/.env",
}

FILES = {

    # ==================== BACKEND ====================

    "backend/requirements.txt": """fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
psycopg2-binary==2.9.9
pydantic==2.9.2
pydantic-settings==2.5.2
python-multipart==0.0.12
passlib==1.7.4
bcrypt==4.0.1
PyJWT==2.9.0
python-dotenv==1.0.1
pandas==2.2.3
openpyxl==3.1.5
email-validator==2.2.0
statsmodels==0.14.4
""",

    "backend/.env": """DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/neda_lab
JWT_SECRET=change_this_to_a_long_random_string
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:5500,http://localhost:5500
""",

    "backend/core/__init__.py": "",

    "backend/core/config.py": """from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    CORS_ORIGINS: str = "http://localhost:3000"

    class Config:
        env_file = ".env"

    @property
    def cors_list(self):
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


settings = Settings()
""",

    "backend/core/database.py": """from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
""",

    "backend/core/security.py": """from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext
from core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_EXPIRE_MINUTES
    )
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
""",

    "backend/core/deps.py": """from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt

from core.database import get_db
from core.security import decode_token
from auth.models import User

bearer_scheme = HTTPBearer()


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(creds.credentials)
        user_id = payload.get("sub")
        if user_id is None:
            raise ValueError("missing sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def require_role(*allowed: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user
    return checker
""",

    "backend/auth/__init__.py": "",

    "backend/auth/models.py": """from sqlalchemy import Column, Integer, String, DateTime, func
from core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(180), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="viewer")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
""",

    "backend/auth/schemas.py": """from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Literal

Role = Literal["admin", "researcher", "viewer"]


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    role: Role = "viewer"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: Role
    created_at: datetime

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
""",

    "backend/auth/routes.py": """from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import hash_password, verify_password, create_access_token
from core.deps import get_current_user
from auth.models import User
from auth.schemas import RegisterIn, LoginIn, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.email == payload.email).first()
    if exists:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
""",

    "backend/data_hub/__init__.py": "",

    "backend/data_hub/models.py": """from sqlalchemy import Column, Integer, String, DateTime, func
from core.database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(180), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    row_count = Column(Integer, default=0)
    column_count = Column(Integer, default=0)
    status = Column(String(30), default="processed")
    cleaned_path = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
""",

    "backend/data_hub/schemas.py": """from pydantic import BaseModel, EmailStr
from datetime import datetime


class DatasetOut(BaseModel):
    id: int
    user_email: EmailStr
    filename: str
    row_count: int
    column_count: int
    status: str
    cleaned_path: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
""",

    "backend/data_hub/cleaning.py": """import pandas as pd


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    stats = {}
    before = len(df)
    df = df.drop_duplicates()
    stats["duplicates_removed"] = before - len(df)
    stats["missing_before"] = int(df.isna().sum().sum())
    df = df.ffill().bfill()

    for col in df.columns:
        if df[col].isna().any():
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(0)
            else:
                df[col] = df[col].fillna("")

    stats["missing_after"] = int(df.isna().sum().sum())
    stats["rows_after"] = len(df)
    stats["columns_after"] = len(df.columns)
    return df, stats
""",

    "backend/data_hub/routes.py": """from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import datetime
import io
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from data_hub.schemas import DatasetOut
from data_hub.cleaning import clean_dataframe

router = APIRouter(prefix="/api/data", tags=["data"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/upload", response_model=DatasetOut, status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    name = (file.filename or "").lower()
    if not (name.endswith(".csv") or name.endswith(".xlsx") or name.endswith(".xls")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only CSV or Excel files are allowed")

    raw = await file.read()

    try:
        if name.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(raw))
        else:
            df = pd.read_excel(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Could not read file: {e}")

    if df.empty:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty")

    df, _stats = clean_dataframe(df)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_name = f"cleaned_{stamp}_{Path(name).stem}.csv"
    clean_path = UPLOAD_DIR / clean_name
    df.to_csv(clean_path, index=False)

    ds = Dataset(
        user_email=user.email,
        filename=file.filename,
        row_count=int(df.shape[0]),
        column_count=int(df.shape[1]),
        status="processed",
        cleaned_path=str(clean_path),
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


@router.get("/datasets", response_model=list[DatasetOut])
def list_datasets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Dataset).order_by(Dataset.created_at.desc())
    if user.role == "admin":
        return q.all()
    return q.filter(Dataset.user_email == user.email).all()


@router.delete("/datasets/{dataset_id}", status_code=204)
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your dataset")
    db.delete(ds)
    db.commit()
    return None
""",

    "backend/workspace/__init__.py": "",

    "backend/workspace/models.py": """from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func, UniqueConstraint
from core.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    slug = Column(String(180), unique=True, nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_member_ws_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False, default="viewer")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
""",

    "backend/workspace/schemas.py": """from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Literal

WorkspaceRole = Literal["admin", "researcher", "viewer"]


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)


class WorkspaceOut(BaseModel):
    id: int
    name: str
    slug: str
    owner_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class MemberAdd(BaseModel):
    email: EmailStr
    role: WorkspaceRole = "viewer"


class MemberOut(BaseModel):
    id: int
    user_id: int
    user_name: str
    user_email: EmailStr
    role: WorkspaceRole
    created_at: datetime


class WorkspaceDetail(BaseModel):
    workspace: WorkspaceOut
    members: list[MemberOut]
    my_role: WorkspaceRole | None = None
""",

    "backend/workspace/rbac.py": """from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from auth.models import User
from workspace.models import Workspace, Member


def get_workspace_by_slug(db: Session, slug: str) -> Workspace:
    ws = db.query(Workspace).filter(Workspace.slug == slug).first()
    if not ws:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return ws


def get_membership(db: Session, workspace_id: int, user_id: int) -> Member | None:
    return (
        db.query(Member)
        .filter(Member.workspace_id == workspace_id, Member.user_id == user_id)
        .first()
    )


def require_workspace_access(db: Session, ws: Workspace, user: User) -> Member | None:
    if user.role == "admin":
        return get_membership(db, ws.id, user.id)
    m = get_membership(db, ws.id, user.id)
    if not m:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this workspace")
    return m


def require_workspace_admin(db: Session, ws: Workspace, user: User) -> Member | None:
    if user.role == "admin":
        return get_membership(db, ws.id, user.id)
    m = get_membership(db, ws.id, user.id)
    if not m or m.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Workspace admin required")
    return m
""",

    "backend/workspace/routes.py": """import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from workspace.models import Workspace, Member
from workspace.schemas import (
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceDetail,
    MemberAdd,
    MemberOut,
)
from workspace.rbac import (
    get_workspace_by_slug,
    get_membership,
    require_workspace_access,
    require_workspace_admin,
)

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


def make_slug(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _member_to_out(db: Session, m: Member) -> MemberOut:
    u = db.query(User).filter(User.id == m.user_id).first()
    return MemberOut(
        id=m.id,
        user_id=m.user_id,
        user_name=u.name if u else "Unknown",
        user_email=u.email if u else "unknown@local",
        role=m.role,
        created_at=m.created_at,
    )


@router.post("/create", response_model=WorkspaceOut, status_code=201)
def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    base_slug = make_slug(payload.name)
    if not base_slug:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid workspace name")

    slug = base_slug
    i = 1
    while db.query(Workspace).filter(Workspace.slug == slug).first():
        i += 1
        slug = f"{base_slug}-{i}"

    ws = Workspace(name=payload.name, slug=slug, owner_id=user.id)
    db.add(ws)
    db.flush()
    db.add(Member(workspace_id=ws.id, user_id=user.id, role="admin"))
    db.commit()
    db.refresh(ws)
    return ws


@router.get("/list", response_model=list[WorkspaceOut])
def list_workspaces(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == "admin":
        return db.query(Workspace).order_by(Workspace.created_at.desc()).all()

    ws_ids = [m.workspace_id for m in db.query(Member).filter(Member.user_id == user.id).all()]
    if not ws_ids:
        return []
    return (
        db.query(Workspace)
        .filter(Workspace.id.in_(ws_ids))
        .order_by(Workspace.created_at.desc())
        .all()
    )


@router.get("/{slug}", response_model=WorkspaceDetail)
def get_workspace(
    slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ws = get_workspace_by_slug(db, slug)
    my_membership = require_workspace_access(db, ws, user)
    members = db.query(Member).filter(Member.workspace_id == ws.id).all()
    return WorkspaceDetail(
        workspace=WorkspaceOut.model_validate(ws),
        members=[_member_to_out(db, m) for m in members],
        my_role=my_membership.role if my_membership else "admin",
    )


@router.post("/{slug}/members", response_model=MemberOut, status_code=201)
def add_member(
    slug: str,
    payload: MemberAdd,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ws = get_workspace_by_slug(db, slug)
    require_workspace_admin(db, ws, user)

    target = db.query(User).filter(User.email == payload.email).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User with that email not found")

    existing = get_membership(db, ws.id, target.id)
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User is already a member")

    m = Member(workspace_id=ws.id, user_id=target.id, role=payload.role)
    db.add(m)
    db.commit()
    db.refresh(m)
    return _member_to_out(db, m)


@router.delete("/{slug}/members/{member_id}", status_code=204)
def remove_member(
    slug: str,
    member_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ws = get_workspace_by_slug(db, slug)
    require_workspace_admin(db, ws, user)

    m = db.query(Member).filter(Member.id == member_id, Member.workspace_id == ws.id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if m.user_id == ws.owner_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot remove workspace owner")

    db.delete(m)
    db.commit()
    return None
""",

    # ==================== FORECASTING (with fix) ====================

    "backend/forecasting/__init__.py": "",

    "backend/forecasting/models.py": """from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from core.database import Base


class ForecastModel(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    model_type = Column(String(50), nullable=False)
    target_column = Column(String(150), nullable=False)
    params_json = Column(Text, nullable=True)
    metrics_json = Column(Text, nullable=True)
    trained_by = Column(String(180), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False, index=True)
    horizon = Column(Integer, nullable=False)
    predictions_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
""",

    "backend/forecasting/schemas.py": """from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Literal, Any

ModelType = Literal["linear", "moving_average", "arima"]


class TrainIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    dataset_id: int
    target_column: str = Field(min_length=1, max_length=150)
    model_type: ModelType = "linear"
    name: str | None = None


class ModelOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)

    id: int
    dataset_id: int
    name: str
    model_type: ModelType
    target_column: str
    params_json: str | None = None
    metrics_json: str | None = None
    trained_by: str
    created_at: datetime


class PredictIn(BaseModel):
    horizon: int = Field(ge=1, le=365)


class PredictOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: int
    horizon: int
    predictions: list[float]
    model_type: ModelType
    metrics: dict[str, Any]
""",

    "backend/forecasting/engine.py": """import numpy as np
import pandas as pd


def _prepare_series(df: pd.DataFrame, target_column: str) -> np.ndarray:
    if target_column not in df.columns:
        raise ValueError(f"Column '{target_column}' not found in dataset")
    series = pd.to_numeric(df[target_column], errors="coerce").dropna().reset_index(drop=True)
    if len(series) < 10:
        raise ValueError("Not enough numeric data points (min 10 required)")
    return series.to_numpy(dtype=float)


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    mask = y_true != 0
    mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100) if mask.any() else None
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 4) if mape is not None else None,
    }


def train_linear(series: np.ndarray) -> tuple[dict, dict, np.ndarray]:
    n = len(series)
    x = np.arange(n, dtype=float)
    a, b = np.polyfit(x, series, 1)
    y_pred = a * x + b
    return {"slope": float(a), "intercept": float(b)}, _metrics(series, y_pred), y_pred


def train_moving_average(series: np.ndarray, window: int = 3) -> tuple[dict, dict, np.ndarray]:
    n = len(series)
    y_pred = np.zeros(n)
    for i in range(n):
        start = max(0, i - window)
        y_pred[i] = float(np.mean(series[start:i])) if i > 0 else series[i]
    return {"window": window}, _metrics(series, y_pred), y_pred


def train_arima(series: np.ndarray) -> tuple[dict, dict, np.ndarray]:
    from statsmodels.tsa.arima.model import ARIMA
    order = (1, 1, 1)
    model = ARIMA(series, order=order)
    fit = model.fit()
    y_pred = np.asarray(fit.fittedvalues, dtype=float)
    return {"order": list(order)}, _metrics(series, y_pred), y_pred


def train_model(series: np.ndarray, model_type: str) -> tuple[dict, dict, np.ndarray]:
    if model_type == "linear":
        return train_linear(series)
    if model_type == "moving_average":
        return train_moving_average(series)
    if model_type == "arima":
        return train_arima(series)
    raise ValueError(f"Unknown model type: {model_type}")


def predict_future(series: np.ndarray, model_type: str, params: dict, horizon: int) -> list[float]:
    if model_type == "linear":
        a = params["slope"]
        b = params["intercept"]
        n = len(series)
        return [round(float(a * (n + i) + b), 4) for i in range(horizon)]

    if model_type == "moving_average":
        window = params["window"]
        history = list(series.astype(float))
        preds = []
        for _ in range(horizon):
            nxt = float(np.mean(history[-window:]))
            preds.append(round(nxt, 4))
            history.append(nxt)
        return preds

    if model_type == "arima":
        from statsmodels.tsa.arima.model import ARIMA
        order = tuple(params["order"])
        model = ARIMA(series, order=order)
        fit = model.fit()
        forecast = fit.forecast(steps=horizon)
        return [round(float(v), 4) for v in forecast]

    raise ValueError(f"Unknown model type: {model_type}")
""",

    "backend/forecasting/routes.py": """import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from forecasting.models import ForecastModel, Forecast
from forecasting.schemas import TrainIn, ModelOut, PredictIn, PredictOut
from forecasting.engine import _prepare_series, train_model, predict_future

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


def _load_dataset_df(ds: Dataset) -> pd.DataFrame:
    if not ds.cleaned_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Dataset has no cleaned file")
    path = Path(ds.cleaned_path)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cleaned file missing on disk")
    return pd.read_csv(path)


@router.post("/train", response_model=ModelOut, status_code=201)
def train(
    payload: TrainIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ds = db.query(Dataset).filter(Dataset.id == payload.dataset_id).first()
    if not ds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")

    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your dataset")

    df = _load_dataset_df(ds)

    try:
        series = _prepare_series(df, payload.target_column)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    try:
        params, metrics, _ = train_model(series, payload.model_type)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Training failed: {e}")

    name = payload.name or f"{payload.model_type} on {payload.target_column}"
    m = ForecastModel(
        dataset_id=ds.id,
        name=name,
        model_type=payload.model_type,
        target_column=payload.target_column,
        params_json=json.dumps(params),
        metrics_json=json.dumps(metrics),
        trained_by=user.email,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.get("/models", response_model=list[ModelOut])
def list_models(
    dataset_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(ForecastModel).order_by(ForecastModel.created_at.desc())
    if dataset_id is not None:
        q = q.filter(ForecastModel.dataset_id == dataset_id)
    if user.role != "admin":
        q = q.filter(ForecastModel.trained_by == user.email)
    return q.all()


@router.get("/models/{model_id}", response_model=ModelOut)
def get_model(
    model_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    m = db.query(ForecastModel).filter(ForecastModel.id == model_id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    if user.role != "admin" and m.trained_by != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your model")
    return m


@router.post("/models/{model_id}/predict", response_model=PredictOut)
def predict(
    model_id: int,
    payload: PredictIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    m = db.query(ForecastModel).filter(ForecastModel.id == model_id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    if user.role != "admin" and m.trained_by != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your model")

    ds = db.query(Dataset).filter(Dataset.id == m.dataset_id).first()
    if not ds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")

    df = _load_dataset_df(ds)
    series = _prepare_series(df, m.target_column)

    params = json.loads(m.params_json or "{}")
    metrics = json.loads(m.metrics_json or "{}")

    try:
        preds = predict_future(series, m.model_type, params, payload.horizon)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Prediction failed: {e}")

    f = Forecast(
        model_id=m.id,
        horizon=payload.horizon,
        predictions_json=json.dumps(preds),
    )
    db.add(f)
    db.commit()

    return PredictOut(
        model_id=m.id,
        horizon=payload.horizon,
        predictions=preds,
        model_type=m.model_type,
        metrics=metrics,
    )


@router.delete("/models/{model_id}", status_code=204)
def delete_model(
    model_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    m = db.query(ForecastModel).filter(ForecastModel.id == model_id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    if user.role != "admin" and m.trained_by != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your model")
    db.delete(m)
    db.commit()
    return None
""",

    "backend/main.py": """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import Base, engine
from auth import models as auth_models                # noqa: F401
from data_hub import models as data_models            # noqa: F401
from workspace import models as ws_models             # noqa: F401
from forecasting import models as forecast_models     # noqa: F401
from auth.routes import router as auth_router
from data_hub.routes import router as data_router
from workspace.routes import router as workspace_router
from forecasting.routes import router as forecast_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="NEDA LAB API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(data_router)
app.include_router(workspace_router)
app.include_router(forecast_router)


@app.get("/")
def root():
    return {"status": "ok", "service": "NEDA LAB API"}
""",

    # ==================== FRONTEND ====================

    "frontend/shared/api.js": """const API_BASE = "http://127.0.0.1:8000";

async function apiFetch(path, { method = "GET", body = null, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const token = localStorage.getItem("neda_token");
    if (token) headers["Authorization"] = "Bearer " + token;
  }
  const res = await fetch(API_BASE + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

async function apiUpload(path, formData) {
  const token = localStorage.getItem("neda_token");
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: token ? { Authorization: "Bearer " + token } : {},
    body: formData,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Upload failed");
  return data;
}
""",

    "frontend/shared/auth.js": """function saveSession(token, user) {
  localStorage.setItem("neda_token", token);
  localStorage.setItem("neda_user", JSON.stringify(user));
}

function getUser() {
  const raw = localStorage.getItem("neda_user");
  return raw ? JSON.parse(raw) : null;
}

function logout() {
  localStorage.removeItem("neda_token");
  localStorage.removeItem("neda_user");
  window.location.href = "../login/login.html";
}

function requireAuth() {
  if (!localStorage.getItem("neda_token")) {
    window.location.href = "../login/login.html";
  }
}
""",

    "frontend/register/register.html": """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>NEDA LAB - Register</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
  <div class="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-xl">
    <h1 class="text-2xl font-bold mb-1">Create account</h1>
    <p class="text-sm text-slate-400 mb-6">Join NEDA LAB research platform</p>

    <form id="registerForm" class="space-y-4">
      <div>
        <label class="block text-sm mb-1">Full name</label>
        <input id="name" required class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
      </div>
      <div>
        <label class="block text-sm mb-1">Email</label>
        <input id="email" type="email" required class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
      </div>
      <div>
        <label class="block text-sm mb-1">Password</label>
        <input id="password" type="password" minlength="6" required class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
      </div>
      <div>
        <label class="block text-sm mb-1">Role</label>
        <select id="role" class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700">
          <option value="viewer">Viewer</option>
          <option value="researcher">Researcher</option>
          <option value="admin">Admin</option>
        </select>
      </div>

      <button class="w-full py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 font-medium">Register</button>
      <p id="msg" class="text-sm text-red-400 hidden"></p>
    </form>

    <p class="text-sm text-slate-400 mt-6 text-center">
      Already have an account?
      <a href="../login/login.html" class="text-indigo-400 hover:underline">Login</a>
    </p>
  </div>

  <script src="../shared/api.js"></script>
  <script src="../shared/auth.js"></script>
  <script src="register.js"></script>
</body>
</html>
""",

    "frontend/register/register.js": """document.getElementById("registerForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("msg");
  msg.classList.add("hidden");

  const payload = {
    name: document.getElementById("name").value.trim(),
    email: document.getElementById("email").value.trim(),
    password: document.getElementById("password").value,
    role: document.getElementById("role").value,
  };

  try {
    const data = await apiFetch("/api/auth/register", {
      method: "POST",
      body: payload,
      auth: false,
    });
    saveSession(data.access_token, data.user);
    window.location.href = "../dashboard/dashboard.html";
  } catch (err) {
    msg.textContent = err.message;
    msg.classList.remove("hidden");
  }
});
""",

    "frontend/login/login.html": """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>NEDA LAB - Login</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
  <div class="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-xl">
    <h1 class="text-2xl font-bold mb-1">Welcome back</h1>
    <p class="text-sm text-slate-400 mb-6">Sign in to NEDA LAB</p>

    <form id="loginForm" class="space-y-4">
      <div>
        <label class="block text-sm mb-1">Email</label>
        <input id="email" type="email" required class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
      </div>
      <div>
        <label class="block text-sm mb-1">Password</label>
        <input id="password" type="password" required class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
      </div>

      <button class="w-full py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 font-medium">Login</button>
      <p id="msg" class="text-sm text-red-400 hidden"></p>
    </form>

    <p class="text-sm text-slate-400 mt-6 text-center">
      No account?
      <a href="../register/register.html" class="text-indigo-400 hover:underline">Register</a>
    </p>
  </div>

  <script src="../shared/api.js"></script>
  <script src="../shared/auth.js"></script>
  <script src="login.js"></script>
</body>
</html>
""",

    "frontend/login/login.js": """document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("msg");
  msg.classList.add("hidden");

  const payload = {
    email: document.getElementById("email").value.trim(),
    password: document.getElementById("password").value,
  };

  try {
    const data = await apiFetch("/api/auth/login", {
      method: "POST",
      body: payload,
      auth: false,
    });
    saveSession(data.access_token, data.user);
    window.location.href = "../dashboard/dashboard.html";
  } catch (err) {
    msg.textContent = err.message;
    msg.classList.remove("hidden");
  }
});
""",

    "frontend/dashboard/dashboard.html": """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>NEDA LAB - Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-950 text-slate-100">

  <nav class="bg-slate-900 border-b border-slate-800 px-6 py-3 flex justify-between items-center">
    <div class="flex items-center gap-6">
      <h1 class="text-lg font-bold tracking-wide">NEDA LAB</h1>
      <a href="dashboard.html" class="text-sm text-indigo-400 font-medium">Dashboard</a>
      <a href="../workspace/workspace.html" class="text-sm text-slate-400 hover:text-slate-200">Workspaces</a>
    </div>
    <div class="flex items-center gap-4">
      <span id="userInfo" class="text-sm text-slate-400"></span>
      <button id="logoutBtn" class="text-sm px-3 py-1 rounded-lg bg-red-600 hover:bg-red-500">Logout</button>
    </div>
  </nav>

  <main class="max-w-6xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
    <section class="lg:col-span-1 bg-slate-900 border border-slate-800 rounded-2xl p-6 h-fit">
      <h2 class="text-lg font-semibold mb-4">Upload dataset</h2>
      <form id="uploadForm" class="space-y-4">
        <input id="fileInput" type="file" accept=".csv,.xlsx,.xls" required
          class="block w-full text-sm text-slate-300 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-indigo-600 file:text-white hover:file:bg-indigo-500 cursor-pointer" />
        <button class="w-full py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 font-medium">Upload &amp; Clean</button>
        <p id="uploadMsg" class="text-sm hidden"></p>
      </form>
      <div class="mt-6 pt-6 border-t border-slate-800 text-xs text-slate-500 space-y-1">
        <p>Accepted: CSV, XLSX, XLS</p>
        <p>Auto: remove duplicates + fill missing values</p>
      </div>
    </section>

    <section class="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6">
      <h2 class="text-lg font-semibold mb-4">Your datasets</h2>
      <div id="datasetList" class="space-y-3">
        <p class="text-sm text-slate-500">Loading...</p>
      </div>
    </section>
  </main>

  <script src="../shared/api.js"></script>
  <script src="../shared/auth.js"></script>
  <script src="dashboard.js"></script>
</body>
</html>
""",

    "frontend/dashboard/dashboard.js": """requireAuth();

const user = getUser();
if (user) {
  document.getElementById("userInfo").textContent = user.name + " (" + user.role + ")";
}
document.getElementById("logoutBtn").addEventListener("click", logout);

async function loadDatasets() {
  const list = document.getElementById("datasetList");
  try {
    const data = await apiFetch("/api/data/datasets");
    if (!data.length) {
      list.innerHTML = '<p class="text-sm text-slate-500">No datasets yet. Upload one to begin.</p>';
      return;
    }
    list.innerHTML = data.map(ds => {
      const date = new Date(ds.created_at).toLocaleString();
      return `
        <div class="border border-slate-800 rounded-xl p-4 flex justify-between items-center gap-4">
          <div class="min-w-0">
            <p class="font-medium truncate">${ds.filename}</p>
            <p class="text-xs text-slate-400">${date} - ${ds.user_email}</p>
          </div>
          <div class="text-right shrink-0">
            <p class="text-sm">${ds.row_count} rows - ${ds.column_count} cols</p>
            <span class="text-xs px-2 py-0.5 rounded-full bg-emerald-900 text-emerald-300">${ds.status}</span>
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    list.innerHTML = '<p class="text-sm text-red-400">' + err.message + '</p>';
  }
}

document.getElementById("uploadForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("uploadMsg");
  const fileInput = document.getElementById("fileInput");
  if (!fileInput.files.length) return;

  msg.className = "text-sm text-slate-400";
  msg.textContent = "Uploading and cleaning...";
  msg.classList.remove("hidden");

  const fd = new FormData();
  fd.append("file", fileInput.files[0]);

  try {
    const data = await apiUpload("/api/data/upload", fd);
    msg.className = "text-sm text-emerald-400";
    msg.textContent = "Cleaned: " + data.row_count + " rows, " + data.column_count + " cols";
    fileInput.value = "";
    loadDatasets();
  } catch (err) {
    msg.className = "text-sm text-red-400";
    msg.textContent = err.message;
  }
});

loadDatasets();
""",

    "frontend/workspace/workspace.html": """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>NEDA LAB - Workspaces</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-950 text-slate-100">

  <nav class="bg-slate-900 border-b border-slate-800 px-6 py-3 flex justify-between items-center">
    <div class="flex items-center gap-6">
      <h1 class="text-lg font-bold tracking-wide">NEDA LAB</h1>
      <a href="../dashboard/dashboard.html" class="text-sm text-slate-400 hover:text-slate-200">Dashboard</a>
      <a href="workspace.html" class="text-sm text-indigo-400 font-medium">Workspaces</a>
    </div>
    <div class="flex items-center gap-4">
      <span id="userInfo" class="text-sm text-slate-400"></span>
      <button id="logoutBtn" class="text-sm px-3 py-1 rounded-lg bg-red-600 hover:bg-red-500">Logout</button>
    </div>
  </nav>

  <main class="max-w-6xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
    <section class="lg:col-span-1 space-y-6">
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6">
        <h2 class="text-lg font-semibold mb-4">Create workspace</h2>
        <form id="createForm" class="space-y-4">
          <input id="wsName" placeholder="Workspace name" required minlength="2"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          <button class="w-full py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 font-medium">Create</button>
          <p id="createMsg" class="text-sm hidden"></p>
        </form>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6">
        <h2 class="text-lg font-semibold mb-4">Your workspaces</h2>
        <div id="wsList" class="space-y-2">
          <p class="text-sm text-slate-500">Loading...</p>
        </div>
      </div>
    </section>

    <section class="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6">
      <div id="wsDetail">
        <p class="text-sm text-slate-500">Select a workspace to view details.</p>
      </div>
    </section>
  </main>

  <script src="../shared/api.js"></script>
  <script src="../shared/auth.js"></script>
  <script src="workspace.js"></script>
</body>
</html>
""",

    "frontend/workspace/workspace.js": """requireAuth();

const user = getUser();
if (user) {
  document.getElementById("userInfo").textContent = user.name + " (" + user.role + ")";
}
document.getElementById("logoutBtn").addEventListener("click", logout);

let currentSlug = null;

async function loadWorkspaces() {
  const list = document.getElementById("wsList");
  try {
    const data = await apiFetch("/api/workspace/list");
    if (!data.length) {
      list.innerHTML = '<p class="text-sm text-slate-500">No workspaces yet.</p>';
      return;
    }
    list.innerHTML = data.map(ws => `
      <button data-slug="${ws.slug}"
        class="ws-item block w-full text-left px-3 py-2 rounded-lg border border-slate-800 hover:border-indigo-500 hover:bg-slate-800/50 transition">
        <p class="font-medium">${ws.name}</p>
        <p class="text-xs text-slate-500">/${ws.slug}</p>
      </button>
    `).join("");

    list.querySelectorAll(".ws-item").forEach(el => {
      el.addEventListener("click", () => openWorkspace(el.dataset.slug));
    });
  } catch (err) {
    list.innerHTML = '<p class="text-sm text-red-400">' + err.message + '</p>';
  }
}

async function openWorkspace(slug) {
  currentSlug = slug;
  const box = document.getElementById("wsDetail");
  box.innerHTML = '<p class="text-sm text-slate-500">Loading...</p>';

  try {
    const data = await apiFetch("/api/workspace/" + slug);
    const ws = data.workspace;
    const members = data.members;
    const myRole = data.my_role || "viewer";
    const canManage = myRole === "admin" || (user && user.role === "admin");

    box.innerHTML = `
      <div class="flex justify-between items-start mb-6">
        <div>
          <h2 class="text-xl font-bold">${ws.name}</h2>
          <p class="text-xs text-slate-500">/${ws.slug}</p>
        </div>
        <span class="text-xs px-2 py-1 rounded-full bg-indigo-900 text-indigo-300">Your role: ${myRole}</span>
      </div>

      <h3 class="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">Members</h3>
      <div class="space-y-2 mb-6">
        ${members.map(m => `
          <div class="flex justify-between items-center border border-slate-800 rounded-lg px-3 py-2">
            <div>
              <p class="text-sm font-medium">${m.user_name}</p>
              <p class="text-xs text-slate-500">${m.user_email}</p>
            </div>
            <div class="flex items-center gap-3">
              <span class="text-xs px-2 py-0.5 rounded-full bg-slate-800">${m.role}</span>
              ${canManage ? `<button data-mid="${m.id}" class="remove-member text-xs text-red-400 hover:text-red-300">Remove</button>` : ""}
            </div>
          </div>
        `).join("")}
      </div>

      ${canManage ? `
        <h3 class="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">Add member</h3>
        <form id="addForm" class="flex flex-col sm:flex-row gap-3">
          <input id="addEmail" type="email" required placeholder="user@example.com"
            class="flex-1 px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          <select id="addRole" class="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700">
            <option value="viewer">Viewer</option>
            <option value="researcher">Researcher</option>
            <option value="admin">Admin</option>
          </select>
          <button class="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 font-medium">Add</button>
        </form>
        <p id="addMsg" class="text-sm mt-2 hidden"></p>
      ` : ""}
    `;

    if (canManage) {
      box.querySelector("#addForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const msg = box.querySelector("#addMsg");
        msg.classList.add("hidden");

        try {
          await apiFetch("/api/workspace/" + slug + "/members", {
            method: "POST",
            body: {
              email: box.querySelector("#addEmail").value.trim(),
              role: box.querySelector("#addRole").value,
            },
          });
          openWorkspace(slug);
        } catch (err) {
          msg.className = "text-sm text-red-400 mt-2";
          msg.textContent = err.message;
          msg.classList.remove("hidden");
        }
      });

      box.querySelectorAll(".remove-member").forEach(btn => {
        btn.addEventListener("click", async () => {
          if (!confirm("Remove this member?")) return;
          try {
            await apiFetch("/api/workspace/" + slug + "/members/" + btn.dataset.mid, {
              method: "DELETE",
            });
            openWorkspace(slug);
          } catch (err) {
            alert(err.message);
          }
        });
      });
    }
  } catch (err) {
    box.innerHTML = '<p class="text-sm text-red-400">' + err.message + '</p>';
  }
}

document.getElementById("createForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("createMsg");
  msg.classList.add("hidden");

  try {
    const ws = await apiFetch("/api/workspace/create", {
      method: "POST",
      body: { name: document.getElementById("wsName").value.trim() },
    });
    document.getElementById("wsName").value = "";
    await loadWorkspaces();
    openWorkspace(ws.slug);
  } catch (err) {
    msg.className = "text-sm text-red-400";
    msg.textContent = err.message;
    msg.classList.remove("hidden");
  }
});

loadWorkspaces();
""",
}


def main():
    base = Path(__file__).parent / ROOT_NAME
    print(f"\n>> Creating project at: {base}\n")

    created, skipped = 0, 0

    for rel_path, content in FILES.items():
        target = base / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)

        if rel_path in PROTECTED and target.exists():
            print(f"  = protected (skipped): {rel_path}")
            skipped += 1
            continue

        if target.exists() and target.read_text(encoding="utf-8") == content:
            print(f"  = skipped (unchanged): {rel_path}")
            skipped += 1
            continue

        target.write_text(content, encoding="utf-8")
        action = "updated" if target.exists() else "created"
        print(f"  + {action}: {rel_path}")
        created += 1

    print(f"\n>> Done.  {created} written,  {skipped} unchanged.")
    print(f">> Project root: {base}\n")


if __name__ == "__main__":
    main()