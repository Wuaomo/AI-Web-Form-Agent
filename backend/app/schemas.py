"""Pydantic models used by the API."""

from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from app.workflow_constants import WORKFLOW_TYPE_FORM_FILL

ProfileKey = str


class HealthResponse(BaseModel):
    """Response returned by the health check endpoint."""

    status: Literal["ok"]


LLMProvider = Literal["openai", "gemini", "deepseek"]


class LLMProviderResponse(BaseModel):
    """Configuration status for one selectable LLM provider."""

    id: LLMProvider
    display_name: str
    model: str
    model_env: str
    api_key_env: str
    configured: bool
    selected: bool
    setup_hint: str


class ProfileBase(BaseModel):
    """Fields shared by profile create and response models."""

    profile_name: str
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    university: str | None = None
    major: str | None = None
    linkedin: str | None = None
    github: str | None = None
    self_intro: str | None = None
    custom_values: dict[str, str] = Field(default_factory=dict)


class ProfileCreate(ProfileBase):
    """Data required to create a profile."""


class ProfileUpdate(BaseModel):
    """Profile fields that may be changed."""

    profile_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    university: str | None = None
    major: str | None = None
    linkedin: str | None = None
    github: str | None = None
    self_intro: str | None = None
    custom_values: dict[str, str] | None = None


class ProfileResponse(ProfileBase):
    """Profile data returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ActionLogResponse(BaseModel):
    """One recorded action performed for a task."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    step: int
    action: str
    message: str | None
    status: str
    created_at: datetime


class LlmApiUsageLogResponse(BaseModel):
    """One internal LLM API usage record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cache_hit_tokens: int
    cache_miss_tokens: int
    cache_hit: bool
    cache_hit_rate: float
    latency_ms: int
    error_type: str | None
    fallback_used: bool
    cache_source: str
    estimated_cost: float
    created_at: datetime


class LlmUsageSummaryResponse(BaseModel):
    """Aggregated LLM token and cache usage."""

    task_id: int | None
    request_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cache_hit_tokens: int
    cache_miss_tokens: int
    cache_hit_rate: float
    average_latency_ms: int
    p95_latency_ms: int
    fallback_count: int
    estimated_cost: float


class ProviderLlmUsageSummaryResponse(BaseModel):
    """Aggregated LLM usage for one provider-model combination."""

    provider: str
    model: str
    request_count: int
    average_latency_ms: int
    p95_latency_ms: int
    cache_hit_rate: float
    fallback_count: int
    estimated_cost: float


class TaskLlmUsageResponse(BaseModel):
    """Task-specific LLM usage details plus totals."""

    task_id: int
    summary: LlmUsageSummaryResponse
    items: list[LlmApiUsageLogResponse]


class ScreenshotResponse(BaseModel):
    """Metadata for a screenshot captured during task execution."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    file_path: str
    stage: str
    created_at: datetime


class FormFieldResponse(BaseModel):
    """An extracted form field and its current profile mapping."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    element_ref: str | None
    form_title: str | None
    section_title: str | None
    field_label: str | None
    hint: str | None
    label: str | None
    selector: str
    field_type: str | None
    placeholder: str | None
    name: str | None
    html_id: str | None
    current_value: str | None
    options: list[dict[str, str | None]] = Field(default_factory=list)
    required: bool
    mapped_profile_key: str | None
    mapped_value: str | None
    confidence: float | None
    profile_memory_policy: str


class FormFieldMappingUpdate(BaseModel):
    """User-editable parts of a form field mapping."""

    mapped_profile_key: ProfileKey | None = None
    mapped_value: str | None = None
    save_to_profile: bool = False
    profile_custom_key: str | None = None
    profile_memory_policy: Literal["auto", "do_not_save", "force_save"] | None = None

    @model_validator(mode="after")
    def require_an_update(self) -> "FormFieldMappingUpdate":
        """Reject an empty JSON object while still allowing explicit nulls."""

        if not self.model_fields_set:
            raise ValueError("Provide mapped_profile_key or mapped_value")
        return self


class ProfileUpdateItem(BaseModel):
    """One profile write-back performed during mapping confirmation."""

    field_id: int
    profile_key: str
    previous_value: str | None
    new_value: str
    action: Literal["created", "updated"]


class ProfileSkipItem(BaseModel):
    """One field that was considered but intentionally not persisted."""

    field_id: int
    reason: Literal[
        "empty_value",
        "non_fillable_type",
        "one_time_field",
        "unchanged",
        "do_not_save",
        "force_save_blocked",
        "policy_blocked",
        "approval_required",
    ]
    detail: str | None = None


class MappingConfirmationResponse(BaseModel):
    """Task status returned after the user confirms the mapping."""

    task_id: int
    status: str
    profile_updates: list[ProfileUpdateItem] = Field(default_factory=list)
    profile_skipped: list[ProfileSkipItem] = Field(default_factory=list)


class SubmissionConfirmationResponse(BaseModel):
    """Task status returned after the user confirms submission."""

    task_id: int
    status: str
    approval_id: int | None = None


class TaskCreate(BaseModel):
    """Data required to create a form analysis task."""

    url: str
    profile_id: int
    description: str | None = None
    workflow_type: str = WORKFLOW_TYPE_FORM_FILL


class TaskResponse(BaseModel):
    """Task details including fields discovered during analysis."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    description: str | None
    profile_id: int
    status: str
    workflow_type: str = WORKFLOW_TYPE_FORM_FILL
    workflow_status: str
    created_at: datetime
    updated_at: datetime
    form_fields: list[FormFieldResponse] = Field(default_factory=list)


class PlannedStepResponse(BaseModel):
    """One persisted workflow plan step."""

    step_id: str
    tool: str
    reason: str
    requires_approval: bool
    status: str


class WorkflowPlanRequest(BaseModel):
    """Request payload for rebuilding a saved workflow plan."""

    goal: str = Field(min_length=1)


class WorkflowPlanResponse(BaseModel):
    """One persisted workflow plan."""

    workflow_type: str
    goal: str
    steps: list[PlannedStepResponse] = Field(default_factory=list)


class WorkflowTemplateResponse(BaseModel):
    """One static workflow template exposed for task creation."""

    id: str
    name: str
    description: str
    enabled: bool
    steps: list[str]
    approval_policy: dict[str, str] = Field(default_factory=dict)


class WorkflowSpanResponse(BaseModel):
    """One persisted workflow trace span."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    parent_span_id: int | None
    phase: str
    name: str
    status: str
    input: dict[str, object] = Field(default_factory=dict)
    output: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("span_metadata", "metadata"),
    )
    provider: str | None
    model: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    latency_ms: int
    screenshot_id: int | None
    error_message: str | None
    created_at: datetime


class ApprovalRequestResponse(BaseModel):
    """One persisted approval request."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    step_name: str
    risk_type: str
    risk_level: str
    decision: str
    reason: str
    proposed_action: dict[str, object] = Field(default_factory=dict)
    status: str
    resolved_by: str | None
    created_at: datetime
    resolved_at: datetime | None


class BenchmarkRunRequest(BaseModel):
    """Options for running the local benchmark suite."""

    mode: Literal["rules", "llm"] = "rules"
    provider: str | None = None
    stress_mode: Literal["standard", "cache_cold", "cache_warm", "concurrent"] = "standard"


class BenchmarkCaseResultResponse(BaseModel):
    """Metrics and failure details for one benchmark case."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    case_id: str
    title: str
    metrics: dict[str, float]
    failures: list[dict[str, object]]
    created_at: datetime


class BenchmarkRunResponse(BaseModel):
    """Persisted benchmark run with optional case details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    mode: str
    provider: str | None
    total_cases: int
    average_score: float
    summary_metrics: dict[str, float | None]
    baseline_run_id: int | None
    duration_ms: int
    regression_count: int
    improvement_count: int
    mode_detail: str | None
    created_at: datetime
    case_results: list[BenchmarkCaseResultResponse] = Field(default_factory=list)


class TaskActionTraceResponse(BaseModel):
    """Detailed admin-only action trace entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    step: int
    phase: str
    action: str
    selector: str | None
    field_id: int | None
    input_value: str | None
    result: str
    error_message: str | None
    screenshot_id: int | None
    created_at: datetime


class TaskCheckpointResponse(BaseModel):
    """A recoverable stage result for one task workflow."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    stage: str
    status: str
    input_hash: str | None
    output: dict[str, object] = Field(default_factory=dict)
    failure_reason: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class JobResponse(BaseModel):
    """An asynchronous job for long-running workflow tasks."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int | None
    job_type: str
    status: str
    priority: int
    payload: dict[str, object] = Field(default_factory=dict)
    attempts: int
    max_attempts: int
    locked_by: str | None
    locked_at: datetime | None
    next_run_at: datetime | None
    error_reason: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class JobAttemptResponse(BaseModel):
    """Record of one execution attempt for a job."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    attempt_no: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    error_reason: str | None
    error_message: str | None


class WorkerHeartbeatResponse(BaseModel):
    """Heartbeat record tracking a worker's availability and current workload."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    worker_id: str
    hostname: str | None
    current_job_id: int | None
    status: str
    last_seen_at: datetime


class FieldVerificationResultResponse(BaseModel):
    """Post-fill verification result for one form field."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    field_id: int | None
    selector: str
    expected_value_hash: str | None
    actual_value_hash: str | None
    status: str
    reason: str | None
    message: str | None
    created_at: datetime


class AgentReviewResponse(BaseModel):
    """Review decision from an AI agent for a form automation task."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    role: str
    decision: str
    input_hash: str
    output: dict[str, object] = Field(default_factory=dict)
    model: str | None
    provider: str | None
    created_at: datetime
