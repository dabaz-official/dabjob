"""An OpenAI-compatible endpoint as a transport.

Anything that speaks `/v1/chat/completions` works: Ollama, LM Studio, vLLM,
OpenRouter, DeepSeek, a gateway. That is the whole reason the contract is
text-in/text-out rather than a vendor SDK.

The endpoint is asked for a single JSON object and told the schema. Small
local models still wrap it in a code fence or add a sentence, so the fences
are stripped here and anything else is left for validation to reject — the
runner retries once and then records the raw answer.
"""

from __future__ import annotations

import json
from typing import Any

import httpx2

from .base import OUTPUT_SCHEMAS, TaskEnvelope

SYSTEM_PROMPT = (
    "You analyse job-search data. Reply with exactly one JSON object and "
    "nothing else: no prose, no explanation, no code fences."
)

_FENCE = ("```json", "```")


class HttpTransport:
    name = "http"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 120.0,
        client: Any | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        if not model:
            raise ValueError("AGENT_MODEL is not set; the http transport needs a model name")
        if not base_url:
            raise ValueError("AGENT_BASE_URL is not set")

        self.base_url = base_url.rstrip("/")
        self.model = model
        self._api_key = api_key
        self._timeout = timeout
        self._client = client
        self._extra_headers = dict(extra_headers or {})
        self.last_usage: tuple[int, int] | None = None

    def complete(self, envelope: TaskEnvelope) -> str:
        response = self._post(self._payload(envelope))
        self.last_usage = _usage(response)

        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError(f"unexpected response shape: {response!r:.300}") from error

        return _strip_fences(str(content))

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        headers = {"content-type": "application/json", **self._extra_headers}
        if self._api_key:
            headers["authorization"] = f"Bearer {self._api_key}"

        if self._client is not None:
            injected = self._client.post(url, json=payload, headers=headers)
            return dict(injected.json())

        with httpx2.Client(timeout=self._timeout) as client:
            result = client.post(url, json=payload, headers=headers)
            if result.status_code >= 400:
                raise ValueError(f"{url} returned {result.status_code}: {result.text[:300]}")
            return dict(result.json())

    def _payload(self, envelope: TaskEnvelope) -> dict[str, Any]:
        schema = OUTPUT_SCHEMAS[envelope.task].model_json_schema()
        return {
            "model": self.model,
            "temperature": 0,
            "max_tokens": envelope.constraints.max_output_tokens,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Task: {envelope.task}\n"
                        f"Schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
                        f"Input:\n{json.dumps(envelope.input, ensure_ascii=False)}"
                    ),
                },
            ],
        }


def _usage(response: dict[str, Any]) -> tuple[int, int] | None:
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    if isinstance(prompt, int) and isinstance(completion, int):
        return (prompt, completion)
    return None


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned
    cleaned = cleaned.removeprefix("```json").removeprefix("```")
    return cleaned.removesuffix("```").strip()
