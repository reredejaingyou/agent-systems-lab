"""Model-facing types.

The runtime consumes structured actions so model providers remain replaceable and
tests can run without network credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Action:
    """One agent decision."""

    kind: str
    tool: str | None = None
    arguments: dict[str, str] | None = None
    summary: str = ""

    @classmethod
    def finish(cls, summary: str) -> "Action":
        return cls(kind="finish", summary=summary)

    @classmethod
    def call(cls, tool: str, arguments: dict[str, str], summary: str = "") -> "Action":
        return cls(kind="tool", tool=tool, arguments=arguments, summary=summary)


class AgentModel(Protocol):
    """A model policy that selects the next structured action."""

    def next_action(self, *, task: str, observations: list[dict[str, str]]) -> Action:
        """Return the next action for a task and prior observations."""


class ScriptedModel:
    """Deterministic local policy used for tests and credential-free demos."""

    def __init__(self, actions: list[Action]) -> None:
        self._actions = actions
        self._position = 0

    @classmethod
    def from_json_file(cls, path: Path) -> "ScriptedModel":
        import json

        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Plan must be a JSON array of actions.")
        actions = [
            Action(
                kind=item["kind"],
                tool=item.get("tool"),
                arguments=item.get("arguments"),
                summary=item.get("summary", ""),
            )
            for item in raw
        ]
        return cls(actions)

    def next_action(self, *, task: str, observations: list[dict[str, str]]) -> Action:
        if self._position >= len(self._actions):
            return Action.finish("Scripted plan exhausted.")
        action = self._actions[self._position]
        self._position += 1
        return action

    def seek(self, completed_steps: int) -> None:
        """Advance a deterministic plan when resuming a stored run."""
        self._position = min(max(completed_steps, 0), len(self._actions))
