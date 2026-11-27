"""Transport selection.

``manual`` is the default and the only one implemented so far. Asking for a
transport that does not exist yet is an error rather than a silent fallback:
silently scoring on rules when the user configured a model would be the
worst of both.
"""

from __future__ import annotations

from ..config import Settings
from .base import Transport
from .manual import ManualTransport

IMPLEMENTED = ("manual",)


def make_transport(settings: Settings) -> Transport:
    name = settings.agent_provider.strip().lower()
    if name in ("", "manual"):
        return ManualTransport()
    raise ValueError(
        f"AGENT_PROVIDER={name!r} is not implemented yet. "
        f"Available: {', '.join(IMPLEMENTED)}. "
        "The http and cli transports arrive in M3 and M8."
    )
