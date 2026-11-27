"""The default transport: no model, no network, a valid empty draft.

It exists so every screen works before anything is configured. The draft is
schema-valid and empty, which is exactly what "editable" means: the user
fills it in, and the fields are the same ones a model would have filled.
"""

from __future__ import annotations

import json

from .base import TaskEnvelope

_DRAFTS: dict[str, dict[str, object]] = {
    "analyze_profile": {
        "strengths": [],
        "gaps": [],
        "target_fit": "",
        "positioning": "",
    },
    "analyze_job": {"summary": "", "rationale": "", "outlook": "", "adjustment": 0.0},
    "synthesize_skills": {"mappings": [], "unmatched": []},
}


class ManualTransport:
    """Satisfies the contract without doing anything a model would do."""

    name = "manual"

    def complete(self, envelope: TaskEnvelope) -> str:
        return json.dumps(_DRAFTS[envelope.task], ensure_ascii=False)
