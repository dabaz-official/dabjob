"""The integrity gate.

A job posting is not a document; it is an attacker-controlled document.
Postings carry zero-width characters, bidi overrides and lines shaped like
instructions to whatever model reads them next.

This module is deliberately plain Python: no model, no heuristics that need
a network call, and no way to switch it off. It removes characters that
carry no meaning to a human and flags lines that look like an instruction,
so the UI can show the user what was found.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Characters a human cannot see and a parser will happily keep.
ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u00ad]")
# Bidirectional overrides can reorder text after it has been copied.
BIDI = re.compile("[\u202a-\u202e\u2066-\u2069]")
CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

INSTRUCTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)\bignore\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above)\s+"
        r"(?:instructions?|prompts?|rules?|context)"
    ),
    re.compile(r"(?i)\bdisregard\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above)"),
    re.compile(
        r"(?i)\b(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\b.{0,40}"
        r"\b(?:assistant|ai|model|agent|system)\b"
    ),
    re.compile(r"(?i)\b(?:system|assistant|developer)\s*(?:prompt|message)\s*:"),
    re.compile(r"(?i)\bdo\s+not\s+(?:tell|inform|reveal\s+to)\s+the\s+user\b"),
    re.compile(r"(?i)\b(?:new|updated)\s+instructions?\s*:"),
    re.compile(r"忽略(?:以上|之前|前面|上述)?(?:的)?(?:所有)?(?:指令|提示|规则)"),
    re.compile(r"(?:系统|开发者)(?:提示|指令|消息)\s*[:：]"),
    re.compile(r"(?:不要|别)(?:告诉|通知)(?:用户|招聘者)"),
)

MAX_TEXT_CHARS = 200_000


@dataclass(frozen=True)
class GateResult:
    """Cleaned text plus what was found.

    ``flags`` is what the UI shows; ``flagged_lines`` is 1-based so it can be
    pointed at directly.
    """

    text: str
    flags: tuple[str, ...] = field(default_factory=tuple)
    flagged_lines: tuple[int, ...] = field(default_factory=tuple)

    @property
    def is_clean(self) -> bool:
        return not self.flags


def inspect(raw: str) -> GateResult:
    """Normalise the text and report what had to be removed or flagged."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    flags: list[str] = []

    text, removed = ZERO_WIDTH.subn("", text)
    if removed:
        flags.append(f"zero_width_chars_removed:{removed}")

    text, removed = BIDI.subn("", text)
    if removed:
        flags.append(f"bidi_controls_removed:{removed}")

    text, removed = CONTROL.subn("", text)
    if removed:
        flags.append(f"control_chars_removed:{removed}")

    flagged = tuple(
        number
        for number, line in enumerate(text.splitlines(), start=1)
        if any(pattern.search(line) for pattern in INSTRUCTION_PATTERNS)
    )
    if flagged:
        flags.append(f"instruction_shaped_lines:{len(flagged)}")

    return GateResult(text=text.strip(), flags=tuple(flags), flagged_lines=flagged)
