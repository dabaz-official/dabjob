"""Run one envelope and record what happened.

Every call becomes an ``agent_task`` row whether it succeeds or not: an
answer nobody can trace back to a transport, a model and an input is an
answer the user has to take on faith.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import AgentTask, AgentTaskStatus, utcnow
from .base import OutputInvalid, TaskEnvelope, Transport, validate_output

ATTEMPTS = 2


def run_task(
    session: Session,
    transport: Transport,
    envelope: TaskEnvelope,
    *,
    job_id: int | None = None,
) -> AgentTask:
    task = AgentTask(
        kind=envelope.task,
        transport=transport.name,
        status=AgentTaskStatus.RUNNING,
        # The task's payload, not the whole envelope: kind and transport are
        # already columns, and nesting the payload under "input" inside an
        # "input" column makes the audit row harder to read, not easier.
        input=envelope.input,
        job_id=job_id,
    )
    session.add(task)
    session.flush()

    last_error = ""
    for _attempt in range(ATTEMPTS):
        try:
            raw = transport.complete(envelope)
        except Exception as error:  # a transport is foreign code
            last_error = f"{type(error).__name__}: {error}"
            task.status = AgentTaskStatus.FAILED
            task.error = last_error
            continue

        task.raw_output = raw
        try:
            output = validate_output(envelope.task, raw)
        except OutputInvalid as error:
            last_error = str(error)
            task.status = AgentTaskStatus.FAILED
            task.error = last_error
            continue

        task.output = output.model_dump(mode="json")
        task.status = AgentTaskStatus.SUCCEEDED
        task.error = None
        usage = getattr(transport, "last_usage", None)
        if isinstance(usage, tuple) and len(usage) == 2:
            task.tokens_in, task.tokens_out = usage
        break

    task.finished_at = utcnow()
    session.commit()
    return task
