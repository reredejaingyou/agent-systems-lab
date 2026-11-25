"""Durable state and append-only trace storage."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class RunState:
    run_id: str
    task: str
    workspace: str
    status: str = "running"
    next_step: int = 0
    observations: list[dict[str, str]] = field(default_factory=list)
    started_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    final_summary: str = ""

    @classmethod
    def new(cls, task: str, workspace: Path) -> "RunState":
        return cls(run_id=uuid4().hex, task=task, workspace=str(workspace.resolve()))


class RunStore:
    """Persists a state machine without partially-written state files."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.state_path = run_dir / "state.json"
        self.trace_path = run_dir / "trace.jsonl"
        self.report_path = run_dir / "report.json"

    def initialize(self, state: RunState) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.save(state)
        self.trace("run_started", {"task": state.task, "workspace": state.workspace})

    def load(self) -> RunState:
        raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        return RunState(**raw)

    def save(self, state: RunState) -> None:
        state.updated_at = utc_now()
        self._atomic_write(self.state_path, json.dumps(asdict(state), indent=2, sort_keys=True))

    def trace(self, event: str, payload: dict[str, object]) -> None:
        entry = {"at": utc_now(), "event": event, **payload}
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def report(self, state: RunState) -> None:
        payload = {
            "run_id": state.run_id,
            "status": state.status,
            "task": state.task,
            "workspace": state.workspace,
            "steps_completed": state.next_step,
            "final_summary": state.final_summary,
            "started_at": state.started_at,
            "finished_at": utc_now(),
        }
        self._atomic_write(self.report_path, json.dumps(payload, indent=2, sort_keys=True))

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", text=True)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
