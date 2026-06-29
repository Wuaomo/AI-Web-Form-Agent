"""Pydantic models used by the API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ProfileKey = Literal[
    "first_name",
    "last_name",
    "full_name",
    "email",
    "university",
    "major",
    "phone",
    "linkedin",
    "github",
    "self_intro",
]


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
    required: bool
    mapped_profile_key: str | None
    mapped_value: str | None
    confidence: float | None


class FormFieldMappingUpdate(BaseModel):
    """User-editable parts of a form field mapping."""

    mapped_profile_key: ProfileKey | None = None
    mapped_value: str | None = None

    @model_validator(mode="after")
    def require_an_update(self) -> "FormFieldMappingUpdate":
        """Reject an empty JSON object while still allowing explicit nulls."""

        if not self.model_fields_set:
            raise ValueError("Provide mapped_profile_key or mapped_value")
        return self


class MappingConfirmationResponse(BaseModel):
    """Task status returned after the user confirms the mapping."""

    task_id: int
    status: str


class SubmissionConfirmationResponse(BaseModel):
    """Task status returned after the user confirms submission."""

    task_id: int
    status: str


class TaskCreate(BaseModel):
    """Data required to create a form analysis task."""

    url: str
    profile_id: int
    description: str | None = None


class TaskResponse(BaseModel):
    """Task details including fields discovered during analysis."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    description: str | None
    profile_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    form_fields: list[FormFieldResponse] = Field(default_factory=list)
