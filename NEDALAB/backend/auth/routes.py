from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import hash_password, verify_password, create_access_token
from core.deps import get_current_user
from auth.models import User
from auth.schemas import (
    RegisterIn, LoginIn, TokenOut, UserOut,
    ProfileUpdate, PasswordChange, PasswordResetIn, ProfileOut, ProfileStats,
)

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


# ---- Profile ----

@router.get("/profile", response_model=ProfileOut)
def get_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Lazy imports to avoid circular dependencies
    from data_hub.models import Dataset
    from workspace.models import Member
    from forecasting.models import ForecastModel

    ds_count = db.query(Dataset).filter(Dataset.user_email == user.email).count()
    model_count = db.query(ForecastModel).filter(ForecastModel.trained_by == user.email).count()
    ws_count = db.query(Member).filter(Member.user_id == user.id).count()

    if user.created_at:
        now = datetime.now(timezone.utc)
        created = user.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_days = max(0, (now - created).days)
    else:
        age_days = 0

    return ProfileOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
        stats=ProfileStats(
            datasets=ds_count,
            models=model_count,
            workspaces=ws_count,
            account_age_days=age_days,
        ),
    )


@router.put("/profile", response_model=UserOut)
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user.name = payload.name.strip()
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/password-reset")
def password_reset(payload: PasswordResetIn, db: Session = Depends(get_db)):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Passwords do not match")

    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No account found for this email")

    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "New password must be different from the current password")

    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    return {"message": "Password reset successful. You can now sign in with your new password."}


@router.post("/change-password", status_code=204)
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "New password must be different")
    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    return None
