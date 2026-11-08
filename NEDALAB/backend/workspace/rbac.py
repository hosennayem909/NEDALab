from fastapi import HTTPException, status
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


def _admin_member(ws: Workspace, user: User) -> Member:
    return Member(id=None, workspace_id=ws.id, user_id=user.id, role="admin")


def require_workspace_access(db: Session, ws: Workspace, user: User) -> Member | None:
    if user.role == "admin":
        return get_membership(db, ws.id, user.id) or _admin_member(ws, user)
    m = get_membership(db, ws.id, user.id)
    if not m:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this workspace")
    return m


def require_workspace_admin(db: Session, ws: Workspace, user: User) -> Member | None:
    if user.role == "admin":
        return get_membership(db, ws.id, user.id) or _admin_member(ws, user)
    m = get_membership(db, ws.id, user.id)
    if not m or m.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Workspace admin required")
    return m
