"""SQLAlchemy models for profiles and form automation tasks."""

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.workflow_constants import (
    WORKFLOW_STATUS_CREATED,
    WORKFLOW_TYPE_FORM_FILL,
)


def utc_now() -> datetime:
    """Return the current UTC time for model timestamp defaults."""

    return datetime.now(timezone.utc)


class Profile(Base):
    """Reusable personal information used to fill web forms."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_name: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(200))
    email: Mapped[Optional[str]] = mapped_column(String(320))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    university: Mapped[Optional[str]] = mapped_column(String(200))
    major: Mapped[Optional[str]] = mapped_column(String(200))
    linkedin: Mapped[Optional[str]] = mapped_column(String(500))
    github: Mapped[Optional[str]] = mapped_column(String(500))
    self_intro: Mapped[Optional[str]] = mapped_column(Text)
    custom_values_json: Mapped[Optional[str]] = mapped_column("custom_values", Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="profile")

    @property
    def custom_values(self) -> dict[str, str]:
        """User-saved values that do not fit the built-in profile fields."""

        if not self.custom_values_json:
            return {}
        try:
            parsed = json.loads(self.custom_values_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in parsed.items()
            if value not in (None, "")
        }

    @custom_values.setter
    def custom_values(self, value: dict[str, str] | None) -> None:
        """Persist custom profile values as JSON."""

        self.custom_values_json = json.dumps(value or {}, ensure_ascii=False)


class Task(Base):
    """A web form automation task."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=WORKFLOW_STATUS_CREATED, nullable=False)
    workflow_type: Mapped[str] = mapped_column(
        String(50),
        default=WORKFLOW_TYPE_FORM_FILL,
        nullable=False,
    )
    workflow_status: Mapped[str] = mapped_column(
        String(50),
        default=WORKFLOW_STATUS_CREATED,
        nullable=False,
    )
    workflow_plan_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    profile: Mapped["Profile"] = relationship(back_populates="tasks")
    form_fields: Mapped[list["FormField"]] = relationship(back_populates="task")
    action_logs: Mapped[list["ActionLog"]] = relationship(back_populates="task")
    screenshots: Mapped[list["Screenshot"]] = relationship(back_populates="task")
    llm_usage_logs: Mapped[list["LlmApiUsageLog"]] = relationship(
        back_populates="task"
    )
    checkpoints: Mapped[list["TaskCheckpoint"]] = relationship(back_populates="task")
    workflow_spans: Mapped[list["WorkflowSpan"]] = relationship(back_populates="task")
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(back_populates="task")
    jobs: Mapped[list["Job"]] = relationship(back_populates="task")
    verification_results: Mapped[list["FieldVerificationResult"]] = relationship(back_populates="task")
    agent_reviews: Mapped[list["AgentReview"]] = relationship(back_populates="task")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="task")

    @property
    def workflow_plan(self) -> dict[str, object]:
        """Return the saved workflow plan JSON, raising on malformed content."""

        if not self.workflow_plan_json:
            return {}
        try:
            parsed = json.loads(self.workflow_plan_json)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid workflow plan JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("Invalid workflow plan JSON")
        return parsed

    @workflow_plan.setter
    def workflow_plan(self, value: dict[str, object] | None) -> None:
        """Persist the saved workflow plan as stable JSON."""

        self.workflow_plan_json = json.dumps(
            value or {},
            ensure_ascii=False,
            sort_keys=True,
        )


class FormField(Base):
    """A field extracted from a task's target form."""

    __tablename__ = "form_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    element_ref: Mapped[Optional[str]] = mapped_column(String(100))
    form_title: Mapped[Optional[str]] = mapped_column(String(500))
    section_title: Mapped[Optional[str]] = mapped_column(String(500))
    label: Mapped[Optional[str]] = mapped_column(String(500))
    selector: Mapped[str] = mapped_column(String(1000), nullable=False)
    field_type: Mapped[Optional[str]] = mapped_column(String(100))
    placeholder: Mapped[Optional[str]] = mapped_column(String(500))
    name: Mapped[Optional[str]] = mapped_column(String(500))
    html_id: Mapped[Optional[str]] = mapped_column(String(500))
    current_value: Mapped[Optional[str]] = mapped_column(Text)
    field_options: Mapped[Optional[str]] = mapped_column("options", Text)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mapped_profile_key: Mapped[Optional[str]] = mapped_column(String(100))
    mapped_value: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    profile_memory_policy: Mapped[str] = mapped_column(String(20), default="auto", nullable=False)

    task: Mapped["Task"] = relationship(back_populates="form_fields")

    @property
    def field_label(self) -> Optional[str]:
        """Semantic alias for the input's own title."""

        return self.label

    @property
    def hint(self) -> Optional[str]:
        """Semantic alias for the input placeholder/help text."""

        return self.placeholder

    @property
    def options(self) -> list[dict[str, str | None]]:
        """Structured choices for select/radio-like fields."""

        if not self.field_options:
            return []
        try:
            options = json.loads(self.field_options)
        except json.JSONDecodeError:
            return []
        if not isinstance(options, list):
            return []
        return [
            option
            for option in options
            if isinstance(option, dict)
        ]

    @options.setter
    def options(self, value: list[dict[str, str | None]] | None) -> None:
        """Persist structured choices as JSON."""

        self.field_options = json.dumps(value or [], ensure_ascii=False)


class AgentRun(Base):
    """Persisted compatibility record for one governed runtime run."""

    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    legacy_task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    target_url: Mapped[Optional[str]] = mapped_column(String(2048))
    profile_id: Mapped[Optional[int]] = mapped_column(Integer)
    workflow_hint: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    current_plan_id: Mapped[Optional[str]] = mapped_column(String(200))
    pending_review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    final_result_json: Mapped[Optional[str]] = mapped_column("final_result", Text)
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    task: Mapped["Task"] = relationship(back_populates="agent_runs")
    plans: Mapped[list["AgentPlan"]] = relationship(back_populates="run")
    tool_calls: Mapped[list["AgentToolCall"]] = relationship(back_populates="run")

    @property
    def final_result(self) -> dict[str, object]:
        """Return structured final result data."""

        if not self.final_result_json:
            return {}
        try:
            parsed = json.loads(self.final_result_json)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @final_result.setter
    def final_result(self, value: dict[str, object] | None) -> None:
        """Persist final result as stable JSON."""

        self.final_result_json = json.dumps(
            value or {},
            ensure_ascii=False,
            sort_keys=True,
        )


class AgentPlan(Base):
    """Persisted compact plan for one governed runtime run."""

    __tablename__ = "agent_plans"

    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    steps_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    run: Mapped["AgentRun"] = relationship(back_populates="plans")

    @property
    def steps(self) -> list[dict[str, object]]:
        """Return compact planned tool calls."""

        try:
            parsed = json.loads(self.steps_json)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []

    @steps.setter
    def steps(self, value: list[dict[str, object]] | None) -> None:
        """Persist plan steps as stable JSON."""

        self.steps_json = json.dumps(
            value or [],
            ensure_ascii=False,
            sort_keys=True,
        )


class AgentToolCall(Base):
    """Persisted compact tool call record for a governed runtime run."""

    __tablename__ = "agent_tool_calls"

    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False)
    plan_step_id: Mapped[Optional[str]] = mapped_column(String(200))
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    input_payload_json: Mapped[str] = mapped_column("input_json", Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    governance_decision_json: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    run: Mapped["AgentRun"] = relationship(back_populates="tool_calls")
    result: Mapped[Optional["AgentToolResult"]] = relationship(
        back_populates="tool_call",
        cascade="all, delete-orphan",
        uselist=False,
    )

    @property
    def input_json(self) -> dict[str, object]:
        """Return structured tool input."""

        try:
            parsed = json.loads(self.input_payload_json)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @input_json.setter
    def input_json(self, value: dict[str, object] | None) -> None:
        """Persist tool input as stable JSON."""

        self.input_payload_json = json.dumps(
            value or {},
            ensure_ascii=False,
            sort_keys=True,
        )

    @property
    def governance_decision(self) -> dict[str, object]:
        """Return structured governance decision data."""

        if not self.governance_decision_json:
            return {}
        try:
            parsed = json.loads(self.governance_decision_json)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @governance_decision.setter
    def governance_decision(self, value: dict[str, object] | None) -> None:
        """Persist governance decision as stable JSON."""

        self.governance_decision_json = json.dumps(
            value or {},
            ensure_ascii=False,
            sort_keys=True,
        )


class AgentToolResult(Base):
    """Persisted raw result for one governed runtime tool call."""

    __tablename__ = "agent_tool_results"

    tool_call_id: Mapped[str] = mapped_column(
        ForeignKey("agent_tool_calls.id"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    output_payload_json: Mapped[str] = mapped_column("output_json", Text, nullable=False)
    evidence_items_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_proposals_json: Mapped[str] = mapped_column(Text, nullable=False)
    verification_candidates_json: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    tool_call: Mapped["AgentToolCall"] = relationship(back_populates="result")

    @property
    def output_json(self) -> dict[str, object]:
        """Return structured raw tool output for backend-only recovery."""

        try:
            parsed = json.loads(self.output_payload_json)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @output_json.setter
    def output_json(self, value: dict[str, object] | None) -> None:
        """Persist raw tool output as stable JSON."""

        self.output_payload_json = json.dumps(
            value or {},
            ensure_ascii=False,
            sort_keys=True,
        )

    @property
    def evidence_items(self) -> list[dict[str, object]]:
        """Return persisted evidence item payloads."""

        return _json_list(self.evidence_items_json)

    @evidence_items.setter
    def evidence_items(self, value: list[dict[str, object]] | None) -> None:
        """Persist evidence items as stable JSON."""

        self.evidence_items_json = _dump_json_list(value)

    @property
    def created_proposals(self) -> list[dict[str, object]]:
        """Return persisted proposal payloads."""

        return _json_list(self.created_proposals_json)

    @created_proposals.setter
    def created_proposals(self, value: list[dict[str, object]] | None) -> None:
        """Persist created proposals as stable JSON."""

        self.created_proposals_json = _dump_json_list(value)

    @property
    def verification_candidates(self) -> list[dict[str, object]]:
        """Return persisted verification candidate payloads."""

        return _json_list(self.verification_candidates_json)

    @verification_candidates.setter
    def verification_candidates(self, value: list[dict[str, object]] | None) -> None:
        """Persist verification candidates as stable JSON."""

        self.verification_candidates_json = _dump_json_list(value)


def _json_list(value: str | None) -> list[dict[str, object]]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _dump_json_list(value: list[dict[str, object]] | None) -> str:
    return json.dumps(value or [], ensure_ascii=False, sort_keys=True)


class ActionLog(Base):
    """A chronological record of actions performed for a task."""

    __tablename__ = "action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    task: Mapped["Task"] = relationship(back_populates="action_logs")


class LlmApiUsageLog(Base):
    """Internal token and cache usage from one LLM API response."""

    __tablename__ = "llm_api_usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cache_hit_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cache_miss_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cache_hit_rate: Mapped[float] = mapped_column(Float, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_type: Mapped[Optional[str]] = mapped_column(String(100))
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cache_source: Mapped[str] = mapped_column(String(50), default="no_cache", nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    task: Mapped["Task"] = relationship(back_populates="llm_usage_logs")


class Screenshot(Base):
    """A screenshot captured during task execution."""

    __tablename__ = "screenshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    task: Mapped["Task"] = relationship(back_populates="screenshots")


class LLMMappingCache(Base):
    """Reusable LLM field-to-profile-key mappings for stable form structures."""

    __tablename__ = "llm_mapping_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    fields_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_keys_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class UserMappingOverrideCache(Base):
    """User-confirmed field mapping preference for one stable field signature."""

    __tablename__ = "user_mapping_override_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    field_signature: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    mapped_profile_key: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class FormAnalysisCache(Base):
    """Reusable extracted form metadata for one normalized public URL."""

    __tablename__ = "form_analysis_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url_cache_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    fields_json: Mapped[str] = mapped_column(Text, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class BenchmarkRun(Base):
    """One execution of the local benchmark suite."""

    __tablename__ = "benchmark_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    average_score: Mapped[float] = mapped_column(Float, nullable=False)
    summary_metrics_json: Mapped[str] = mapped_column("summary_metrics", Text, nullable=False)
    baseline_run_id: Mapped[Optional[int]] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    regression_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    improvement_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mode_detail: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    case_results: Mapped[list["BenchmarkCaseResult"]] = relationship(
        back_populates="run"
    )

    @property
    def summary_metrics(self) -> dict[str, float | None]:
        """Return structured aggregate benchmark metrics."""

        try:
            parsed = json.loads(self.summary_metrics_json)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}


class WorkflowMemoryItem(Base):
    """A retrieval-backed memory entry derived from confirmed safe mappings."""

    __tablename__ = "workflow_memory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    workflow_type: Mapped[str] = mapped_column(
        String(50),
        default=WORKFLOW_TYPE_FORM_FILL,
        nullable=False,
    )
    source_domain: Mapped[Optional[str]] = mapped_column(String(300))
    field_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    field_text: Mapped[str] = mapped_column(Text, nullable=False)
    mapped_profile_key: Mapped[str] = mapped_column(String(100), nullable=False)
    value_kind: Mapped[str] = mapped_column(String(50), default="profile_value", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class KnowledgeSource(Base):
    """A user-uploaded document used as retrieval evidence."""

    __tablename__ = "knowledge_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), default="text/plain", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )


class KnowledgeChunk(Base):
    """A searchable section from a user-uploaded knowledge source."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("knowledge_sources.id"), nullable=False)
    section_title: Mapped[str] = mapped_column(String(500), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    source: Mapped["KnowledgeSource"] = relationship(back_populates="chunks")


class BenchmarkCaseResult(Base):
    """Metrics and failures for one benchmark case in a run."""

    __tablename__ = "benchmark_case_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("benchmark_runs.id"), nullable=False)
    case_id: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    metrics_json: Mapped[str] = mapped_column("metrics", Text, nullable=False)
    failures_json: Mapped[str] = mapped_column("failures", Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    run: Mapped["BenchmarkRun"] = relationship(back_populates="case_results")

    @property
    def metrics(self) -> dict[str, float]:
        """Return structured metrics for this case."""

        try:
            parsed = json.loads(self.metrics_json)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @property
    def failures(self) -> list[dict[str, object]]:
        """Return structured failure details for this case."""

        try:
            parsed = json.loads(self.failures_json)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []


class TaskActionTrace(Base):
    """Detailed admin-only trace of browser automation actions."""

    __tablename__ = "task_action_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    selector: Mapped[Optional[str]] = mapped_column(String(1000))
    field_id: Mapped[Optional[int]] = mapped_column(Integer)
    input_value: Mapped[Optional[str]] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    screenshot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("screenshots.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WorkflowSpan(Base):
    """A queryable workflow trace span for one task run."""

    __tablename__ = "workflow_spans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    parent_span_id: Mapped[Optional[int]] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    input_json: Mapped[Optional[str]] = mapped_column(Text)
    output_json: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    screenshot_id: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    task: Mapped["Task"] = relationship(back_populates="workflow_spans")

    @property
    def input(self) -> dict[str, object]:
        """Return structured input data from JSON."""

        if not self.input_json:
            return {}
        try:
            parsed = json.loads(self.input_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    @input.setter
    def input(self, value: dict[str, object] | None) -> None:
        """Persist structured input as JSON."""

        self.input_json = json.dumps(value or {}, ensure_ascii=False)

    @property
    def output(self) -> dict[str, object]:
        """Return structured output data from JSON."""

        if not self.output_json:
            return {}
        try:
            parsed = json.loads(self.output_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    @output.setter
    def output(self, value: dict[str, object] | None) -> None:
        """Persist structured output as JSON."""

        self.output_json = json.dumps(value or {}, ensure_ascii=False)

    @property
    def span_metadata(self) -> dict[str, object]:
        """Return structured metadata from JSON."""

        if not self.metadata_json:
            return {}
        try:
            parsed = json.loads(self.metadata_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    @span_metadata.setter
    def span_metadata(self, value: dict[str, object] | None) -> None:
        """Persist structured metadata as JSON."""

        self.metadata_json = json.dumps(value or {}, ensure_ascii=False)


class ApprovalRequest(Base):
    """A persisted approval gate for risky workflow actions."""

    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    step_name: Mapped[str] = mapped_column(String(150), nullable=False)
    risk_type: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_action_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    task: Mapped["Task"] = relationship(back_populates="approval_requests")

    @property
    def proposed_action(self) -> dict[str, object]:
        """Return structured approval payload from JSON."""

        if not self.proposed_action_json:
            return {}
        try:
            parsed = json.loads(self.proposed_action_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    @proposed_action.setter
    def proposed_action(self, value: dict[str, object] | None) -> None:
        """Persist proposed action as JSON."""

        self.proposed_action_json = json.dumps(
            value or {},
            ensure_ascii=False,
            sort_keys=True,
        )


class TaskCheckpoint(Base):
    """A recoverable stage result for one task workflow."""

    __tablename__ = "task_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    input_hash: Mapped[Optional[str]] = mapped_column(String(64))
    output_json: Mapped[Optional[str]] = mapped_column(Text)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(100))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    task: Mapped["Task"] = relationship(back_populates="checkpoints")

    @property
    def output(self) -> dict[str, object]:
        """Return structured output data from JSON, safely handling invalid JSON."""

        if not self.output_json:
            return {}
        try:
            parsed = json.loads(self.output_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    @output.setter
    def output(self, value: dict[str, object] | None) -> None:
        """Persist structured output as JSON."""

        self.output_json = json.dumps(value or {}, ensure_ascii=False)


class Job(Base):
    """An asynchronous job for long-running workflow tasks."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"))
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload_json: Mapped[Optional[str]] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    locked_by: Mapped[Optional[str]] = mapped_column(String(100))
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_reason: Mapped[Optional[str]] = mapped_column(String(100))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    task: Mapped[Optional["Task"]] = relationship(back_populates="jobs")
    attempts_list: Mapped[list["JobAttempt"]] = relationship(back_populates="job")

    @property
    def payload(self) -> dict[str, object]:
        """Return structured payload data from JSON."""

        if not self.payload_json:
            return {}
        try:
            parsed = json.loads(self.payload_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    @payload.setter
    def payload(self, value: dict[str, object] | None) -> None:
        """Persist structured payload as JSON."""

        self.payload_json = json.dumps(value or {}, ensure_ascii=False)


class JobAttempt(Base):
    """Record of one execution attempt for a job."""

    __tablename__ = "job_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_reason: Mapped[Optional[str]] = mapped_column(String(100))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    job: Mapped["Job"] = relationship(back_populates="attempts_list")


class WorkerHeartbeat(Base):
    """Heartbeat record tracking a worker's availability and current workload."""

    __tablename__ = "worker_heartbeats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[str] = mapped_column(String(100), nullable=False)
    hostname: Mapped[Optional[str]] = mapped_column(String(200))
    current_job_id: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


VERIFICATION_STATUS_VERIFIED = "VERIFIED"
VERIFICATION_STATUS_PARTIAL = "PARTIAL"
VERIFICATION_STATUS_FAILED = "FAILED"
VERIFICATION_STATUS_SKIPPED = "SKIPPED"

VERIFICATION_REASON_SELECTOR_NOT_FOUND = "SELECTOR_NOT_FOUND"
VERIFICATION_REASON_VALUE_MISMATCH = "VALUE_MISMATCH"
VERIFICATION_REASON_OPTION_NOT_SELECTED = "OPTION_NOT_SELECTED"
VERIFICATION_REASON_FIELD_DISABLED = "FIELD_DISABLED"
VERIFICATION_REASON_SENSITIVE_FIELD_SKIPPED = "SENSITIVE_FIELD_SKIPPED"
VERIFICATION_REASON_PAGE_NAVIGATED_UNEXPECTEDLY = "PAGE_NAVIGATED_UNEXPECTEDLY"


class FieldVerificationResult(Base):
    """Post-fill verification result for one form field."""

    __tablename__ = "field_verification_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    field_id: Mapped[Optional[int]] = mapped_column(Integer)
    selector: Mapped[str] = mapped_column(String(1000), nullable=False)
    expected_value_hash: Mapped[Optional[str]] = mapped_column(String(64))
    actual_value_hash: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(100))
    message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    task: Mapped["Task"] = relationship(back_populates="verification_results")


class AgentReview(Base):
    """Review decision from an AI agent for a form automation task."""

    __tablename__ = "agent_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_json: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(100))
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    task: Mapped["Task"] = relationship(back_populates="agent_reviews")

    @property
    def output(self) -> dict[str, object]:
        """Return structured output data from JSON, safely handling invalid JSON."""

        if not self.output_json:
            return {}
        try:
            parsed = json.loads(self.output_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed
