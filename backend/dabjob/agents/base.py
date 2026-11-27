"""The task envelope and the schemas a transport must satisfy.

One envelope, three transports (manual, an OpenAI-compatible endpoint, an
agent CLI). What changes between them is how the answer is produced; what
does not change is the shape of the question or of the answer.

Nothing here imports a model library, and nothing here needs a network.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, ValidationError

TaskName = Literal["analyze_profile", "analyze_job", "synthesize_skills"]

TASKS: tuple[TaskName, ...] = ("analyze_profile", "analyze_job", "synthesize_skills")

SCHEMA_VERSION = 1


class Constraints(BaseModel):
    """What the transport is allowed to do.

    ``tools`` is pinned to ``none`` for analysis: a posting is untrusted, and
    an agent holding tools while reading one is the case the roadmap forbids.
    """

    tools: Literal["none"] = "none"
    max_output_tokens: int = Field(default=4000, ge=1, le=100_000)


class TaskEnvelope(BaseModel):
    task: TaskName
    schema_version: int = SCHEMA_VERSION
    input: dict[str, Any]
    constraints: Constraints = Field(default_factory=Constraints)


class ProfileAnalysis(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    target_fit: str = ""
    positioning: str = ""


class JobAnalysis(BaseModel):
    summary: str = ""
    rationale: str = ""
    outlook: str = ""
    # The rule score is the score. A transport may nudge it, within bounds,
    # and must say why in ``rationale``.
    adjustment: float = Field(default=0.0, ge=-10, le=10)


class SkillMapping(BaseModel):
    term: str
    canonical: str
    confidence: float = Field(default=1.0, ge=0, le=1)


class SkillSynthesis(BaseModel):
    mappings: list[SkillMapping] = Field(default_factory=list)
    unmatched: list[str] = Field(default_factory=list)


OUTPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "analyze_profile": ProfileAnalysis,
    "analyze_job": JobAnalysis,
    "synthesize_skills": SkillSynthesis,
}


class Transport(Protocol):
    """Anything that can answer an envelope with text.

    Text rather than an object on purpose: an HTTP endpoint and a CLI both
    return text, and validating it in one place is what keeps them honest.
    """

    name: str

    def complete(self, envelope: TaskEnvelope) -> str: ...


class OutputInvalid(ValueError):
    """The transport answered, but not with something the schema accepts."""


def validate_output(task: TaskName, text: str) -> BaseModel:
    schema = OUTPUT_SCHEMAS[task]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise OutputInvalid(f"not JSON: {error}") from error

    try:
        return schema.model_validate(payload)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in item['loc']) or 'root'}: {item['msg']}"
            for item in error.errors()
        )
        raise OutputInvalid(problems) from error
