from __future__ import annotations

import json

import pytest

from agent_systems_lab.openai_compat import ModelProviderError, OpenAICompatibleModel, parse_action


def test_parse_action_accepts_fenced_tool_json() -> None:
    action = parse_action(
        """```json
        {"kind":"tool","tool":"write_file","arguments":{"path":"a.txt","content":"ok"},"summary":"write"}
        ```"""
    )
    assert action.kind == "tool"
    assert action.tool == "write_file"
    assert action.arguments == {"path": "a.txt", "content": "ok"}


def test_parse_action_rejects_non_string_tool_arguments() -> None:
    with pytest.raises(ModelProviderError, match="string-to-string"):
        parse_action('{"kind":"tool","tool":"run_shell","arguments":{"command":3},"summary":"bad"}')


def test_openai_compatible_model_uses_structured_response_without_leaking_key() -> None:
    recorded: dict[str, object] = {}

    def transport(endpoint: str, payload: str, headers: dict[str, str], timeout: int) -> str:
        recorded["endpoint"] = endpoint
        recorded["payload"] = json.loads(payload)
        recorded["headers"] = headers
        return json.dumps({"choices": [{"message": {"content": '{"kind":"finish","summary":"done"}'}}]})

    model = OpenAICompatibleModel(
        model="test-model",
        api_key="sk_this_is_a_fake_test_key",
        base_url="https://example.test/v1",
        transport=transport,
    )
    action = model.next_action(task="Finish safely.", observations=[])
    assert action.kind == "finish"
    assert recorded["endpoint"] == "https://example.test/v1/chat/completions"
    assert recorded["headers"] == {
        "Authorization": "Bearer sk_this_is_a_fake_test_key",
        "Content-Type": "application/json",
    }
