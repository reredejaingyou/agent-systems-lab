"""Terminal-Bench integration helpers.

The benchmark itself is installed and versioned independently through Harbor.
This module deliberately prints commands instead of silently downloading or
running a benchmark with an unpinned version.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class TerminalBenchEnvironment:
    harbor_available: bool
    message: str


def check_environment() -> TerminalBenchEnvironment:
    harbor = shutil.which("harbor")
    if harbor:
        return TerminalBenchEnvironment(True, f"Harbor found at {harbor}")
    return TerminalBenchEnvironment(
        False,
        "Harbor is not installed. Install a pinned Harbor release before running Terminal-Bench.",
    )


DEFAULT_DATASET = "terminal-bench@2.0"
DEFAULT_SMOKE_TASKS = ("openssl-selfsigned-cert", "regex-log")


def build_command(
    *,
    agent: str,
    model: str,
    dataset: str = DEFAULT_DATASET,
    tasks: list[str] | tuple[str, ...] | None = None,
    jobs_dir: str | None = None,
    include_model: bool = True,
) -> str:
    if not agent:
        raise ValueError("--agent is required.")
    if include_model and not model:
        raise ValueError("--model is required.")
    parts = [f"harbor run --dataset {dataset}", f"--agent {agent}"]
    if include_model:
        parts.append(f"--model {model}")
    parts.append("--n-concurrent 1")
    if jobs_dir:
        parts.append(f"--jobs-dir {jobs_dir}")
    for task in tasks or ():
        parts.append(f"--include-task-name {task}")
    return " ".join(parts)
