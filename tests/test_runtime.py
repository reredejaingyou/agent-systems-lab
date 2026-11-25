from __future__ import annotations

import json
from pathlib import Path

from agent_systems_lab.model import Action, ScriptedModel
from agent_systems_lab.runtime import AgentRuntime
from agent_systems_lab.state import RunStore
from agent_systems_lab.tools import ToolPolicy, WorkspaceTools


def runtime(workspace: Path, actions: list[Action], max_steps: int = 10) -> AgentRuntime:
    return AgentRuntime(
        ScriptedModel(actions),
        WorkspaceTools(ToolPolicy(workspace)),
        max_steps=max_steps,
    )


def test_runtime_persists_trace_and_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    result = runtime(
        workspace,
        [
            Action.call("write_file", {"path": "answer.txt", "content": "42"}),
            Action.call("read_file", {"path": "answer.txt"}),
            Action.finish("Verified the requested file."),
        ],
    ).start(task="Write answer.txt.", runs_root=tmp_path / "runs")

    assert result.status == "succeeded"
    assert (workspace / "answer.txt").read_text(encoding="utf-8") == "42"
    trace = (result.run_dir / "trace.jsonl").read_text(encoding="utf-8")
    assert '"event": "tool_result"' in trace
    report = json.loads((result.run_dir / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "succeeded"
    assert report["steps_completed"] == 2


def test_resume_continues_from_saved_step(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    first = runtime(
        workspace,
        [Action.call("write_file", {"path": "a.txt", "content": "a"})],
        max_steps=1,
    ).start(task="Create files.", runs_root=tmp_path / "runs")
    assert first.status == "failed"
    state = RunStore(first.run_dir).load()
    state.status = "running"
    RunStore(first.run_dir).save(state)

    resumed = runtime(
        workspace,
        [
            Action.call("write_file", {"path": "ignored.txt", "content": "ignored"}),
            Action.call("write_file", {"path": "b.txt", "content": "b"}),
            Action.finish("Recovered."),
        ],
    ).resume(first.run_dir)
    assert resumed.status == "succeeded"
    assert not (workspace / "ignored.txt").exists()
    assert (workspace / "b.txt").read_text(encoding="utf-8") == "b"


def test_workspace_policy_blocks_path_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tools = WorkspaceTools(ToolPolicy(workspace))
    try:
        tools.write_file("../outside.txt", "no")
    except Exception as error:
        assert "escapes workspace" in str(error)
    else:
        raise AssertionError("Expected path escape to be rejected.")
