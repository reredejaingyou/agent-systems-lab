"""OpenAI-compatible model adapter with strict structured-action parsing."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from .model import Action


class ModelProviderError(RuntimeError):
    """A model provider request or response could not be used safely."""


def _strip_code_fence(content: str) -> str:
    match = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", content, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else content.strip()


def parse_action(content: str) -> Action:
    """Parse one model response into the runtime's intentionally small action schema."""
    try:
        raw = json.loads(_strip_code_fence(content))
    except json.JSONDecodeError as error:
        raise ModelProviderError("Model response is not valid JSON.") from error
    if not isinstance(raw, dict):
        raise ModelProviderError("Model response must be a JSON object.")

    kind = raw.get("kind")
    summary = raw.get("summary", "")
    if not isinstance(kind, str) or not isinstance(summary, str):
        raise ModelProviderError("Action requires string fields 'kind' and 'summary'.")
    if kind == "finish":
        return Action.finish(summary)
    if kind != "tool":
        raise ModelProviderError("Action kind must be 'tool' or 'finish'.")

    tool = raw.get("tool")
    arguments = raw.get("arguments")
    if not isinstance(tool, str) or not isinstance(arguments, dict):
        raise ModelProviderError("Tool actions require string 'tool' and object 'arguments'.")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in arguments.items()):
        raise ModelProviderError("Tool arguments must be a string-to-string object.")
    return Action.call(tool, arguments, summary)


@dataclass
class OpenAICompatibleModel:
    """Calls the OpenAI chat-completions shape without persisting credentials."""

    model: str
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: int = 60
    transport: Callable[[str, str, dict[str, str], int], str] | None = None

    @classmethod
    def from_environment(
        cls,
        *,
        model: str | None = None,
        base_url: str | None = None,
    ) -> "OpenAICompatibleModel":
        api_key = os.environ.get("ASL_OPENAI_API_KEY", "")
        resolved_model = model or os.environ.get("ASL_OPENAI_MODEL", "")
        if not api_key:
            raise ModelProviderError("Set ASL_OPENAI_API_KEY before using the OpenAI-compatible provider.")
        if not resolved_model:
            raise ModelProviderError("Pass --model or set ASL_OPENAI_MODEL.")
        return cls(
            model=resolved_model,
            api_key=api_key,
            base_url=base_url or os.environ.get("ASL_OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )

    def next_action(self, *, task: str, observations: list[dict[str, str]]) -> Action:
        compact_observations = observations[-8:]
        prompt = {
            "task": task,
            "observations": compact_observations,
            "tools": {
                "read_file": {"path": "relative workspace path"},
                "write_file": {"path": "relative workspace path", "content": "text"},
                "run_shell": {"command": "single allowlisted command without shell operators"},
            },
            "response_schema": {
                "kind": "tool | finish",
                "tool": "required only for kind=tool",
                "arguments": "required string-to-string object only for kind=tool",
                "summary": "short explanation",
            },
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a bounded software-engineering agent. Return exactly one JSON object. "
                    "Use a tool only when necessary. Never include credentials or secrets."
                ),
            },
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ]
        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "temperature": 0,
                "response_format": {"type": "json_object"},
            }
        )
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        response = self._request(payload, headers)
        try:
            content = json.loads(response)["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ModelProviderError("Provider response does not contain choices[0].message.content.") from error
        if not isinstance(content, str):
            raise ModelProviderError("Provider returned a non-string message content.")
        return parse_action(content)

    def _request(self, payload: str, headers: dict[str, str]) -> str:
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        if self.transport:
            return self.transport(endpoint, payload, headers, self.timeout_seconds)
        request = urllib.request.Request(endpoint, data=payload.encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read().decode("utf-8")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            raise ModelProviderError(f"Model provider request failed: {error}") from error
