from sqlalchemy.orm import Session
from notifications.models import Notification


def create_notification(
    db: Session,
    user_id: int,
    ntype: str,
    title: str,
    message: str | None = None,
    link: str | None = None,
    actor_email: str | None = None,
) -> Notification:
    """Insert a notification row. Caller is responsible for commit."""
    n = Notification(
        user_id=user_id,
        type=ntype,
        title=title,
        message=message,
        link=link,
        actor_email=actor_email,
    )
    db.add(n)
    return n
