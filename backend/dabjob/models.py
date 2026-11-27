"""The schema, in one place.

Two things are deliberate here:

* enums are stored as their values in a VARCHAR with a CHECK constraint
  (``native_enum=False``), because a SQLite file is meant to be readable
  with a plain ``sqlite3`` shell;
* timestamps are timezone-aware UTC, because "two weeks quiet" is a
  subtraction that must not depend on where the machine is.
"""

from __future__ import annotations

import enum
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[str]: JSON}


def _enum(enum_type: type[enum.Enum], name: str) -> Enum:
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


class PipelineStatus(enum.StrEnum):
    SAVED = "saved"
    APPLIED = "applied"
    CHATTED = "chatted"
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    GHOSTED = "ghosted"
    DROPPED = "dropped"


class IngestSource(enum.StrEnum):
    BOOKMARKLET = "bookmarklet"
    PASTE = "paste"
    TABULAR = "tabular"
    IMPORTER = "importer"


class IngestStatus(enum.StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestOutcome(enum.StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class AgentTaskStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"


class AgentActionStatus(enum.StrEnum):
    PROPOSED = "proposed"
    APPLIED = "applied"
    REJECTED = "rejected"


class SkillLevel(enum.StrEnum):
    MET = "met"
    PARTIAL = "partial"
    MISSING = "missing"


class DocumentKind(enum.StrEnum):
    RESUME = "resume"
    SELF_INTRO = "self_intro"
    TARGETS = "targets"


class EventKind(enum.StrEnum):
    APPLIED = "applied"
    REPLIED = "replied"
    SCREENED = "screened"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    NOTE = "note"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


# ── The person ─────────────────────────────────────────────────────────────


class Profile(TimestampMixin, Base):
    """One row. The whole point of a single-user tool is that this is singular."""

    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    years_experience: Mapped[int | None] = mapped_column(Integer)
    target_roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    target_cities: Mapped[list[str]] = mapped_column(JSON, default=list)
    salary_floor: Mapped[int | None] = mapped_column(Integer)
    strengths: Mapped[str | None] = mapped_column(Text)
    gaps: Mapped[str | None] = mapped_column(Text)


class ProfileDocument(TimestampMixin, Base):
    __tablename__ = "profile_document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[DocumentKind] = mapped_column(_enum(DocumentKind, "document_kind"))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(120))
    extracted_text: Mapped[str | None] = mapped_column(Text)


# ── What you are looking at ────────────────────────────────────────────────


class Company(TimestampMixin, Base):
    __tablename__ = "company"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    industry: Mapped[str | None] = mapped_column(String(120))
    size: Mapped[str | None] = mapped_column(String(120))
    funding_stage: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)


class Job(TimestampMixin, Base):
    __tablename__ = "job"
    __table_args__ = (Index("ix_job_platform_external", "platform", "external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("company.id", ondelete="SET NULL"))

    platform: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(120))
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_text: Mapped[str | None] = mapped_column(String(255))
    seniority: Mapped[str | None] = mapped_column(String(64))
    jd_text: Mapped[str] = mapped_column(Text, default="")

    # Filled by the dedupe rule in M2; indexed now so the lookup is not a scan.
    fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Skill(TimestampMixin, Base):
    __tablename__ = "skill"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)


class JobSkill(Base):
    """Weight is per posting: the same skill matters more in some JDs."""

    __tablename__ = "job_skill"

    job_id: Mapped[int] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skill.id", ondelete="CASCADE"), primary_key=True
    )
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class JobAnalysis(TimestampMixin, Base):
    """One transport's verdict on one posting. Both a rule score and a note."""

    __tablename__ = "job_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), index=True)

    transport: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(120))

    skill_coverage: Mapped[float | None] = mapped_column(Float)
    salary_fit: Mapped[float | None] = mapped_column(Float)
    city_fit: Mapped[float | None] = mapped_column(Float)
    seniority_fit: Mapped[float | None] = mapped_column(Float)
    composite: Mapped[float | None] = mapped_column(Float)
    adjustment: Mapped[float | None] = mapped_column(Float)

    rationale: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    outlook: Mapped[str | None] = mapped_column(Text)


# ── What you did about it ──────────────────────────────────────────────────


class Application(TimestampMixin, Base):
    __tablename__ = "application"
    __table_args__ = (UniqueConstraint("job_id", name="uq_application_job"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"))
    status: Mapped[PipelineStatus] = mapped_column(
        _enum(PipelineStatus, "pipeline_status"), default=PipelineStatus.SAVED
    )
    channel: Mapped[str | None] = mapped_column(String(64))
    resume_version: Mapped[str | None] = mapped_column(String(120))
    next_follow_up_on: Mapped[date | None] = mapped_column(Date)


class ApplicationEvent(Base):
    __tablename__ = "application_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("application.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[EventKind] = mapped_column(_enum(EventKind, "event_kind"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    body: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ── Where it came from ─────────────────────────────────────────────────────


class IngestRun(TimestampMixin, Base):
    __tablename__ = "ingest_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[IngestSource] = mapped_column(_enum(IngestSource, "ingest_source"))
    adapter: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[IngestStatus] = mapped_column(
        _enum(IngestStatus, "ingest_status"), default=IngestStatus.RUNNING
    )
    accepted: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IngestItem(Base):
    __tablename__ = "ingest_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingest_run.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[IngestOutcome] = mapped_column(_enum(IngestOutcome, "ingest_outcome"))
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    gate_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ── What the agent did ─────────────────────────────────────────────────────


class AgentTask(TimestampMixin, Base):
    """One model or agent run. The audit trail for D11."""

    __tablename__ = "agent_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(64))
    transport: Mapped[str] = mapped_column(String(64))
    status: Mapped[AgentTaskStatus] = mapped_column(
        _enum(AgentTaskStatus, "agent_task_status"), default=AgentTaskStatus.QUEUED
    )
    job_id: Mapped[int | None] = mapped_column(ForeignKey("job.id", ondelete="SET NULL"))

    input: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    raw_output: Mapped[str | None] = mapped_column(Text)

    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentAction(Base):
    """A proposed mutation. Nothing applies without a decided_by (D11)."""

    __tablename__ = "agent_action"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("agent_task.id", ondelete="CASCADE"), index=True
    )
    tool: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[AgentActionStatus] = mapped_column(
        _enum(AgentActionStatus, "agent_action_status"), default=AgentActionStatus.PROPOSED
    )
    decided_by: Mapped[str | None] = mapped_column(String(64))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ── Configuration ──────────────────────────────────────────────────────────


class Setting(Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
