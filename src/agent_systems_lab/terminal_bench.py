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


def build_command(*, agent: str, model: str, dataset: str = "terminal-bench/terminal-bench@latest") -> str:
    if not agent or not model:
        raise ValueError("Both --agent and --model are required.")
    return (
        f"uv run harbor run -d {dataset} "
        f"--agent {agent} --model {model} "
        "--env modal --n-concurrent 1"
    )
