"""SQLAlchemy models for profiles and form automation tasks."""

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


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
    status: Mapped[str] = mapped_column(String(50), default="CREATED", nullable=False)
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
