"""The protocol is the contract; these tests are what keeps a future
transport from drifting away from it."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from dabjob.agents import make_transport
from dabjob.agents.base import OutputInvalid, TaskEnvelope, validate_output
from dabjob.agents.contract import assert_contract, sample_envelope
from dabjob.agents.manual import ManualTransport
from dabjob.agents.runner import run_task
from dabjob.config import Settings
from dabjob.models import AgentTask, AgentTaskStatus


class ScriptedTransport:
    """A transport that returns whatever the test tells it to."""

    name = "scripted"

    def __init__(self, answers: list[str]) -> None:
        self._answers = answers
        self.calls = 0

    def complete(self, envelope: TaskEnvelope) -> str:
        answer = self._answers[min(self.calls, len(self._answers) - 1)]
        self.calls += 1
        return answer


def test_manual_satisfies_the_transport_contract() -> None:
    assert_contract(ManualTransport())


def test_the_contract_rejects_a_transport_without_a_name() -> None:
    class Nameless:
        name = ""

        def complete(self, envelope: TaskEnvelope) -> str:
            return "{}"

    with pytest.raises(AssertionError, match="no name"):
        assert_contract(Nameless())


def test_an_unknown_task_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TaskEnvelope(task="write_my_cv", input={})  # type: ignore[arg-type]


def test_tools_are_pinned_off_for_analysis() -> None:
    with pytest.raises(ValidationError):
        TaskEnvelope(task="analyze_job", input={}, constraints={"tools": "bash"})  # type: ignore[arg-type]


def test_an_adjustment_outside_the_bounds_is_invalid() -> None:
    text = json.dumps({"summary": "ok", "adjustment": 50})

    with pytest.raises(OutputInvalid, match="adjustment"):
        validate_output("analyze_job", text)


def test_non_json_output_is_invalid() -> None:
    with pytest.raises(OutputInvalid, match="not JSON"):
        validate_output("analyze_job", "Here is your analysis!")


def test_the_runner_records_a_successful_task(session: Session) -> None:
    task = run_task(session, ManualTransport(), sample_envelope("analyze_job"))

    assert task.status is AgentTaskStatus.SUCCEEDED
    assert task.transport == "manual"
    assert task.output is not None
    assert task.raw_output is not None
    assert task.finished_at is not None

    stored = session.scalar(select(AgentTask).where(AgentTask.id == task.id))
    assert stored is not None
    assert stored.status is AgentTaskStatus.SUCCEEDED


def test_the_runner_retries_once_and_keeps_the_raw_answer(session: Session) -> None:
    transport = ScriptedTransport(["not json at all"])
    task = run_task(session, transport, sample_envelope("analyze_job"))

    assert transport.calls == 2
    assert task.status is AgentTaskStatus.FAILED
    assert task.raw_output == "not json at all"
    assert task.error is not None and "not JSON" in task.error


def test_a_second_attempt_can_succeed(session: Session) -> None:
    transport = ScriptedTransport(["nonsense", json.dumps({"summary": "ok"})])
    task = run_task(session, transport, sample_envelope("analyze_job"))

    assert transport.calls == 2
    assert task.status is AgentTaskStatus.SUCCEEDED
    assert task.output == {"summary": "ok", "rationale": "", "outlook": "", "adjustment": 0.0}


def test_a_transport_that_raises_is_recorded_not_propagated(session: Session) -> None:
    class Broken:
        name = "broken"

        def complete(self, envelope: TaskEnvelope) -> str:
            raise RuntimeError("endpoint refused")

    task = run_task(session, Broken(), sample_envelope("analyze_job"))

    assert task.status is AgentTaskStatus.FAILED
    assert task.error is not None and "endpoint refused" in task.error


def test_manual_is_the_default_transport() -> None:
    assert isinstance(make_transport(Settings()), ManualTransport)


def test_an_unimplemented_transport_fails_loudly() -> None:
    with pytest.raises(ValueError, match="not implemented"):
        make_transport(Settings(agent_provider="http"))


def test_agent_provider_is_read_from_the_documented_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_PROVIDER", "cli")

    assert Settings().agent_provider == "cli"
