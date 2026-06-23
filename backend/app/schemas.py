"""Pydantic models used by the API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Response returned by the health check endpoint."""

    status: Literal["ok"]


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
