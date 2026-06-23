"""Helpers for recording task action logs."""

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ActionLog


def create_log(
    task_id: int,
    step: int,
    action: str,
    message: str,
    status: str,
    db: Session | None = None,
) -> ActionLog:
    """Create an action log and return the persisted record.

    Callers that already have a database session can pass it in so the log is
    committed with the surrounding task operation. Other callers can use the
    helper directly and let it manage a short-lived session.
    """

    log = ActionLog(
        task_id=task_id,
        step=step,
        action=action,
        message=message,
        status=status,
    )

    if db is not None:
        db.add(log)
        db.flush()
        return log

    with SessionLocal() as session:
        session.add(log)
        session.commit()
        session.refresh(log)
        session.expunge(log)

    return log
