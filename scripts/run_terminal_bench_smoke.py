"""Run a pinned Terminal-Bench smoke and package reproducibility artifacts.

Examples:

  # Oracle connectivity check (no model key)
  python scripts/run_terminal_bench_smoke.py --mode oracle --tasks openssl-selfsigned-cert

  # Agent smoke (requires ASL_OPENAI_API_KEY)
  python scripts/run_terminal_bench_smoke.py --mode agent --model <model-id> \\
    --tasks openssl-selfsigned-cert regex-log
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from agent_systems_lab.terminal_bench import DEFAULT_DATASET, build_command

ROOT = Path(__file__).resolve().parents[1]
AGENT = "agent_systems_lab.integrations.harbor_agent:AgentSystemsLabHarborAgent"
DEFAULT_TASKS = ("openssl-selfsigned-cert", "regex-log")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _docker_ok() -> bool:
    docker = shutil.which("docker")
    if not docker:
        return False
    try:
        subprocess.check_call(
            [docker, "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _write_report(path: Path, *, mode: str, model: str, tasks: list[str], jobs_dir: Path, command: str) -> None:
    path.write_text(
        "\n".join(
            [
                f"# Terminal-Bench 2.0 smoke report ({mode})",
                "",
                "## Claim boundary",
                "",
                "This report packages a smoke/reproducibility run. Fill remaining fields before treating the numbers as a public score.",
                "",
                "## Identity",
                "",
                f"- Recorded at: `{datetime.now(UTC).isoformat()}`",
                f"- Mode: `{mode}`",
                f"- Agent: `{AGENT if mode == 'agent' else 'oracle'}`",
                f"- Dataset: `{DEFAULT_DATASET}`",
                f"- Model: `{model or 'n/a'}`",
                f"- Tasks: `{', '.join(tasks)}`",
                f"- Jobs dir: `{jobs_dir}`",
                "",
                "## Resolved command",
                "",
                "```bash",
                command,
                "```",
                "",
                "## Results",
                "",
                "| Metric | Value |",
                "|---|---|",
                "| Solved / total | |",
                "| Success rate | |",
                "| Notes | Inspect Harbor job outputs under the jobs dir |",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("oracle", "agent"), default="agent")
    parser.add_argument("--model", default="")
    parser.add_argument("--tasks", nargs="+", default=list(DEFAULT_TASKS))
    parser.add_argument("--output-dir", type=Path, default=ROOT / "evals" / "artifacts")
    parser.add_argument("--jobs-dir", type=Path, default=ROOT / "evals" / "artifacts" / "jobs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _require(shutil.which("harbor") is not None, "Harbor is not on PATH. Install with: pip install -e '.[terminal-bench]'")
    _require(_docker_ok(), "Docker is unavailable or the daemon is not running.")

    if args.mode == "agent":
        _require(bool(os.environ.get("ASL_OPENAI_API_KEY")), "Set ASL_OPENAI_API_KEY before agent smoke runs.")
        _require(bool(args.model), "--model is required for agent mode.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.jobs_dir.mkdir(parents=True, exist_ok=True)

    command = build_command(
        agent=AGENT if args.mode == "agent" else "oracle",
        model=args.model or "oracle",
        dataset=DEFAULT_DATASET,
        tasks=args.tasks,
        jobs_dir=str(args.jobs_dir),
        include_model=args.mode == "agent",
    )
    (args.output_dir / "resolved_command.txt").write_text(command + "\n", encoding="utf-8")
    subprocess.check_call(
        [
            sys.executable,
            str(ROOT / "scripts" / "record_eval_environment.py"),
            "--output",
            str(args.output_dir / "environment_versions.json"),
            "--dataset",
            DEFAULT_DATASET,
            "--model",
            args.model or "oracle",
        ]
    )
    _write_report(
        args.output_dir / "report.md",
        mode=args.mode,
        model=args.model,
        tasks=args.tasks,
        jobs_dir=args.jobs_dir,
        command=command,
    )

    print(command)
    if args.dry_run:
        print("dry-run: skipped harbor execution")
        return 0

    cmd = ["harbor", "run", "--dataset", DEFAULT_DATASET, "--n-concurrent", "1", "--jobs-dir", str(args.jobs_dir)]
    if args.mode == "agent":
        cmd.extend(["--agent", AGENT, "--model", args.model])
        cmd.extend(["--agent-env", f"ASL_OPENAI_API_KEY={os.environ['ASL_OPENAI_API_KEY']}"])
        base_url = os.environ.get("ASL_OPENAI_BASE_URL")
        if base_url:
            cmd.extend(["--agent-env", f"ASL_OPENAI_BASE_URL={base_url}"])
    else:
        cmd.extend(["--agent", "oracle"])
    for task in args.tasks:
        cmd.extend(["--include-task-name", task])

    print("running:", command)
    completed = subprocess.run(cmd, check=False)
    summary = {
        "mode": args.mode,
        "model": args.model or "oracle",
        "tasks": args.tasks,
        "exit_code": completed.returncode,
        "jobs_dir": str(args.jobs_dir),
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    (args.output_dir / "smoke_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
