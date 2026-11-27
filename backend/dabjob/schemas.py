"""Request and response bodies. Kept separate from the ORM so a schema change
does not silently change the API."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import PipelineStatus


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company_name: str
    city: str | None = None
    platform: str
    url: str | None = None
    salary_text: str | None = None
    captured_at: datetime
    snippet: str | None = None


class JobList(BaseModel):
    items: list[JobSummary]
    total: int = Field(description="Number of items returned, not the size of the table")


class JobUpdate(BaseModel):
    """Only the fields present in the body are written.

    A field set to null clears it; a field left out is untouched. Without
    that distinction a rename form would wipe the city every time.
    """

    title: str | None = Field(default=None, min_length=1, max_length=255)
    company_name: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    url: str | None = None
    salary_text: str | None = Field(default=None, max_length=255)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    seniority: str | None = Field(default=None, max_length=64)


class ApplicationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    status: PipelineStatus
    channel: str | None = None
    resume_version: str | None = None
    next_follow_up_on: date | None = None
    created_at: datetime
    updated_at: datetime


class ApplicationList(BaseModel):
    items: list[ApplicationSummary]
    total: int


class ApplicationCreate(BaseModel):
    job_id: int
    status: PipelineStatus = PipelineStatus.SAVED


class ApplicationUpdate(BaseModel):
    status: PipelineStatus | None = None
    channel: str | None = Field(default=None, max_length=64)
    resume_version: str | None = Field(default=None, max_length=120)
    next_follow_up_on: date | None = None
