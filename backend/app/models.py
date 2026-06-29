"""SQLAlchemy models for profiles and form automation tasks."""

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="profile")


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


class Screenshot(Base):
    """A screenshot captured during task execution."""

    __tablename__ = "screenshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    task: Mapped["Task"] = relationship(back_populates="screenshots")
