"""Record the minimum metadata needed to reproduce a benchmark run."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def git_revision() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", default="terminal-bench@2.0")
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    payload = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "dataset": args.dataset,
        "model": args.model,
        "git_revision": git_revision(),
        "python": sys.version,
        "platform": platform.platform(),
        "packages": {
            "agent-systems-lab": package_version("agent-systems-lab"),
            "harbor": package_version("harbor"),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
