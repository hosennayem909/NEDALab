import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from workspace.models import Workspace, Member
from workspace.schemas import (
    WorkspaceCreate, WorkspaceOut, WorkspaceDetail,
    MemberAdd, MemberOut,
)
from workspace.rbac import (
    get_workspace_by_slug, get_membership,
    require_workspace_access, require_workspace_admin,
)
from notifications.service import create_notification

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


def make_slug(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _member_to_out(db: Session, m: Member) -> MemberOut:
    u = db.query(User).filter(User.id == m.user_id).first()
    return MemberOut(
        id=m.id, user_id=m.user_id,
        user_name=u.name if u else "Unknown",
        user_email=u.email if u else "unknown@local",
        role=m.role, created_at=m.created_at,
    )


@router.post("/create", response_model=WorkspaceOut, status_code=201)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    base_slug = make_slug(payload.name)
    if not base_slug:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid workspace name")

    slug = base_slug
    i = 1
    while db.query(Workspace).filter(Workspace.slug == slug).first():
        i += 1
        slug = f"{base_slug}-{i}"

    ws = Workspace(name=payload.name, slug=slug, owner_id=user.id)
    db.add(ws); db.flush()
    db.add(Member(workspace_id=ws.id, user_id=user.id, role="admin"))
    create_notification(
        db, user.id, "workspace_created",
        f"Workspace created: {payload.name}",
        f"slug: /{slug}",
        "/workspace/workspace.html",
        user.email,
    )
    db.commit(); db.refresh(ws)
    return ws


@router.get("/list", response_model=list[WorkspaceOut])
def list_workspaces(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == "admin":
        return db.query(Workspace).order_by(Workspace.created_at.desc()).all()
    ws_ids = [m.workspace_id for m in db.query(Member).filter(Member.user_id == user.id).all()]
    if not ws_ids:
        return []
    return db.query(Workspace).filter(Workspace.id.in_(ws_ids)).order_by(Workspace.created_at.desc()).all()


@router.get("/{slug}", response_model=WorkspaceDetail)
def get_workspace(slug: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ws = get_workspace_by_slug(db, slug)
    my_membership = require_workspace_access(db, ws, user)
    members = db.query(Member).filter(Member.workspace_id == ws.id).all()
    return WorkspaceDetail(
        workspace=WorkspaceOut.model_validate(ws),
        members=[_member_to_out(db, m) for m in members],
        my_role=my_membership.role if my_membership else "admin",
    )


@router.post("/{slug}/members", response_model=MemberOut, status_code=201)
def add_member(slug: str, payload: MemberAdd, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ws = get_workspace_by_slug(db, slug)
    require_workspace_admin(db, ws, user)

    target = db.query(User).filter(User.email == payload.email).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User with that email not found")

    existing = get_membership(db, ws.id, target.id)
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User is already a member")

    m = Member(workspace_id=ws.id, user_id=target.id, role=payload.role)
    db.add(m); db.flush()

    # Notify target user
    create_notification(
        db, target.id, "member_added",
        f"Added to workspace: {ws.name}",
        f"Role: {payload.role} · by {user.email}",
        "/workspace/workspace.html",
        user.email,
    )
    # Notify actor (self)
    create_notification(
        db, user.id, "member_invited",
        f"Invited {target.email} to {ws.name}",
        f"Role: {payload.role}",
        "/workspace/workspace.html",
        user.email,
    )
    db.commit(); db.refresh(m)
    return _member_to_out(db, m)


@router.delete("/{slug}/members/{member_id}", status_code=204)
def remove_member(slug: str, member_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ws = get_workspace_by_slug(db, slug)
    require_workspace_admin(db, ws, user)
    m = db.query(Member).filter(Member.id == member_id, Member.workspace_id == ws.id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if m.user_id == ws.owner_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot remove workspace owner")
    db.delete(m); db.commit()
    return None
