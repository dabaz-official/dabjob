"""A transport contract any implementation must pass.

Imported by the tests and quoted by CONTRIBUTING: a new transport is done
when this passes for it, not when it works once by hand.
"""

from __future__ import annotations

from .base import TASKS, TaskEnvelope, TaskName, Transport, validate_output

SAMPLE_INPUTS: dict[TaskName, dict[str, object]] = {
    "analyze_profile": {
        "resume_text": "Backend engineer, five years. Python, PostgreSQL, FastAPI.",
        "target_roles": ["Backend engineer"],
        "target_cities": ["Shanghai"],
    },
    "analyze_job": {
        "title": "Backend engineer",
        "company": "Example",
        "jd_text": "Python, PostgreSQL, FastAPI. Three to five years.",
    },
    "synthesize_skills": {
        "terms": ["fastapi", "pg", "k8s"],
    },
}


def sample_envelope(task: TaskName) -> TaskEnvelope:
    return TaskEnvelope(task=task, input=SAMPLE_INPUTS[task])


def assert_contract(transport: Transport) -> None:
    """Raise AssertionError describing the first thing the transport gets wrong."""
    if not getattr(transport, "name", ""):
        raise AssertionError("transport has no name")

    for task in TASKS:
        envelope = sample_envelope(task)
        raw = transport.complete(envelope)
        if not isinstance(raw, str):
            raise AssertionError(f"{transport.name}: {task} returned {type(raw).__name__}")
        validate_output(task, raw)
