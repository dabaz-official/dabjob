"""Request and response bodies. Kept separate from the ORM so a schema change
does not silently change the API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
