"""Prepare the reproducible command and environment metadata for a smoke run."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from agent_systems_lab.terminal_bench import DEFAULT_DATASET, build_command

AGENT = "agent_systems_lab.integrations.harbor_agent:AgentSystemsLabHarborAgent"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    command = build_command(agent=AGENT, model=args.model, dataset=args.dataset)
    command_path = args.output_dir / "resolved_command.txt"
    command_path.write_text(command + "\n", encoding="utf-8")

    env_path = args.output_dir / "environment_versions.json"
    subprocess.check_call(
        [
            sys.executable,
            str(Path(__file__).with_name("record_eval_environment.py")),
            "--output",
            str(env_path),
            "--dataset",
            args.dataset,
            "--model",
            args.model,
        ]
    )
    print(command)
    print(f"wrote {command_path}")
    print(f"wrote {env_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
