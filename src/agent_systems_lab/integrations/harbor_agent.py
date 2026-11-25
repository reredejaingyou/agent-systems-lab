"""Harbor external-agent integration for Terminal-Bench 2.0.

Usage once Harbor is installed:

    harbor run --dataset terminal-bench@2.0 \
      --agent agent_systems_lab.integrations.harbor_agent:AgentSystemsLabHarborAgent \
      --model <provider/model> \
      --agent-env ASL_OPENAI_API_KEY=$ASL_OPENAI_API_KEY

The integration keeps the agent loop on the Harbor host and executes task
commands only through Harbor's `BaseEnvironment`. It writes a redacted JSONL
trajectory to Harbor's trial logs directory.
"""

from __future__ import annotations

import base64
import json
import os
import shlex
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from harbor.agents.base import BaseAgent
    from harbor.environments.base import BaseEnvironment
    from harbor.models.agent.context import AgentContext
except ImportError:  # pragma: no cover - exercised when Harbor is installed
    BaseAgent = object  # type: ignore[assignment,misc]
    BaseEnvironment = Any  # type: ignore[assignment,misc]
    AgentContext = Any  # type: ignore[assignment,misc]

from ..openai_compat import ModelProviderError, OpenAICompatibleModel
from ..redaction import redact


def _truncate(value: str, limit: int = 12_000) -> str:
    return value if len(value) <= limit else value[:limit] + "\n[truncated]"


def build_write_command(path: str, content: str) -> str:
    """Build a quoted shell command without embedding literal file content."""
    target = PurePosixPath(path)
    parent = str(target.parent) if str(target.parent) else "."
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    return (
        f"mkdir -p {shlex.quote(parent)} && "
        f"printf %s {shlex.quote(encoded)} | base64 -d > {shlex.quote(str(target))}"
    )


class AgentSystemsLabHarborAgent(BaseAgent):
    """Minimal external Harbor agent using Agent Systems Lab's action protocol."""

    max_steps: int = 20

    @staticmethod
    def name() -> str:
        return "agent-systems-lab"

    def version(self) -> str | None:
        return "0.3.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        result = await environment.exec(command="pwd", timeout_sec=15)
        self._trace("environment_ready", {"return_code": result.return_code, "cwd": _truncate(result.stdout)})

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        model = self._model()
        observations: list[dict[str, str]] = []
        failures: list[dict[str, str]] = []

        for step in range(self.max_steps):
            try:
                action = model.next_action(task=instruction, observations=observations)
            except ModelProviderError as error:
                failures.append({"category": "model_error", "detail": str(error)})
                self._trace("run_failed", {"step": step, "category": "model_error", "error": str(error)})
                self._set_context(context, status="failed", steps=step, failures=failures)
                return

            self._trace(
                "model_action",
                {
                    "step": step,
                    "kind": action.kind,
                    "tool": action.tool,
                    "arguments": action.arguments or {},
                    "summary": action.summary,
                },
            )
            if action.kind == "finish":
                self._trace("run_finished", {"step": step, "summary": action.summary})
                self._set_context(context, status="succeeded", steps=step, failures=failures)
                return

            try:
                output, ok = await self._dispatch(environment, action.tool or "", action.arguments or {})
            except (KeyError, ValueError, RuntimeError) as error:
                output, ok = f"{type(error).__name__}: {error}", False
                failures.append({"category": "tool_execution", "detail": output})

            safe_output = _truncate(str(redact(output)))
            observation = {"tool": action.tool or "", "ok": str(ok).lower(), "output": safe_output}
            observations.append(observation)
            self._trace("tool_result", {"step": step, **observation})

        failures.append({"category": "step_budget", "detail": f"Step budget exhausted ({self.max_steps})."})
        self._trace("run_failed", {"category": "step_budget", "steps": self.max_steps})
        self._set_context(context, status="failed", steps=self.max_steps, failures=failures)

    def _model(self) -> OpenAICompatibleModel:
        api_key = os.environ.get("ASL_OPENAI_API_KEY", "")
        model_name = self.model_name or os.environ.get("ASL_OPENAI_MODEL", "")
        if not api_key:
            raise ModelProviderError("ASL_OPENAI_API_KEY is required for Agent Systems Lab Harbor runs.")
        if not model_name:
            raise ModelProviderError("Pass Harbor --model or set ASL_OPENAI_MODEL.")
        return OpenAICompatibleModel(
            model=model_name,
            api_key=api_key,
            base_url=os.environ.get("ASL_OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )

    async def _dispatch(
        self,
        environment: BaseEnvironment,
        tool: str,
        arguments: dict[str, str],
    ) -> tuple[str, bool]:
        if tool == "read_file":
            command = f"cat -- {shlex.quote(arguments['path'])}"
        elif tool == "write_file":
            command = build_write_command(arguments["path"], arguments["content"])
        elif tool == "run_shell":
            command = arguments["command"]
        else:
            raise ValueError(f"Unknown tool: {tool}")

        result = await environment.exec(command=command, timeout_sec=120)
        return (result.stdout or "") + (result.stderr or ""), result.return_code == 0

    def _trace(self, event: str, payload: dict[str, object]) -> None:
        path = self.logs_dir / "agent-systems-lab.trace.jsonl"
        entry = redact({"event": event, **payload})
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")

    @staticmethod
    def _set_context(context: AgentContext, *, status: str, steps: int, failures: list[dict[str, str]]) -> None:
        context.metadata = {
            "agent_systems_lab": {
                "status": status,
                "steps": steps,
                "failure_count": len(failures),
                "failures": failures,
            }
        }
