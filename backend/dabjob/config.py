"""Application settings and the bind policy that protects them.

Two rules live here rather than in deployment documentation:

* every variable carries the ``DABJOB_`` prefix, so a stray shell variable
  cannot silently reconfigure the app;
* a non-loopback bind is refused unless it is asked for explicitly, because
  this server holds a résumé, a salary floor and a recruiter thread.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})


class Settings(BaseSettings):
    """Environment-backed settings, read once at startup."""

    model_config = SettingsConfigDict(
        env_prefix="DABJOB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    data_dir: Path = Path("data")
    host: str = "127.0.0.1"
    port: int = 8000
    allow_remote: bool = False
    token: str | None = None
    static_dir: Path = Path("frontend/dist")

    # Documented as AGENT_PROVIDER; the DABJOB_ form is accepted too so a
    # prefixed environment stays consistent.
    agent_provider: str = Field(
        default="manual",
        validation_alias=AliasChoices("AGENT_PROVIDER", "DABJOB_AGENT_PROVIDER"),
    )

    @property
    def database_url(self) -> str:
        """SQLite URL for the single database this app owns."""
        return f"sqlite:///{self.data_dir / 'app.db'}"


def is_loopback(host: str) -> bool:
    """Return True for an address that cannot be reached from the network."""
    normalized = host.strip().lower()
    return normalized in LOOPBACK_HOSTS or normalized.startswith("127.")


def enforce_bind_policy(settings: Settings) -> None:
    """Refuse to start on a reachable address without an explicit opt-in.

    Raising is intentional: a warning in a log is read by nobody, and the
    cost of a mistake here is publishing the database to the local network.
    """
    if settings.allow_remote or is_loopback(settings.host):
        return
    raise RuntimeError(
        f"Refusing to bind to {settings.host!r}: DabJob is local-only.\n"
        "Set DABJOB_ALLOW_REMOTE=1 only if you understand that the ingest "
        "endpoint and your job-search data become reachable from your network."
    )
