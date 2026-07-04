"""Task-related API endpoints."""

import json
import re
from typing import Literal, Union

from fastapi import APIRouter, Depends, HTTPException, status
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
from app.models import ActionLog, FormField, Job, Profile, Screenshot, Task, TaskCheckpoint
from app.schemas import (
    ActionLogResponse,
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
    TaskResponse,
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
    map_fields_with_llm,
)
from app.services.form_extractor import ExtractedFormAnalysis, extract_form_analysis
from app.services.form_analysis_cache import (
    read_form_analysis_cache,
    write_form_analysis_cache,
)
from app.services.browser_session import prepare_login_session
from app.services.llm_provider_config import (
    get_provider_setup_hint,
    is_provider_configured,
    resolve_llm_provider,
)
from app.services.llm_usage_service import list_llm_usage_logs, summarize_llm_usage
from app.services.log_service import create_log
from app.services.job_queue import enqueue_job
from app.services.mapping_cache import save_user_mapping_override
from app.services.checkpoint_service import list_checkpoints, write_checkpoint
from app.workflow_constants import (
    CHECKPOINT_FAILED,
    CHECKPOINT_SUCCESS,
    FAILURE_ANALYSIS_FAILED,
    FAILURE_BROWSER_FILL_FAILED,
    FAILURE_LLM_MAPPING_FAILED,
    WORKFLOW_STAGE_ANALYSIS,
    WORKFLOW_STAGE_FILL,
    WORKFLOW_STAGE_MAPPING,
)

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

    task.status = "LOGIN_REQUIRED"
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

    task.status = "MAPPING_READY"
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

    task = Task(**task_data.model_dump(), status="CREATED")
    db.add(task)
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

    if config.ASYNC_JOBS_ENABLED:
        job = enqueue_job(
            db=db,
            job_type=JOB_TYPE_ANALYZE_FORM,
            task_id=task.id,
        )
        db.commit()
        return job

    step = get_next_log_step(task.id, db)

    task.status = "ANALYZING"
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
    except Exception as exc:
        db.rollback()
        task = get_task_or_404(task_id, db)
        task.status = "FAILED"
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

    get_task_or_404(task_id, db)

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
            fields = map_fields_with_llm(task_id, db, provider=selected_provider)
        else:
            fields = map_fields_by_rules(task_id, db)

        mapped_count = sum(1 for f in fields if f.mapped_profile_key)
        write_checkpoint(
            task_id=task_id,
            stage=WORKFLOW_STAGE_MAPPING,
            status=CHECKPOINT_SUCCESS,
            input_hash=f"{task_id}:{mode}:{provider or 'default'}",
            output={"field_count": len(fields), "mapped_count": mapped_count, "mode": mode},
            db=db,
        )
        db.commit()
        return fields
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        task = get_task_or_404(task_id, db)
        task.status = "FAILED"
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

    task.status = "READY_TO_FILL"
    db.commit()
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
    if task.status != "READY_TO_FILL":
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
    missing_required_fields = get_missing_required_fields(fields)
    if missing_required_fields:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=missing_required_detail(missing_required_fields),
        )

    if not mapped_fields:
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
    task.status = "FILLING"
    create_log(
        task_id=task.id,
        step=step,
        action="fill_form",
        message=f"Filling {len(mapped_fields)} mapped fields.",
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
            fields=mapped_fields,
            stage="filled_form",
            db=db,
        )

        required_field_ids = {f.id for f in fields if f.required and is_fillable_field(f) and f.mapped_value}
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
            task.status = "FAILED"
            failure_details = ", ".join(f"field {v.field_id}" for v in required_failures)
            write_checkpoint(
                task_id=task.id,
                stage=WORKFLOW_STAGE_FILL,
                status=CHECKPOINT_FAILED,
                input_hash=f"{task.id}:{len(mapped_fields)}",
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
            task.status = "WAITING_APPROVAL"
            write_checkpoint(
                task_id=task.id,
                stage=WORKFLOW_STAGE_FILL,
                status=CHECKPOINT_SUCCESS,
                input_hash=f"{task.id}:{len(mapped_fields)}",
                output={
                    "filled_count": len(mapped_fields),
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
    except Exception as exc:
        db.rollback()
        task = get_task_or_404(task_id, db)
        task.status = "FAILED"
        write_checkpoint(
            task_id=task.id,
            stage=WORKFLOW_STAGE_FILL,
            status=CHECKPOINT_FAILED,
            input_hash=f"{task.id}:{len(mapped_fields)}",
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
    step = get_next_log_step(task.id, db)
    task.status = "LOGIN_IN_PROGRESS"
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
            task.status = "LOGIN_REQUIRED"
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

        task.status = "ANALYZING"
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
        task.status = "FAILED"
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
    if task.status != "WAITING_APPROVAL":
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

    step = get_next_log_step(task.id, db)
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
        await submit_form_and_capture_screenshot(
            task_id=task.id,
            url=task.url,
            profile_id=task.profile_id,
            fields=mapped_fields,
            stage="submitted_form",
            db=db,
        )
        task.status = "COMPLETED"
        create_log(
            task_id=task.id,
            step=step + 1,
            action="submit_form",
            message="Submitted the reviewed form after user approval.",
            status="SUCCESS",
            db=db,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        task = get_task_or_404(task_id, db)
        task.status = "FAILED"
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="submit_form",
            message=f"Form submission failed: {exc}",
            status="FAILED",
            db=db,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Form submission failed",
        ) from exc

    return SubmissionConfirmationResponse(task_id=task.id, status=task.status)
