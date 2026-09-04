"""Agent runtime API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AgentRun
from app.routers.workflows import _to_governed_compact_state
from app.services.agent_runtime.state_store import restore_governed_runtime_state

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


@router.get("/{run_id}", status_code=status.HTTP_200_OK)
def get_agent_run(run_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    """Return compact persisted AgentRun state."""

    run = db.get(AgentRun, run_id)
    if run is None or run.task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agent run state found for {run_id}.",
        )

    raw_state = restore_governed_runtime_state(db, task=run.task, run_id=run_id)
    if raw_state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agent run state found for {run_id}.",
        )
    return {"run_id": run_id, **_to_governed_compact_state(raw_state)}
