"""Narrow, workspace-bounded tools for the v0.1 runtime."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class ToolPolicyError(RuntimeError):
    """Raised when an action violates the runtime's explicit policy."""


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: str


class ToolPolicy:
    """Validates paths and shell calls before execution."""

    def __init__(
        self,
        workspace: Path,
        *,
        allowed_executables: set[str] | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.workspace = workspace.resolve()
        self.allowed_executables = allowed_executables or {"python", "python3", "pytest", "git", "type", "cat"}
        self.timeout_seconds = timeout_seconds

    def resolve_workspace_path(self, raw_path: str) -> Path:
        candidate = (self.workspace / raw_path).resolve()
        if candidate != self.workspace and self.workspace not in candidate.parents:
            raise ToolPolicyError(f"Path escapes workspace: {raw_path}")
        return candidate

    def validate_command(self, command: str) -> list[str]:
        if not command.strip():
            raise ToolPolicyError("Command must not be empty.")
        forbidden = (";", "&&", "||", "|", ">", "<", "`", "$(", "\n", "\r")
        if any(token in command for token in forbidden):
            raise ToolPolicyError("Shell composition and redirects are disabled by policy.")
        tokens = command.split()
        executable = Path(tokens[0]).name
        if executable not in self.allowed_executables:
            raise ToolPolicyError(f"Executable is not allowed: {executable}")
        return tokens


class WorkspaceTools:
    """File and shell tools that enforce ToolPolicy."""

    def __init__(self, policy: ToolPolicy) -> None:
        self.policy = policy

    def read_file(self, path: str) -> ToolResult:
        target = self.policy.resolve_workspace_path(path)
        return ToolResult(ok=True, output=target.read_text(encoding="utf-8"))

    def write_file(self, path: str, content: str) -> ToolResult:
        target = self.policy.resolve_workspace_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ToolResult(ok=True, output=f"Wrote {target.relative_to(self.policy.workspace)}")

    def run_shell(self, command: str) -> ToolResult:
        tokens = self.policy.validate_command(command)
        completed = subprocess.run(
            tokens,
            cwd=self.policy.workspace,
            text=True,
            capture_output=True,
            timeout=self.policy.timeout_seconds,
            check=False,
        )
        output = (completed.stdout + completed.stderr).strip()
        return ToolResult(ok=completed.returncode == 0, output=output)

    def dispatch(self, tool: str, arguments: dict[str, str]) -> ToolResult:
        if tool == "read_file":
            return self.read_file(arguments["path"])
        if tool == "write_file":
            return self.write_file(arguments["path"], arguments["content"])
        if tool == "run_shell":
            return self.run_shell(arguments["command"])
        raise ToolPolicyError(f"Unknown tool: {tool}")
