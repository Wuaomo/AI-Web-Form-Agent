"""Task-related API endpoints."""

import json
import logging
import re
import time
from typing import Literal, Union

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app import config
from app.database import BACKEND_DIR
from app.database import get_db
from app.job_constants import (
    JOB_TYPE_ANALYZE_FORM,
    JOB_TYPE_FILL_FORM,
    JOB_TYPE_MAP_FIELDS,
)
from app.models import ActionLog, AgentReview, FormField, Job, Profile, Screenshot, Task, TaskCheckpoint
from app.schemas import (
    ActionLogResponse,
    AgentReviewResponse,
    FieldVerificationResultResponse,
    FormFieldMappingUpdate,
    FormFieldResponse,
    JobResponse,
    LLMProvider,
    MappingConfirmationResponse,
    ProfileSkipItem,
    ProfileUpdateItem,
    ScreenshotResponse,
    SubmissionConfirmationResponse,
    TaskCheckpointResponse,
    TaskCreate,
    TaskLlmUsageResponse,
    WorkflowPlanRequest,
    WorkflowPlanResponse,
    TaskResponse,
)
from app.services.approval_gate_service import (
    create_approval_request,
    has_pending_approval,
    list_pending_approvals,
    latest_approved_request_for_action,
    latest_approved_request,
)
from app.services.browser_executor import (
    fill_form_and_capture_screenshot,
    open_url_and_capture_screenshot,
    submit_form_and_capture_screenshot,
)
from app.services.execution_verification_service import (
    save_verification_result,
    get_verification_summary_for_task,
)
from app.models import (
    FieldVerificationResult,
    VERIFICATION_STATUS_FAILED,
)
from app.services.field_mapper import (
    CUSTOM_PROFILE_KEY_PREFIX,
    get_profile_value,
    map_fields_by_rules,
    map_fields_with_llm_result,
)
from app.services.form_extractor import ExtractedFormAnalysis, extract_form_analysis
from app.services.page_extractor import extract_page
from app.services.research_summary import generate_research_summary
from app.services.form_analysis_cache import (
    read_form_analysis_cache,
    write_form_analysis_cache,
)
from app.services.browser_session import prepare_login_session
from app.services.policy_engine import (
    evaluate_field_action,
    evaluate_memory_write,
    evaluate_submit_action,
)
from app.services.llm_provider_config import (
    get_provider_setup_hint,
    is_provider_configured,
    resolve_llm_provider,
)
from app.services.llm_usage_service import (
    get_latest_llm_usage_log,
    list_llm_usage_logs,
    summarize_llm_usage,
)
from app.services.log_service import create_log
from app.services.job_queue import enqueue_job
from app.services.mapping_cache import save_user_mapping_override
from app.services.planner_service import (
    build_plan,
    plan_to_dict,
    resolve_plan_goal,
    save_plan,
)
from app.services.policy_answer_retrieval import apply_policy_answer_suggestions
from app.services.workflow_memory import save_confirmed_mappings_for_task
from app.services.checkpoint_service import list_checkpoints, write_checkpoint
from app.services.tool_registry import require_tool
from app.services.workflow_state_service import (
    InvalidWorkflowTransition,
    set_workflow_status,
    sync_legacy_status,
)
from app.services.workflow_trace_service import safe_create_span, safe_finish_span
from app.workflow_templates import require_enabled_template
from app.workflow_constants import (
    APPROVAL_STATUS_REJECTED,
    CHECKPOINT_FAILED,
    CHECKPOINT_SUCCESS,
    FAILURE_ANALYSIS_FAILED,
    FAILURE_BROWSER_FILL_FAILED,
    FAILURE_LLM_MAPPING_FAILED,
    POLICY_DECISION_BLOCK,
    POLICY_DECISION_REVIEW_REQUIRED,
    SPAN_PHASE_APPROVAL,
    SPAN_PHASE_BROWSER,
    SPAN_PHASE_EXTRACTION,
    SPAN_PHASE_MAPPING,
    SPAN_PHASE_PLANNING,
    SPAN_STATUS_FAILED,
    SPAN_STATUS_SUCCESS,
    WORKFLOW_STATUS_ANALYZING,
    WORKFLOW_STATUS_COMPLETED,
    WORKFLOW_STATUS_CREATED,
    WORKFLOW_STATUS_FAILED,
    WORKFLOW_STATUS_FILLING,
    WORKFLOW_STATUS_LOGIN_IN_PROGRESS,
    WORKFLOW_STATUS_LOGIN_REQUIRED,
    WORKFLOW_STATUS_MAPPING_READY,
    WORKFLOW_STATUS_READY_TO_FILL,
    WORKFLOW_STATUS_REVIEWING,
    WORKFLOW_STATUS_WAITING_APPROVAL,
    WORKFLOW_STAGE_ANALYSIS,
    WORKFLOW_STAGE_FILL,
    WORKFLOW_STAGE_MAPPING,
    WORKFLOW_TYPE_FORM_FILL,
    WORKFLOW_TYPE_JOB_RESEARCH_SUMMARY,
    WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE,
    WORKFLOW_TYPE_VENDOR_ONBOARDING,
    WORKFLOW_TYPE_WEB_DATA_EXTRACT,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

NON_FILLABLE_FIELD_TYPES = {
    "button",
    "file",
    "submit",
    "reset",
    "image",
}


def is_fillable_field(field: FormField) -> bool:
    """Return whether a field can receive profile or manual input."""

    return (field.field_type or "").lower() not in NON_FILLABLE_FIELD_TYPES


def field_display_name(field: FormField) -> str:
    """Return a useful human label for a form field."""

    return field.label or field.name or field.placeholder or field.selector


def get_missing_required_fields(fields: list[FormField]) -> list[FormField]:
    """Find required fields that still need a value before filling."""

    return [
        field
        for field in fields
        if field.required
        and is_fillable_field(field)
        and field.mapped_value in (None, "")
    ]


def missing_required_detail(fields: list[FormField]) -> str:
    """Build a concise API error for required fields needing user input."""

    missing_names = ", ".join(field_display_name(field) for field in fields)
    return f"Required fields need values: {missing_names}"


def normalize_profile_custom_key(raw_key: str | None) -> str:
    """Return a compact custom profile key safe to reuse in mappings."""

    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", raw_key or "").strip("_").lower()
    return re.sub(r"_+", "_", normalized)


BUILT_IN_PROFILE_WRITEBACK_KEYS = {
    "full_name",
    "email",
    "phone",
    "university",
    "major",
    "linkedin",
    "github",
    "self_intro",
}

DERIVED_PROFILE_WRITEBACK_KEYS = {"first_name", "last_name"}

ONE_TIME_FIELD_PHRASES = ("sign in", "sign-in")

ONE_TIME_FIELD_TOKENS = {
    "terms",
    "privacy",
    "agree",
    "consent",
    "password",
    "payment",
    "card",
    "billing",
    "checkout",
    "login",
    "signin",
    "otp",
    "verification",
    "verify",
    "submit",
    "reset",
    "file",
    "upload",
    "button",
}


def is_one_time_field(field: FormField) -> bool:
    """Return whether a field looks like a one-time or sensitive action."""

    parts = [field.label, field.name, field.placeholder, field.selector]
    haystack = " ".join(part for part in parts if part).lower()
    if any(phrase in haystack for phrase in ONE_TIME_FIELD_PHRASES):
        return True

    normalized = re.sub(r"[^a-z0-9]+", " ", haystack)
    tokens = {token for token in normalized.split() if token}
    return bool(tokens & ONE_TIME_FIELD_TOKENS)


def generate_deduped_custom_key(custom_values: dict[str, str], raw_key: str) -> str:
    """Generate a stable custom_values key, adding a numeric suffix if needed."""

    lowered = (raw_key or "").lower()
    if "portfolio" in lowered:
        raw_key = "code_portfolio" if "code" in lowered else "portfolio"

    base_key = normalize_profile_custom_key(raw_key) or "custom_value"
    if base_key not in custom_values:
        return base_key
    if custom_values.get(base_key) in (None, ""):
        return base_key

    suffix = 2
    while True:
        candidate = f"{base_key}_{suffix}"
        if candidate not in custom_values:
            return candidate
        suffix += 1


def split_full_name(full_name: str | None) -> tuple[str, str]:
    """Split a stored full name into simple first/last values."""

    if not full_name or not full_name.strip():
        return "", ""
    parts = full_name.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def get_task_or_404(task_id: int, db: Session) -> Task:
    """Return a task or raise a consistent not-found response."""

    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return task


def get_task_workflow_status(task: Task) -> str:
    """Return the workflow status while tolerating legacy rows."""

    if task.status and task.workflow_status and task.status != task.workflow_status:
        return task.status
    return task.workflow_status or task.status or WORKFLOW_STATUS_CREATED


def get_saved_task_plan(task: Task) -> dict[str, object]:
    """Return the saved task plan or convert malformed JSON into an API error."""

    try:
        return task.workflow_plan
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


def build_and_save_task_plan(db: Session, task: Task, *, goal: str) -> dict[str, object]:
    """Build and persist a deterministic workflow plan for one task."""

    planning_span_id = safe_create_span(
        task_id=task.id,
        phase=SPAN_PHASE_PLANNING,
        name="planning.build_plan",
        input={
            "workflow_type": task.workflow_type,
            "goal": goal,
        },
    )
    try:
        plan = build_plan(
            workflow_type=task.workflow_type,
            goal=goal,
        )
        for step in plan.steps:
            require_tool(step.tool)
        plan_payload = plan_to_dict(plan)
        save_plan(db, task, plan)
    except ValueError as exc:
        safe_finish_span(
            planning_span_id,
            status=SPAN_STATUS_FAILED,
            error_message=str(exc),
        )
        raise

    safe_finish_span(
        planning_span_id,
        status=SPAN_STATUS_SUCCESS,
        output={
            "step_count": len(plan_payload["steps"]),
            "step_ids": [step["step_id"] for step in plan_payload["steps"]],
        },
    )
    return plan_payload


def ensure_form_fill_workflow(task: Task) -> None:
    """Reject execution for workflow types that are not implemented yet."""

    if task.workflow_type not in {
        WORKFLOW_TYPE_FORM_FILL,
        WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE,
        WORKFLOW_TYPE_VENDOR_ONBOARDING,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow type not executable yet: {task.workflow_type}",
        )


def apply_workflow_status(task: Task, next_status: str, *, reason: str | None = None) -> None:
    """Apply a workflow transition and convert validation errors into API errors."""

    try:
        set_workflow_status(task, next_status, reason=reason)
    except InvalidWorkflowTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


def trace_usage_fields(task_id: int, db: Session) -> dict[str, object]:
    """Return the latest LLM usage summary suitable for workflow spans."""

    usage = get_latest_llm_usage_log(db, task_id)
    if usage is None:
        return {}
    return {
        "provider": usage.provider,
        "model": usage.model,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "estimated_cost": usage.estimated_cost,
        "metadata": {
            "fallback_used": usage.fallback_used,
            "cache_hit": usage.cache_hit,
            "cache_source": usage.cache_source,
        },
    }


def latest_rejected_request(task_id: int, step_name: str, db: Session):
    """Return the newest rejected approval for one task step."""

    from app.models import ApprovalRequest

    statement = (
        select(ApprovalRequest)
        .where(
            ApprovalRequest.task_id == task_id,
            ApprovalRequest.step_name == step_name,
            ApprovalRequest.status == APPROVAL_STATUS_REJECTED,
        )
        .order_by(ApprovalRequest.resolved_at.desc(), ApprovalRequest.id.desc())
    )
    return db.scalar(statement)


def filter_fillable_fields_by_policy(
    task: Task,
    fields: list[FormField],
    db: Session,
) -> tuple[list[FormField], list[FormField], list[FormField]]:
    """Return allowed fields plus blocked and approval-pending required fields."""

    allowed_fields: list[FormField] = []
    blocked_required_fields: list[FormField] = []
    pending_required_fields: list[FormField] = []

    for field in fields:
        if not field.mapped_value:
            continue
        policy = evaluate_field_action(
            label=field.label,
            name=field.name,
            field_type=field.field_type,
            selector=field.selector,
            confidence=field.confidence,
        )
        if policy.decision == POLICY_DECISION_BLOCK:
            if field.required and is_fillable_field(field):
                blocked_required_fields.append(field)
            continue
        if policy.decision == POLICY_DECISION_REVIEW_REQUIRED:
            step_name = f"fill_field:{field.id}"
            proposed_action = {
                "action": "fill_field",
                "field_id": field.id,
                "field_label": field_display_name(field),
                "mapped_value": str(field.mapped_value),
                "risk_type": policy.risk_type,
            }
            if latest_approved_request_for_action(
                db,
                task_id=task.id,
                step_name=step_name,
                proposed_action=proposed_action,
            ) is None:
                if not has_pending_approval(db, task_id=task.id, step_name=step_name):
                    create_approval_request(
                        db,
                        task_id=task.id,
                        step_name=step_name,
                        policy_decision=policy,
                        proposed_action=proposed_action,
                    )
                if field.required and is_fillable_field(field):
                    pending_required_fields.append(field)
                continue
        allowed_fields.append(field)

    return allowed_fields, blocked_required_fields, pending_required_fields


def get_task_field_or_404(task_id: int, field_id: int, db: Session) -> FormField:
    """Return a form field only when it belongs to the requested task."""

    statement = select(FormField).where(
        FormField.id == field_id,
        FormField.task_id == task_id,
    )
    field = db.scalar(statement)
    if field is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form field not found",
        )
    return field


def get_next_log_step(task_id: int, db: Session) -> int:
    """Return the next chronological action-log step for a task."""

    current_step = db.scalar(
        select(func.max(ActionLog.step)).where(ActionLog.task_id == task_id)
    )
    return (current_step or 0) + 1


def mark_login_required(task: Task, db: Session) -> None:
    """Pause analysis until the user explicitly starts manual login."""

    set_workflow_status(task, WORKFLOW_STATUS_LOGIN_REQUIRED, reason="analysis_requires_login")
    create_log(
        task_id=task.id,
        step=get_next_log_step(task.id, db),
        action="login_required",
        message=(
            "The target URL opened a login page. User confirmation is needed "
            "before opening a login browser."
        ),
        status="WAITING",
        db=db,
    )


def save_extracted_fields(
    task: Task,
    analysis: ExtractedFormAnalysis,
    db: Session,
) -> None:
    """Persist extracted fields and move the task to mapping-ready state."""

    db.execute(delete(FormField).where(FormField.task_id == task.id))
    for field in analysis.fields:
        db.add(
            FormField(
                task_id=task.id,
                element_ref=field.element_ref,
                form_title=field.form_title,
                section_title=field.section_title,
                label=field.label,
                selector=field.selector,
                field_type=field.field_type,
                placeholder=field.placeholder,
                name=field.name,
                html_id=field.html_id,
                current_value=field.current_value,
                field_options=json.dumps(field.options, ensure_ascii=False),
                required=field.required,
            )
        )

    set_workflow_status(task, WORKFLOW_STATUS_MAPPING_READY, reason="analysis_completed")
    create_log(
        task_id=task.id,
        step=get_next_log_step(task.id, db),
        action="extract_fields",
        message=f"Extracted and saved {len(analysis.fields)} form fields.",
        status="SUCCESS",
        db=db,
    )


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(task_data: TaskCreate, db: Session = Depends(get_db)) -> Task:
    """Create a task ready for form analysis."""

    if db.get(Profile, task_data.profile_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    try:
        require_enabled_template(task_data.workflow_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    task = Task(
        **task_data.model_dump(),
        workflow_status=WORKFLOW_STATUS_CREATED,
    )
    sync_legacy_status(task)
    db.add(task)
    db.flush()
    try:
        build_and_save_task_plan(
            db,
            task,
            goal=resolve_plan_goal(
                description=task.description,
                url=task.url,
            ),
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    db.commit()
    db.refresh(task)
    return task


@router.get("", response_model=list[TaskResponse])
def list_tasks(db: Session = Depends(get_db)) -> list[Task]:
    """Return all tasks ordered newest first."""

    statement = (
        select(Task)
        .options(selectinload(Task.form_fields))
        .order_by(Task.created_at.desc(), Task.id.desc())
    )
    return list(db.scalars(statement))


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    """Return task details together with extracted form fields."""

    statement = (
        select(Task)
        .options(selectinload(Task.form_fields))
        .where(Task.id == task_id)
    )
    task = db.scalar(statement)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return task


@router.get("/{task_id}/plan", response_model=WorkflowPlanResponse)
def get_task_plan(task_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    """Return the saved workflow plan for one task."""

    task = get_task_or_404(task_id, db)
    plan = get_saved_task_plan(task)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow plan not found",
        )
    return plan


@router.post("/{task_id}/plan", response_model=WorkflowPlanResponse)
def rebuild_task_plan(
    task_id: int,
    request: WorkflowPlanRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Rebuild and overwrite the saved workflow plan for one task."""

    task = get_task_or_404(task_id, db)
    goal = request.goal.strip()
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide a non-empty goal",
        )
    try:
        plan = build_and_save_task_plan(db, task, goal=goal)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    db.commit()
    db.refresh(task)
    return plan


@router.get("/{task_id}/verification-results", response_model=list[FieldVerificationResultResponse])
def get_task_verification_results(task_id: int, db: Session = Depends(get_db)) -> list[FieldVerificationResult]:
    """Return verification results for a task."""

    task = get_task_or_404(task_id, db)

    statement = (
        select(FieldVerificationResult)
        .where(FieldVerificationResult.task_id == task_id)
        .order_by(FieldVerificationResult.id)
    )
    return list(db.scalars(statement))


@router.get("/{task_id}/agent-reviews", response_model=list[AgentReviewResponse])
def get_task_agent_reviews(task_id: int, db: Session = Depends(get_db)) -> list[AgentReview]:
    """Return all agent reviews for a task, newest first."""

    task = get_task_or_404(task_id, db)

    statement = (
        select(AgentReview)
        .where(AgentReview.task_id == task_id)
        .order_by(AgentReview.created_at.desc())
    )
    return list(db.scalars(statement))


class AgentReviewRequest(BaseModel):
    """Request body for running agent reviews."""

    roles: list[str] = []


@router.post("/{task_id}/agent-reviews", response_model=list[AgentReviewResponse])
def run_task_agent_reviews(
    task_id: int,
    request: AgentReviewRequest = AgentReviewRequest(),
    db: Session = Depends(get_db),
) -> list[AgentReview]:
    """Run specified agent reviews for a task and return results.

    Accepts a list of roles to run. Valid roles are:
    - MAPPING_CRITIC - reviews field-to-profile mappings
    - SAFETY_REVIEW - checks for sensitive data handling
    - EXECUTION_VERIFICATION - validates form filling execution

    Each agent returns a structured decision (PASS, REVIEW_REQUIRED, BLOCK).
    """

    from app.agent_constants import (
        AGENT_ROLE_MAPPING_CRITIC,
        AGENT_ROLE_SAFETY_REVIEW,
        AGENT_ROLE_EXECUTION_VERIFICATION,
    )
    from app.services.agent_coordinator import run_agent_review_sequence, get_agent_reviews_for_task

    VALID_ROLES = {
        AGENT_ROLE_MAPPING_CRITIC,
        AGENT_ROLE_SAFETY_REVIEW,
        AGENT_ROLE_EXECUTION_VERIFICATION,
    }

    task = get_task_or_404(task_id, db)

    roles = request.roles if request.roles else list(VALID_ROLES)

    for role in roles:
        if role not in VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid agent role: {role}. Valid roles are: {', '.join(VALID_ROLES)}",
            )

    run_agent_review_sequence(task.id, db, roles)
    db.commit()

    statement = (
        select(AgentReview)
        .where(AgentReview.task_id == task_id)
        .order_by(AgentReview.created_at.desc())
    )
    return list(db.scalars(statement))


@router.post("/{task_id}/analyze", response_model=Union[TaskResponse, JobResponse])
async def analyze_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> Task | Job:
    """Open a task URL, extract its fields, and persist the result.

    When ASYNC_JOBS_ENABLED is True, enqueues an ANALYZE_FORM job instead of
    running the analysis synchronously.
    """

    task = get_task_or_404(task_id, db)
    ensure_form_fill_workflow(task)

    if config.ASYNC_JOBS_ENABLED:
        job = enqueue_job(
            db=db,
            job_type=JOB_TYPE_ANALYZE_FORM,
            task_id=task.id,
        )
        db.commit()
        return job

    step = get_next_log_step(task.id, db)
    span_started_at = time.monotonic()
    analysis_span_id = safe_create_span(
        task_id=task.id,
        phase=SPAN_PHASE_EXTRACTION,
        name="extract_form",
        input={"url": task.url},
    )

    apply_workflow_status(task, WORKFLOW_STATUS_ANALYZING, reason="analyze_started")
    create_log(
        task_id=task.id,
        step=step,
        action="analyze_form",
        message=f"Opening {task.url} and analyzing form fields.",
        status="STARTED",
        db=db,
    )
    db.commit()

    try:
        analysis = read_form_analysis_cache(db, task.url)
        cache_hit = analysis is not None
        if analysis is None:
            analysis = await extract_form_analysis(task.url, task.profile_id)
            write_form_analysis_cache(db, task.url, analysis)
        if analysis.login_required:
            mark_login_required(task, db)
        else:
            save_extracted_fields(task, analysis, db)
        write_checkpoint(
            task_id=task.id,
            stage=WORKFLOW_STAGE_ANALYSIS,
            status=CHECKPOINT_SUCCESS,
            input_hash=f"{task.url}:{task.profile_id}",
            output={"field_count": len(analysis.fields), "login_required": analysis.login_required},
            db=db,
        )
        db.commit()
        safe_finish_span(
            analysis_span_id,
            status=SPAN_STATUS_SUCCESS,
            output={
                "field_count": len(analysis.fields),
                "login_required": analysis.login_required,
                "cache_hit": cache_hit,
            },
            latency_ms=int((time.monotonic() - span_started_at) * 1000),
        )
    except Exception as exc:
        db.rollback()
        task = get_task_or_404(task_id, db)
        apply_workflow_status(task, WORKFLOW_STATUS_FAILED, reason="analyze_failed")
        write_checkpoint(
            task_id=task.id,
            stage=WORKFLOW_STAGE_ANALYSIS,
            status=CHECKPOINT_FAILED,
            input_hash=f"{task.url}:{task.profile_id}",
            failure_reason=FAILURE_ANALYSIS_FAILED,
            error_message=str(exc),
            db=db,
        )
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="analyze_form",
            message=f"Form analysis failed: {exc}",
            status="FAILED",
            db=db,
        )
        db.commit()
        safe_finish_span(
            analysis_span_id,
            status=SPAN_STATUS_FAILED,
            error_message=str(exc),
            latency_ms=int((time.monotonic() - span_started_at) * 1000),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Form analysis failed",
        ) from exc


    statement = (
        select(Task)
        .options(selectinload(Task.form_fields))
        .where(Task.id == task.id)
    )
    return db.scalar(statement)


@router.get("/{task_id}/logs", response_model=list[ActionLogResponse])
def list_task_logs(task_id: int, db: Session = Depends(get_db)) -> list[ActionLog]:
    """Return a task's logs in execution order."""

    get_task_or_404(task_id, db)
    statement = (
        select(ActionLog)
        .where(ActionLog.task_id == task_id)
        .order_by(ActionLog.step, ActionLog.created_at, ActionLog.id)
    )
    return list(db.scalars(statement))


@router.get("/{task_id}/llm-usage", response_model=TaskLlmUsageResponse)
def get_task_llm_usage(
    task_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Return internal LLM usage records and totals for one task."""

    get_task_or_404(task_id, db)
    return {
        "task_id": task_id,
        "summary": summarize_llm_usage(db, task_id=task_id),
        "items": list_llm_usage_logs(db, task_id=task_id),
    }


@router.post(
    "/{task_id}/screenshots",
    response_model=ScreenshotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def capture_task_screenshot(
    task_id: int,
    db: Session = Depends(get_db),
) -> Screenshot:
    """Open the task URL and capture a screenshot for browser testing."""

    task = get_task_or_404(task_id, db)
    screenshot = await open_url_and_capture_screenshot(
        task_id=task.id,
        url=task.url,
        profile_id=task.profile_id,
        stage="page_opened",
        db=db,
    )
    db.commit()
    db.refresh(screenshot)
    return screenshot


@router.get(
    "/{task_id}/screenshots",
    response_model=list[ScreenshotResponse],
)
def list_task_screenshots(
    task_id: int,
    db: Session = Depends(get_db),
) -> list[Screenshot]:
    """Return all screenshots captured for a task."""

    get_task_or_404(task_id, db)
    statement = (
        select(Screenshot)
        .where(Screenshot.task_id == task_id)
        .order_by(Screenshot.created_at, Screenshot.id)
    )
    screenshots = list(db.scalars(statement))
    return [
        screenshot
        for screenshot in screenshots
        if (BACKEND_DIR / screenshot.file_path).is_file()
    ]


@router.get(
    "/{task_id}/checkpoints",
    response_model=list[TaskCheckpointResponse],
)
def list_task_checkpoints(
    task_id: int,
    db: Session = Depends(get_db),
) -> list[TaskCheckpoint]:
    """Return all checkpoints for a task."""

    get_task_or_404(task_id, db)
    return list_checkpoints(task_id=task_id, db=db)


@router.post(
    "/{task_id}/extract-page",
    response_model=TaskResponse,
)
async def extract_task_page(
    task_id: int,
    db: Session = Depends(get_db),
) -> Task:
    """Extract page data for web_data_extract workflow.

    Opens the page, extracts structured data (title, headings, text, links, tables, forms),
    captures a screenshot, and saves the result to the extraction checkpoint.
    """

    task = get_task_or_404(task_id, db)
    if task.workflow_type != WORKFLOW_TYPE_WEB_DATA_EXTRACT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Extract page is only available for web_data_extract workflow",
        )

    step = get_next_log_step(task.id, db)
    span_started_at = time.monotonic()
    extract_span_id = safe_create_span(
        task_id=task.id,
        phase=SPAN_PHASE_EXTRACTION,
        name="extract_page",
        input={"url": task.url},
    )

    apply_workflow_status(task, WORKFLOW_STATUS_ANALYZING, reason="extract_started")
    create_log(
        task_id=task.id,
        step=step,
        action="extract_page",
        message=f"Opening {task.url} and extracting page data.",
        status="STARTED",
        db=db,
    )
    db.commit()

    try:
        result = await extract_page(task.url, task.profile_id)

        await open_url_and_capture_screenshot(
            task_id=task.id,
            url=task.url,
            profile_id=task.profile_id,
            stage="extracted",
            db=db,
        )

        extraction_output = {
            "title": result.title,
            "heading_count": len(result.headings),
            "headings": [{"level": h.level, "text": h.text} for h in result.headings],
            "text_block_count": len(result.main_text_blocks),
            "main_text_blocks": result.main_text_blocks,
            "link_count": len(result.links),
            "links": [{"text": l.text, "href": l.href} for l in result.links],
            "table_count": len(result.tables),
            "tables": [
                {"headers": t.headers, "row_count": len(t.rows)}
                for t in result.tables
            ],
            "form_count": len(result.forms),
            "forms": [
                {"action": f.action, "method": f.method, "field_count": f.field_count}
                for f in result.forms
            ],
        }

        write_checkpoint(
            task_id=task.id,
            stage="EXTRACTION",
            status=CHECKPOINT_SUCCESS,
            input_hash=f"{task.url}:{task.profile_id}",
            output=extraction_output,
            db=db,
        )

        apply_workflow_status(task, WORKFLOW_STATUS_COMPLETED, reason="extraction_completed")
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="extract_page",
            message=f"Extracted page data: {len(result.headings)} headings, {len(result.links)} links, {len(result.tables)} tables, {len(result.forms)} forms",
            status="SUCCESS",
            db=db,
        )
        db.commit()
        safe_finish_span(
            extract_span_id,
            status=SPAN_STATUS_SUCCESS,
            output={
                "heading_count": len(result.headings),
                "link_count": len(result.links),
                "table_count": len(result.tables),
                "form_count": len(result.forms),
            },
            latency_ms=int((time.monotonic() - span_started_at) * 1000),
        )
    except Exception as exc:
        db.rollback()
        task = get_task_or_404(task_id, db)
        apply_workflow_status(task, WORKFLOW_STATUS_FAILED, reason="extraction_failed")
        write_checkpoint(
            task_id=task.id,
            stage="EXTRACTION",
            status=CHECKPOINT_FAILED,
            input_hash=f"{task.url}:{task.profile_id}",
            failure_reason=FAILURE_ANALYSIS_FAILED,
            error_message=str(exc),
            db=db,
        )
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="extract_page",
            message=f"Page extraction failed: {exc}",
            status="FAILED",
            db=db,
        )
        db.commit()
        safe_finish_span(
            extract_span_id,
            status=SPAN_STATUS_FAILED,
            error_message=str(exc),
            latency_ms=int((time.monotonic() - span_started_at) * 1000),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Page extraction failed",
        ) from exc

    statement = (
        select(Task)
        .options(selectinload(Task.form_fields))
        .where(Task.id == task.id)
    )
    return db.scalar(statement)


@router.post(
    "/{task_id}/job-summary",
    response_model=TaskResponse,
)
async def generate_job_summary(
    task_id: int,
    db: Session = Depends(get_db),
) -> Task:
    """Generate a research summary for job_research_summary workflow.

    If extraction checkpoint doesn't exist, first extracts page data,
    then generates a deterministic summary report.
    """

    task = get_task_or_404(task_id, db)
    if task.workflow_type not in (WORKFLOW_TYPE_WEB_DATA_EXTRACT, WORKFLOW_TYPE_JOB_RESEARCH_SUMMARY):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job summary is only available for web_data_extract and job_research_summary workflows",
        )

    step = get_next_log_step(task.id, db)
    span_started_at = time.monotonic()
    summary_span_id = safe_create_span(
        task_id=task.id,
        phase=SPAN_PHASE_EXTRACTION,
        name="generate_job_summary",
        input={"url": task.url},
    )

    apply_workflow_status(task, WORKFLOW_STATUS_ANALYZING, reason="summary_started")
    create_log(
        task_id=task.id,
        step=step,
        action="generate_job_summary",
        message=f"Generating research summary for {task.url}.",
        status="STARTED",
        db=db,
    )
    db.commit()

    try:
        extraction_checkpoints = list_checkpoints(task_id=task.id, db=db)
        extraction_data = None
        for cp in extraction_checkpoints:
            if cp.stage == "EXTRACTION" and cp.status == CHECKPOINT_SUCCESS and cp.output:
                extraction_data = cp.output
                break

        if extraction_data is None:
            create_log(
                task_id=task.id,
                step=get_next_log_step(task.id, db),
                action="extract_page",
                message=f"No extraction checkpoint found, extracting page first.",
                status="STARTED",
                db=db,
            )
            db.commit()

            result = await extract_page(task.url, task.profile_id)

            await open_url_and_capture_screenshot(
                task_id=task.id,
                url=task.url,
                profile_id=task.profile_id,
                stage="extracted",
                db=db,
            )

            extraction_data = {
                "title": result.title,
                "heading_count": len(result.headings),
                "headings": [{"level": h.level, "text": h.text} for h in result.headings],
                "text_block_count": len(result.main_text_blocks),
                "main_text_blocks": result.main_text_blocks,
                "link_count": len(result.links),
                "links": [{"text": l.text, "href": l.href} for l in result.links],
                "table_count": len(result.tables),
                "tables": [
                    {"headers": t.headers, "row_count": len(t.rows)}
                    for t in result.tables
                ],
                "form_count": len(result.forms),
                "forms": [
                    {"action": f.action, "method": f.method, "field_count": f.field_count}
                    for f in result.forms
                ],
            }

            write_checkpoint(
                task_id=task.id,
                stage="EXTRACTION",
                status=CHECKPOINT_SUCCESS,
                input_hash=f"{task.url}:{task.profile_id}",
                output=extraction_data,
                db=db,
            )

        summary_result = generate_research_summary(extraction_data, goal=task.description or "")

        summary_output = {
            "summary": summary_result.summary,
            "key_requirements": summary_result.key_requirements,
            "action_checklist": summary_result.action_checklist,
            "risks": summary_result.risks,
        }

        write_checkpoint(
            task_id=task.id,
            stage="SUMMARY",
            status=CHECKPOINT_SUCCESS,
            input_hash=f"{task.url}:{task.profile_id}",
            output=summary_output,
            db=db,
        )

        apply_workflow_status(task, WORKFLOW_STATUS_COMPLETED, reason="summary_completed")
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="generate_job_summary",
            message=f"Generated research summary with {len(summary_result.key_requirements)} requirements, {len(summary_result.action_checklist)} checklist items, {len(summary_result.risks)} risks.",
            status="SUCCESS",
            db=db,
        )
        db.commit()
        safe_finish_span(
            summary_span_id,
            status=SPAN_STATUS_SUCCESS,
            output={
                "requirement_count": len(summary_result.key_requirements),
                "checklist_count": len(summary_result.action_checklist),
                "risk_count": len(summary_result.risks),
            },
            latency_ms=int((time.monotonic() - span_started_at) * 1000),
        )
    except Exception as exc:
        db.rollback()
        task = get_task_or_404(task_id, db)
        apply_workflow_status(task, WORKFLOW_STATUS_FAILED, reason="summary_failed")
        write_checkpoint(
            task_id=task.id,
            stage="SUMMARY",
            status=CHECKPOINT_FAILED,
            input_hash=f"{task.url}:{task.profile_id}",
            failure_reason=FAILURE_ANALYSIS_FAILED,
            error_message=str(exc),
            db=db,
        )
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="generate_job_summary",
            message=f"Research summary failed: {exc}",
            status="FAILED",
            db=db,
        )
        db.commit()
        safe_finish_span(
            summary_span_id,
            status=SPAN_STATUS_FAILED,
            error_message=str(exc),
            latency_ms=int((time.monotonic() - span_started_at) * 1000),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Research summary failed",
        ) from exc

    statement = (
        select(Task)
        .options(selectinload(Task.form_fields))
        .where(Task.id == task.id)
    )
    return db.scalar(statement)


@router.post(
    "/{task_id}/map-fields",
    response_model=Union[list[FormFieldResponse], JobResponse],
)
def map_task_fields(
    task_id: int,
    mode: Literal["rules", "llm"] = "llm",
    provider: LLMProvider | None = None,
    db: Session = Depends(get_db),
) -> list[FormField] | Job:
    """Generate and save Agent mappings, with a developer rule-mode override.

    When ASYNC_JOBS_ENABLED is True, enqueues a MAP_FIELDS job with the
    mode and provider as payload instead of running synchronously.
    """

    task = get_task_or_404(task_id, db)
    ensure_form_fill_workflow(task)

    if config.ASYNC_JOBS_ENABLED:
        selected_provider = provider
        if mode == "llm":
            try:
                selected_provider = resolve_llm_provider(provider)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc
        job = enqueue_job(
            db=db,
            job_type=JOB_TYPE_MAP_FIELDS,
            task_id=task_id,
            payload={"mode": mode, "provider": selected_provider},
        )
        db.commit()
        return job

    map_span_id = safe_create_span(
        task_id=task.id,
        phase=SPAN_PHASE_MAPPING,
        name="map_fields_llm" if mode == "llm" else "map_fields_rules",
        input={"mode": mode, "provider": provider},
    )
    map_started_at = time.monotonic()
    selected_provider = provider

    try:
        if mode == "llm":
            try:
                selected_provider = resolve_llm_provider(provider)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc
            if not is_provider_configured(selected_provider):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=get_provider_setup_hint(selected_provider),
                )
            mapping_result = map_fields_with_llm_result(
                task_id,
                db,
                provider=selected_provider,
            )
            fields = mapping_result.fields
            retrieval_suggestions = mapping_result.retrieval_suggestions
        else:
            fields = map_fields_by_rules(task_id, db)
            retrieval_suggestions = []

        source_suggestions: list[dict[str, object]] = []
        if task.workflow_type == WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE:
            source_suggestions = apply_policy_answer_suggestions(
                fields=fields,
            )

        apply_workflow_status(task, WORKFLOW_STATUS_MAPPING_READY, reason="mapping_completed")
        mapped_count = sum(1 for f in fields if f.mapped_profile_key or f.mapped_value)
        usage_fields = trace_usage_fields(task_id, db) if mode == "llm" else {}
        checkpoint_output = {
            "field_count": len(fields),
            "mapped_count": mapped_count,
            "mode": mode,
        }
        if source_suggestions:
            checkpoint_output["source_suggestions"] = source_suggestions
        if retrieval_suggestions:
            checkpoint_output["retrieval_suggestions"] = retrieval_suggestions
        write_checkpoint(
            task_id=task_id,
            stage=WORKFLOW_STAGE_MAPPING,
            status=CHECKPOINT_SUCCESS,
            input_hash=f"{task_id}:{mode}:{provider or 'default'}",
            output=checkpoint_output,
            db=db,
        )
        db.commit()
        safe_finish_span(
            map_span_id,
            status=SPAN_STATUS_SUCCESS,
            output={
                "field_count": len(fields),
                "mapped_count": mapped_count,
                "mode": mode,
                "provider": selected_provider if mode == "llm" else None,
            },
            metadata=usage_fields.get("metadata") if usage_fields else None,
            provider=usage_fields.get("provider") if usage_fields else None,
            model=usage_fields.get("model") if usage_fields else None,
            prompt_tokens=usage_fields.get("prompt_tokens") if usage_fields else None,
            completion_tokens=usage_fields.get("completion_tokens") if usage_fields else None,
            total_tokens=usage_fields.get("total_tokens") if usage_fields else None,
            estimated_cost=usage_fields.get("estimated_cost") if usage_fields else None,
            latency_ms=int((time.monotonic() - map_started_at) * 1000),
        )
        return fields
    except HTTPException:
        safe_finish_span(
            map_span_id,
            status=SPAN_STATUS_FAILED,
            error_message="Mapping request rejected",
            latency_ms=int((time.monotonic() - map_started_at) * 1000),
        )
        raise
    except Exception as exc:
        db.rollback()
        task = get_task_or_404(task_id, db)
        apply_workflow_status(task, WORKFLOW_STATUS_FAILED, reason="mapping_failed")
        write_checkpoint(
            task_id=task.id,
            stage=WORKFLOW_STAGE_MAPPING,
            status=CHECKPOINT_FAILED,
            input_hash=f"{task_id}:{mode}:{provider or 'default'}",
            failure_reason=FAILURE_LLM_MAPPING_FAILED if mode == "llm" else FAILURE_ANALYSIS_FAILED,
            error_message=str(exc),
            db=db,
        )
        db.commit()
        safe_finish_span(
            map_span_id,
            status=SPAN_STATUS_FAILED,
            error_message=str(exc),
            latency_ms=int((time.monotonic() - map_started_at) * 1000),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Field mapping failed",
        ) from exc


@router.get(
    "/{task_id}/fields",
    response_model=list[FormFieldResponse],
)
def list_task_fields(
    task_id: int,
    db: Session = Depends(get_db),
) -> list[FormField]:
    """Return extracted fields and their current mappings."""

    get_task_or_404(task_id, db)
    statement = (
        select(FormField)
        .where(FormField.task_id == task_id)
        .order_by(FormField.id)
    )
    return list(db.scalars(statement))


@router.put(
    "/{task_id}/fields/{field_id}",
    response_model=FormFieldResponse,
)
def update_task_field_mapping(
    task_id: int,
    field_id: int,
    mapping_data: FormFieldMappingUpdate,
    db: Session = Depends(get_db),
) -> FormField:
    """Apply a user's correction or clear a field mapping."""

    task = get_task_or_404(task_id, db)
    field = get_task_field_or_404(task_id, field_id, db)
    changes = mapping_data.model_dump(exclude_unset=True)

    if "mapped_profile_key" in changes:
        profile_key = changes["mapped_profile_key"]
        field.mapped_profile_key = profile_key
        if profile_key is None:
            field.mapped_value = None
            field.confidence = None
        elif "mapped_value" not in changes:
            field.mapped_value = get_profile_value(task.profile, profile_key)
            field.confidence = 1.0 if field.mapped_value is not None else None
        save_user_mapping_override(db, field, profile_key)

    if "mapped_value" in changes:
        field.mapped_value = changes["mapped_value"]
        field.confidence = 1.0 if field.mapped_value is not None else None

    if changes.get("save_to_profile"):
        custom_key = normalize_profile_custom_key(changes.get("profile_custom_key"))
        if not custom_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide profile_custom_key when saving to profile",
            )
        if field.mapped_value in (None, ""):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide mapped_value when saving to profile",
            )

        custom_values = task.profile.custom_values
        custom_values[custom_key] = field.mapped_value
        task.profile.custom_values = custom_values
        profile_key = f"{CUSTOM_PROFILE_KEY_PREFIX}{custom_key}"
        field.mapped_profile_key = profile_key
        field.confidence = 1.0
        save_user_mapping_override(db, field, profile_key)

    if "profile_memory_policy" in changes:
        policy = changes["profile_memory_policy"]
        if policy is None:
            field.profile_memory_policy = "auto"
        else:
            field.profile_memory_policy = policy

    db.commit()
    db.refresh(field)
    return field


@router.post(
    "/{task_id}/confirm-mapping",
    response_model=MappingConfirmationResponse,
)
def confirm_task_mapping(
    task_id: int,
    db: Session = Depends(get_db),
) -> MappingConfirmationResponse:
    """Mark the task's reviewed field mapping as ready for filling."""

    task = get_task_or_404(task_id, db)
    ensure_form_fill_workflow(task)
    fields = list(
        db.scalars(
            select(FormField)
            .where(FormField.task_id == task.id)
            .order_by(FormField.id)
        )
    )
    missing_required_fields = get_missing_required_fields(fields)
    if missing_required_fields:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=missing_required_detail(missing_required_fields),
        )

    profile_updates: list[ProfileUpdateItem] = []
    profile_skipped: list[ProfileSkipItem] = []
    custom_values = task.profile.custom_values
    confirm_span_id = safe_create_span(
        task_id=task.id,
        phase=SPAN_PHASE_APPROVAL,
        name="confirm_mapping",
        input={"field_count": len(fields)},
    )
    confirm_started_at = time.monotonic()

    updated_first, updated_last = None, None
    name_field_ids: list[int] = []

    for field in fields:
        if field.mapped_value in (None, ""):
            if field.mapped_profile_key:
                profile_skipped.append(
                    ProfileSkipItem(
                        field_id=field.id,
                        reason="empty_value",
                        detail=field_display_name(field),
                    )
                )
            continue
        if not is_fillable_field(field):
            profile_skipped.append(
                ProfileSkipItem(
                    field_id=field.id,
                    reason="non_fillable_type",
                    detail=field.field_type,
                )
            )
            continue

        memory_policy = field.profile_memory_policy or "auto"

        if memory_policy == "do_not_save":
            profile_skipped.append(
                ProfileSkipItem(
                    field_id=field.id,
                    reason="do_not_save",
                    detail=field_display_name(field),
                )
            )
            continue

        if is_one_time_field(field):
            if memory_policy == "force_save":
                profile_skipped.append(
                    ProfileSkipItem(
                        field_id=field.id,
                        reason="force_save_blocked",
                        detail=field_display_name(field),
                    )
                )
            else:
                profile_skipped.append(
                    ProfileSkipItem(
                        field_id=field.id,
                        reason="one_time_field",
                        detail=field_display_name(field),
                    )
                )
            continue

        profile_key = field.mapped_profile_key or ""
        mapped_value = str(field.mapped_value)
        policy = evaluate_memory_write(
            profile_key=profile_key or field_display_name(field),
            value=mapped_value,
            field_label=field_display_name(field),
        )

        if policy.decision == POLICY_DECISION_BLOCK:
            profile_skipped.append(
                ProfileSkipItem(
                    field_id=field.id,
                    reason="policy_blocked",
                    detail=policy.reason,
                )
            )
            continue
        if policy.decision == POLICY_DECISION_REVIEW_REQUIRED:
            step_name = f"memory_write:{field.id}"
            proposed_action = {
                "action": "memory_write",
                "field_id": field.id,
                "field_label": field_display_name(field),
                "profile_key": profile_key,
                "mapped_value": mapped_value,
                "risk_type": policy.risk_type,
            }
            if latest_approved_request_for_action(
                db,
                task_id=task.id,
                step_name=step_name,
                proposed_action=proposed_action,
            ) is None:
                if not has_pending_approval(db, task_id=task.id, step_name=step_name):
                    create_approval_request(
                        db,
                        task_id=task.id,
                        step_name=step_name,
                        policy_decision=policy,
                        proposed_action=proposed_action,
                    )
                profile_skipped.append(
                    ProfileSkipItem(
                        field_id=field.id,
                        reason="approval_required",
                        detail=policy.reason,
                    )
                )
                continue

        if profile_key.startswith(CUSTOM_PROFILE_KEY_PREFIX):
            custom_key = profile_key.removeprefix(CUSTOM_PROFILE_KEY_PREFIX)
            previous = custom_values.get(custom_key)
            if (previous or "") == mapped_value:
                field.confidence = 1.0
                save_user_mapping_override(db, field, profile_key)
                profile_skipped.append(
                    ProfileSkipItem(
                        field_id=field.id,
                        reason="unchanged",
                        detail=profile_key,
                    )
                )
                continue
            custom_values[custom_key] = mapped_value
            task.profile.custom_values = custom_values
            field.confidence = 1.0
            save_user_mapping_override(db, field, profile_key)
            profile_updates.append(
                ProfileUpdateItem(
                    field_id=field.id,
                    profile_key=profile_key,
                    previous_value=previous,
                    new_value=mapped_value,
                    action="created" if previous in (None, "") else "updated",
                )
            )
            continue

        if profile_key in DERIVED_PROFILE_WRITEBACK_KEYS:
            if updated_first is None and updated_last is None:
                updated_first, updated_last = split_full_name(task.profile.full_name)

            name_field_ids.append(field.id)
            if profile_key == "first_name":
                updated_first = mapped_value
            elif profile_key == "last_name":
                updated_last = mapped_value
            field.confidence = 1.0
            save_user_mapping_override(db, field, profile_key)
            continue

        if profile_key in BUILT_IN_PROFILE_WRITEBACK_KEYS:
            previous = getattr(task.profile, profile_key)
            if (previous or "") == mapped_value:
                field.confidence = 1.0
                save_user_mapping_override(db, field, profile_key)
                profile_skipped.append(
                    ProfileSkipItem(
                        field_id=field.id,
                        reason="unchanged",
                        detail=profile_key,
                    )
                )
                continue
            setattr(task.profile, profile_key, mapped_value)
            field.confidence = 1.0
            save_user_mapping_override(db, field, profile_key)
            profile_updates.append(
                ProfileUpdateItem(
                    field_id=field.id,
                    profile_key=profile_key,
                    previous_value=previous,
                    new_value=mapped_value,
                    action="created" if previous in (None, "") else "updated",
                )
            )
            continue

        generated_key = generate_deduped_custom_key(custom_values, field_display_name(field))
        previous = custom_values.get(generated_key)
        if (previous or "") == mapped_value:
            field.mapped_profile_key = f"{CUSTOM_PROFILE_KEY_PREFIX}{generated_key}"
            field.confidence = 1.0
            save_user_mapping_override(db, field, field.mapped_profile_key)
            profile_skipped.append(
                ProfileSkipItem(
                    field_id=field.id,
                    reason="unchanged",
                    detail=field.mapped_profile_key,
                )
            )
            continue
        custom_values[generated_key] = mapped_value
        task.profile.custom_values = custom_values
        field.mapped_profile_key = f"{CUSTOM_PROFILE_KEY_PREFIX}{generated_key}"
        field.confidence = 1.0
        save_user_mapping_override(db, field, field.mapped_profile_key)
        profile_updates.append(
            ProfileUpdateItem(
                field_id=field.id,
                profile_key=field.mapped_profile_key,
                previous_value=previous,
                new_value=mapped_value,
                action="created" if previous in (None, "") else "updated",
            )
        )

    if name_field_ids and updated_first is not None and updated_last is not None:
        previous_full_name = task.profile.full_name
        full_name_parts = [part for part in [updated_first, updated_last] if part]
        new_full_name = " ".join(full_name_parts).strip() or None
        if new_full_name != previous_full_name:
            task.profile.full_name = new_full_name
            profile_updates.append(
                ProfileUpdateItem(
                    field_id=min(name_field_ids),
                    profile_key="full_name",
                    previous_value=previous_full_name,
                    new_value=new_full_name or "",
                    action="created"
                    if previous_full_name in (None, "")
                    else "updated",
                )
            )

    apply_workflow_status(task, WORKFLOW_STATUS_READY_TO_FILL, reason="mapping_confirmed")
    db.commit()
    try:
        save_confirmed_mappings_for_task(db, task=task, fields=fields)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Workflow memory save failed for task %s", task.id, exc_info=True)
    safe_finish_span(
        confirm_span_id,
        status=SPAN_STATUS_SUCCESS,
        output={
            "profile_update_count": len(profile_updates),
            "skipped_count": len(profile_skipped),
        },
        latency_ms=int((time.monotonic() - confirm_started_at) * 1000),
    )
    return MappingConfirmationResponse(
        task_id=task.id,
        status=task.status,
        profile_updates=profile_updates,
        profile_skipped=profile_skipped,
    )


@router.post("/{task_id}/fill", response_model=Union[TaskResponse, JobResponse])
async def fill_task_form(
    task_id: int,
    db: Session = Depends(get_db),
) -> Task | Job:
    """Fill mapped fields and pause before any final submission.

    When ASYNC_JOBS_ENABLED is True, enqueues a FILL_FORM job instead of
    running the fill synchronously. Validation of task status and required
    fields still runs before enqueueing.
    """

    task = get_task_or_404(task_id, db)
    ensure_form_fill_workflow(task)
    if get_task_workflow_status(task) != WORKFLOW_STATUS_READY_TO_FILL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Review and confirm mapping before filling",
        )

    fields = list(
        db.scalars(
            select(FormField)
            .where(FormField.task_id == task.id)
            .order_by(FormField.id)
        )
    )
    mapped_fields = [field for field in fields if field.mapped_value]
    filtered_fields, blocked_required_fields, pending_required_fields = filter_fillable_fields_by_policy(
        task,
        mapped_fields,
        db,
    )
    missing_required_fields = get_missing_required_fields(fields)
    if missing_required_fields:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=missing_required_detail(missing_required_fields),
        )

    if blocked_required_fields:
        blocked_names = ", ".join(field_display_name(field) for field in blocked_required_fields)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Required fields were blocked by policy: {blocked_names}",
        )
    if pending_required_fields:
        pending_names = ", ".join(field_display_name(field) for field in pending_required_fields)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Required fields require approval before filling: {pending_names}",
        )

    if not filtered_fields:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No mapped fields are ready to fill",
        )

    if config.ASYNC_JOBS_ENABLED:
        job = enqueue_job(
            db=db,
            job_type=JOB_TYPE_FILL_FORM,
            task_id=task.id,
        )
        db.commit()
        return job

    step = get_next_log_step(task.id, db)
    fill_span_id = safe_create_span(
        task_id=task.id,
        phase=SPAN_PHASE_BROWSER,
        name="fill_form",
        input={"filled_count": len(filtered_fields)},
    )
    fill_started_at = time.monotonic()
    screenshot = None
    summary: dict[str, int] = {}
    apply_workflow_status(task, WORKFLOW_STATUS_FILLING, reason="fill_started")
    create_log(
        task_id=task.id,
        step=step,
        action="fill_form",
        message=f"Filling {len(filtered_fields)} mapped fields.",
        status="STARTED",
        db=db,
    )
    db.commit()

    try:
        db.execute(delete(FieldVerificationResult).where(FieldVerificationResult.task_id == task.id))

        screenshot, verification_data = await fill_form_and_capture_screenshot(
            task_id=task.id,
            url=task.url,
            profile_id=task.profile_id,
            fields=filtered_fields,
            stage="filled_form",
            db=db,
        )

        required_field_ids = {f.id for f in filtered_fields if f.required and is_fillable_field(f) and f.mapped_value}
        required_failures = [
            v for v in verification_data
            if v.status == VERIFICATION_STATUS_FAILED
            and v.field_id in required_field_ids
        ]

        for v in verification_data:
            save_verification_result(
                db=db,
                task_id=task.id,
                field_id=v.field_id,
                selector=v.selector,
                expected_value=v.expected_value,
                actual_value=v.actual_value,
                status=v.status,
                reason=v.reason,
                message=v.message,
            )

        summary = get_verification_summary_for_task(db, task.id)

        if required_failures:
            apply_workflow_status(task, WORKFLOW_STATUS_FAILED, reason="fill_verification_failed")
            failure_details = ", ".join(f"field {v.field_id}" for v in required_failures)
            write_checkpoint(
                task_id=task.id,
                stage=WORKFLOW_STAGE_FILL,
                status=CHECKPOINT_FAILED,
                input_hash=f"{task.id}:{len(filtered_fields)}",
                failure_reason=FAILURE_BROWSER_FILL_FAILED,
                error_message=f"Verification failed for required fields: {failure_details}",
                db=db,
            )
            create_log(
                task_id=task.id,
                step=step + 1,
                action="fill_form",
                message=f"Verification failed for required fields: {failure_details}",
                status="FAILED",
                db=db,
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Form filling failed due to verification errors",
            )
        else:
            apply_workflow_status(task, WORKFLOW_STATUS_WAITING_APPROVAL, reason="fill_completed")
            write_checkpoint(
                task_id=task.id,
                stage=WORKFLOW_STAGE_FILL,
                status=CHECKPOINT_SUCCESS,
                input_hash=f"{task.id}:{len(filtered_fields)}",
                output={
                    "filled_count": len(filtered_fields),
                    "verification_summary": summary,
                },
                db=db,
            )
            create_log(
                task_id=task.id,
                step=step + 1,
                action="fill_form",
                message=f"Filled and verified {summary.get('VERIFIED', 0)} fields (skipped {summary.get('SKIPPED', 0)} sensitive fields).",
                status="SUCCESS",
                db=db,
            )

        db.commit()
        safe_finish_span(
            fill_span_id,
            status=SPAN_STATUS_SUCCESS,
            output={
                "filled_count": len(filtered_fields),
                "verification_summary": summary,
            },
            screenshot_id=screenshot.id if screenshot is not None else None,
            latency_ms=int((time.monotonic() - fill_started_at) * 1000),
        )
    except Exception as exc:
        db.rollback()
        task = get_task_or_404(task_id, db)
        apply_workflow_status(task, WORKFLOW_STATUS_FAILED, reason="fill_failed")
        write_checkpoint(
            task_id=task.id,
            stage=WORKFLOW_STAGE_FILL,
            status=CHECKPOINT_FAILED,
            input_hash=f"{task.id}:{len(filtered_fields)}",
            failure_reason=FAILURE_BROWSER_FILL_FAILED,
            error_message=str(exc),
            db=db,
        )
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="fill_form",
            message=f"Form filling failed: {exc}",
            status="FAILED",
            db=db,
        )
        db.commit()
        safe_finish_span(
            fill_span_id,
            status=SPAN_STATUS_FAILED,
            output={
                "filled_count": len(filtered_fields),
                "verification_summary": summary,
            },
            screenshot_id=screenshot.id if screenshot is not None else None,
            error_message=str(exc),
            latency_ms=int((time.monotonic() - fill_started_at) * 1000),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Form filling failed",
        ) from exc

    statement = (
        select(Task)
        .options(selectinload(Task.form_fields))
        .where(Task.id == task.id)
    )
    return db.scalar(statement)


@router.post("/{task_id}/login-and-analyze", response_model=TaskResponse)
async def login_and_analyze_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> Task:
    """Let the user log in, then retry extracting the original target form."""

    task = get_task_or_404(task_id, db)
    ensure_form_fill_workflow(task)
    step = get_next_log_step(task.id, db)
    apply_workflow_status(
        task,
        WORKFLOW_STATUS_LOGIN_IN_PROGRESS,
        reason="manual_login_started",
    )
    create_log(
        task_id=task.id,
        step=step,
        action="manual_login",
        message="Opened login browser. Close it after login to continue analysis.",
        status="STARTED",
        db=db,
    )
    db.commit()

    try:
        _, timed_out = await prepare_login_session(
            url=task.url,
            profile_id=task.profile_id,
        )
        if timed_out:
            apply_workflow_status(
                task,
                WORKFLOW_STATUS_LOGIN_REQUIRED,
                reason="manual_login_timed_out",
            )
            create_log(
                task_id=task.id,
                step=get_next_log_step(task.id, db),
                action="manual_login",
                message="Login browser timed out before it was closed.",
                status="TIMEOUT",
                db=db,
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Login browser timed out. Try logging in again.",
            )

        apply_workflow_status(task, WORKFLOW_STATUS_ANALYZING, reason="manual_login_completed")
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="resume_after_login",
            message="Reopened the original URL with saved login state.",
            status="STARTED",
            db=db,
        )
        db.commit()

        analysis = await extract_form_analysis(task.url, task.profile_id)
        if analysis.login_required:
            mark_login_required(task, db)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Login is still required. Complete login and close the browser window.",
            )

        save_extracted_fields(task, analysis, db)
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        task = get_task_or_404(task_id, db)
        apply_workflow_status(task, WORKFLOW_STATUS_FAILED, reason="manual_login_failed")
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="manual_login",
            message=f"Login and analysis failed: {exc}",
            status="FAILED",
            db=db,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login and analysis failed",
        ) from exc

    statement = (
        select(Task)
        .options(selectinload(Task.form_fields))
        .where(Task.id == task.id)
    )
    return db.scalar(statement)


@router.post(
    "/{task_id}/confirm-submit",
    response_model=SubmissionConfirmationResponse,
)
async def confirm_task_submission(
    task_id: int,
    db: Session = Depends(get_db),
) -> SubmissionConfirmationResponse:
    """Submit the reviewed browser form after explicit user approval."""

    task = get_task_or_404(task_id, db)
    ensure_form_fill_workflow(task)
    if get_task_workflow_status(task) != WORKFLOW_STATUS_WAITING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task is not waiting for approval",
        )

    fields = list(
        db.scalars(
            select(FormField)
            .where(FormField.task_id == task.id)
            .order_by(FormField.id)
        )
    )
    mapped_fields = [field for field in fields if field.mapped_value]
    missing_required_fields = get_missing_required_fields(fields)
    if missing_required_fields:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=missing_required_detail(missing_required_fields),
        )

    if not mapped_fields:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No mapped fields are ready to submit",
        )

    submit_policy = evaluate_submit_action()
    submit_step_name = "submit_form"
    submit_proposed_action = {
        "action": "submit_form",
        "fields": [
            {
                "field_id": field.id,
                "mapped_value": str(field.mapped_value),
            }
            for field in mapped_fields
        ],
    }
    approved_submit_request = latest_approved_request_for_action(
        db,
        task_id=task.id,
        step_name=submit_step_name,
        proposed_action=submit_proposed_action,
    )
    rejected_submit_request = latest_rejected_request(task.id, submit_step_name, db)
    if approved_submit_request is None:
        if rejected_submit_request is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Final submission approval was rejected",
                    "approval_id": rejected_submit_request.id,
                },
            )
        pending_submit_request = None

        pending_requests = list_pending_approvals(db, task_id=task.id, status="PENDING")
        for request in pending_requests:
            if request.step_name == submit_step_name:
                pending_submit_request = request
                break
        if pending_submit_request is None:
            pending_submit_request = create_approval_request(
                db,
                task_id=task.id,
                step_name=submit_step_name,
                policy_decision=submit_policy,
                proposed_action=submit_proposed_action,
            )
            apply_workflow_status(task, WORKFLOW_STATUS_WAITING_APPROVAL, reason="submit_approval_created")
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Final submission requires approval",
                "approval_id": pending_submit_request.id,
            },
        )

    step = get_next_log_step(task.id, db)
    submit_span_id = safe_create_span(
        task_id=task.id,
        phase=SPAN_PHASE_BROWSER,
        name="submit_form",
        input={"field_count": len(mapped_fields)},
    )
    submit_started_at = time.monotonic()
    create_log(
        task_id=task.id,
        step=step,
        action="confirm_submit",
        message="User approved final form submission.",
        status="STARTED",
        db=db,
    )
    db.commit()

    try:
        screenshot = await submit_form_and_capture_screenshot(
            task_id=task.id,
            url=task.url,
            profile_id=task.profile_id,
            fields=mapped_fields,
            stage="submitted_form",
            db=db,
        )
        apply_workflow_status(task, WORKFLOW_STATUS_COMPLETED, reason="submit_completed")
        create_log(
            task_id=task.id,
            step=step + 1,
            action="submit_form",
            message="Submitted the reviewed form after user approval.",
            status="SUCCESS",
            db=db,
        )
        db.commit()
        safe_finish_span(
            submit_span_id,
            status=SPAN_STATUS_SUCCESS,
            output={"final_status": task.status},
            screenshot_id=screenshot.id,
            latency_ms=int((time.monotonic() - submit_started_at) * 1000),
        )
    except Exception as exc:
        db.rollback()
        task = get_task_or_404(task_id, db)
        apply_workflow_status(task, WORKFLOW_STATUS_FAILED, reason="submit_failed")
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="submit_form",
            message=f"Form submission failed: {exc}",
            status="FAILED",
            db=db,
        )
        db.commit()
        safe_finish_span(
            submit_span_id,
            status=SPAN_STATUS_FAILED,
            output={"final_status": task.status},
            error_message=str(exc),
            latency_ms=int((time.monotonic() - submit_started_at) * 1000),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Form submission failed",
        ) from exc

    return SubmissionConfirmationResponse(
        task_id=task.id,
        status=task.status,
        approval_id=approved_submit_request.id,
    )
