from __future__ import annotations

import json
from typing import Any

import pytest

from dabjob.agents import make_transport
from dabjob.agents.base import OutputInvalid, TaskEnvelope, validate_output
from dabjob.agents.contract import assert_contract, sample_envelope
from dabjob.agents.http import HttpTransport, _strip_fences
from dabjob.agents.runner import run_task
from dabjob.config import Settings
from dabjob.models import AgentTaskStatus


class FakeResponse:
    def __init__(self, body: Any, status_code: int = 200) -> None:
        self._body = body
        self.status_code = status_code
        self.text = json.dumps(body) if not isinstance(body, str) else body
        self.json_body = body

    def json(self) -> Any:
        if isinstance(self._body, str):
            raise ValueError("not json")
        return self._body


class FakeClient:
    """Stands in for httpx2.Client so no test touches a network."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, json: Any = None, headers: Any = None) -> FakeResponse:  # noqa: A002
        self.calls.append({"url": url, "json": json, "headers": headers})
        return self._responses[min(len(self.calls) - 1, len(self._responses) - 1)]


def _completion(content: str, usage: dict[str, int] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"choices": [{"message": {"content": content}}]}
    if usage:
        body["usage"] = usage
    return body


def _transport(responses: list[FakeResponse]) -> HttpTransport:
    return HttpTransport(
        base_url="http://model.test/v1",
        model="test-model",
        api_key="secret",
        client=FakeClient(responses),
    )


def test_the_http_transport_satisfies_the_contract() -> None:
    payload = json.dumps({"strengths": ["a"], "gaps": [], "target_fit": "", "positioning": ""})
    assert_contract(_transport([FakeResponse(_completion(payload))]))  # type: ignore[arg-type]


def test_the_request_carries_the_model_the_schema_and_the_input() -> None:
    transport = _transport([FakeResponse(_completion('{"summary": "ok"}'))])

    transport.complete(
        TaskEnvelope(task="analyze_job", input={"title": "Backend", "jd_text": "Python"})
    )

    call = transport._client.calls[0]  # type: ignore[union-attr]
    assert call["url"] == "http://model.test/v1/chat/completions"
    assert call["json"]["model"] == "test-model"
    assert call["json"]["temperature"] == 0
    assert call["headers"]["authorization"] == "Bearer secret"
    user = call["json"]["messages"][1]["content"]
    assert "analyze_job" in user
    assert "Python" in user
    assert "properties" in user  # the JSON schema is included


def test_a_code_fence_is_stripped() -> None:
    fenced = '```json\n{"summary": "ok"}\n```'

    assert _strip_fences(fenced) == '{"summary": "ok"}'


def test_a_fenced_answer_still_validates() -> None:
    fenced = '```json\n{"summary": "ok", "adjustment": 3}\n```'
    transport = _transport([FakeResponse(_completion(fenced))])

    raw = transport.complete(sample_envelope("analyze_job"))

    assert validate_output("analyze_job", raw).model_dump()["adjustment"] == 3


def test_usage_is_recorded_on_the_transport() -> None:
    transport = _transport(
        [
            FakeResponse(
                _completion('{"summary": "ok"}', {"prompt_tokens": 120, "completion_tokens": 30})
            )
        ]
    )

    transport.complete(sample_envelope("analyze_job"))

    assert transport.last_usage == (120, 30)


def test_the_runner_persists_the_token_counts(session) -> None:  # type: ignore[no-untyped-def]
    transport = _transport(
        [
            FakeResponse(
                _completion('{"summary": "ok"}', {"prompt_tokens": 7, "completion_tokens": 3})
            )
        ]
    )

    task = run_task(session, transport, sample_envelope("analyze_job"))

    assert task.status is AgentTaskStatus.SUCCEEDED
    assert (task.tokens_in, task.tokens_out) == (7, 3)


def test_a_missing_model_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="AGENT_MODEL"):
        HttpTransport(base_url="http://model.test/v1", model="")


def test_make_transport_builds_the_http_transport() -> None:
    settings = Settings(
        agent_provider="http",
        agent_base_url="http://model.test/v1",
        agent_model="test-model",
    )

    transport = make_transport(settings)

    assert isinstance(transport, HttpTransport)


def test_a_bad_response_shape_is_a_failure_not_a_crash(session) -> None:  # type: ignore[no-untyped-def]
    transport = _transport([FakeResponse({"unexpected": True})])

    task = run_task(session, transport, sample_envelope("analyze_job"))

    assert task.status is AgentTaskStatus.FAILED
    assert task.error is not None and "unexpected response shape" in task.error


def test_prose_instead_of_json_is_rejected() -> None:
    with pytest.raises(OutputInvalid):
        validate_output("analyze_job", "Sure! Here is the analysis you asked for.")


def test_extra_headers_are_sent() -> None:
    """OpenCode Zen asks for x-opencode-session; the OpenAI spec has no place for it."""
    transport = HttpTransport(
        base_url="http://model.test/v1",
        model="test-model",
        client=FakeClient([FakeResponse(_completion('{"summary": "ok"}'))]),
        extra_headers={"x-opencode-session": "abc"},
    )

    transport.complete(sample_envelope("analyze_job"))

    call = transport._client.calls[0]  # type: ignore[union-attr]
    assert call["headers"]["x-opencode-session"] == "abc"


def test_headers_come_from_the_documented_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_HEADERS", '{"x-opencode-session": "abc"}')

    settings = Settings()

    assert settings.agent_headers == {"x-opencode-session": "abc"}
