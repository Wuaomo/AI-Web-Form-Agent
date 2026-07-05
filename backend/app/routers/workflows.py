"""Workflow template API endpoints."""

from fastapi import APIRouter

from app.schemas import WorkflowTemplateResponse
from app.workflow_templates import list_workflow_templates

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("/templates", response_model=list[WorkflowTemplateResponse])
def list_templates() -> list[dict[str, object]]:
    """Return static workflow templates for UI selection."""

    return list_workflow_templates(include_disabled=True)
