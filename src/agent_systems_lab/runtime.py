"""Checkpointed agent execution loop."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .model import AgentModel
from .redaction import redact
from .state import RunState, RunStore
from .tools import ToolPolicyError, WorkspaceTools


@dataclass(frozen=True)
class RunResult:
    run_dir: Path
    status: str
    summary: str
    steps_completed: int


class AgentRuntime:
    """Runs one task, saving state after every decision and tool outcome."""

    def __init__(self, model: AgentModel, tools: WorkspaceTools, *, max_steps: int = 20) -> None:
        self.model = model
        self.tools = tools
        self.max_steps = max_steps

    def start(self, *, task: str, runs_root: Path) -> RunResult:
        state = RunState.new(task, self.tools.policy.workspace)
        store = RunStore(runs_root / state.run_id)
        store.initialize(state)
        return self._run(store, state)

    def resume(self, run_dir: Path) -> RunResult:
        store = RunStore(run_dir)
        state = store.load()
        if state.status != "running":
            return RunResult(run_dir, state.status, state.final_summary, state.next_step)
        seek = getattr(self.model, "seek", None)
        if callable(seek):
            seek(state.next_step)
        store.trace("run_resumed", {"next_step": state.next_step})
        return self._run(store, state)

    def _run(self, store: RunStore, state: RunState) -> RunResult:
        while state.next_step < self.max_steps:
            try:
                action = self.model.next_action(task=state.task, observations=state.observations)
            except Exception as error:
                return self._fail(store, state, "model_error", f"{type(error).__name__}: {error}")
            store.trace(
                "model_action",
                {
                    "step": state.next_step,
                    "kind": action.kind,
                    "tool": action.tool,
                    "arguments": action.arguments or {},
                    "summary": action.summary,
                },
            )
            if action.kind == "finish":
                state.status = "succeeded"
                state.final_summary = action.summary or "Agent declared task complete."
                store.save(state)
                store.report(state)
                return RunResult(store.run_dir, state.status, state.final_summary, state.next_step)
            if action.kind != "tool" or not action.tool or action.arguments is None:
                return self._fail(store, state, "invalid_action", "Invalid agent action.")

            try:
                outcome = self.tools.dispatch(action.tool, action.arguments)
            except (KeyError, OSError, ToolPolicyError, subprocess.SubprocessError) as error:
                category = "tool_policy" if isinstance(error, ToolPolicyError) else "tool_execution"
                outcome_text = str(redact(f"{type(error).__name__}: {error}"))
                state.observations.append({"tool": action.tool, "ok": "false", "output": outcome_text})
                state.failures.append({"step": str(state.next_step), "category": category, "detail": outcome_text})
                store.trace(
                    "tool_error",
                    {"step": state.next_step, "tool": action.tool, "category": category, "error": outcome_text},
                )
            else:
                output = str(redact(outcome.output))
                state.observations.append({"tool": action.tool, "ok": str(outcome.ok).lower(), "output": output})
                store.trace(
                    "tool_result",
                    {"step": state.next_step, "tool": action.tool, "ok": outcome.ok, "output": output},
                )
            state.next_step += 1
            store.save(state)

        return self._fail(store, state, "step_budget", f"Step budget exhausted ({self.max_steps}).")

    @staticmethod
    def _fail(store: RunStore, state: RunState, category: str, reason: str) -> RunResult:
        state.status = "failed"
        state.final_summary = str(redact(reason))
        state.failures.append({"step": str(state.next_step), "category": category, "detail": state.final_summary})
        store.save(state)
        store.report(state)
        store.trace("run_failed", {"category": category, "reason": state.final_summary})
        return RunResult(store.run_dir, state.status, state.final_summary, state.next_step)
