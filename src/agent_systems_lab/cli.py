"""Command-line entry point for Agent Systems Lab."""

from __future__ import annotations

import argparse
from pathlib import Path

from .model import ScriptedModel
from .runtime import AgentRuntime
from .terminal_bench import build_command, check_environment
from .tools import ToolPolicy, WorkspaceTools


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asl", description="Reproducible tool-using agent runtime.")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="Run a deterministic plan in a bounded workspace.")
    run.add_argument("--workspace", required=True, type=Path)
    run.add_argument("--task", required=True)
    run.add_argument("--plan", required=True, type=Path)
    run.add_argument("--runs-root", type=Path, default=Path(".asl-runs"))
    run.add_argument("--max-steps", type=int, default=20)

    resume = commands.add_parser("resume", help="Resume a previously interrupted run.")
    resume.add_argument("--run-dir", required=True, type=Path)
    resume.add_argument("--plan", required=True, type=Path, help="The deterministic plan used for the run.")
    resume.add_argument("--max-steps", type=int, default=20)

    status = commands.add_parser("status", help="Display durable run state.")
    status.add_argument("--run-dir", required=True, type=Path)

    terminal = commands.add_parser("terminal-bench", help="Terminal-Bench integration helpers.")
    terminal_subcommands = terminal.add_subparsers(dest="terminal_command", required=True)
    terminal_subcommands.add_parser("check", help="Check whether Harbor is installed.")
    command = terminal_subcommands.add_parser("command", help="Print a reproducible Harbor command template.")
    command.add_argument("--agent", required=True)
    command.add_argument("--model", required=True)
    command.add_argument("--dataset", default="terminal-bench/terminal-bench@latest")
    return parser


def _runtime_for_plan(workspace: Path, plan: Path, max_steps: int) -> AgentRuntime:
    policy = ToolPolicy(workspace)
    return AgentRuntime(ScriptedModel.from_json_file(plan), WorkspaceTools(policy), max_steps=max_steps)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        runtime = _runtime_for_plan(args.workspace, args.plan, args.max_steps)
        result = runtime.start(task=args.task, runs_root=args.runs_root)
        print(f"{result.status}: {result.summary}\nrun_dir={result.run_dir}")
        return 0 if result.status == "succeeded" else 1
    if args.command == "resume":
        from .state import RunStore

        state = RunStore(args.run_dir).load()
        runtime = _runtime_for_plan(Path(state.workspace), args.plan, args.max_steps)
        result = runtime.resume(args.run_dir)
        print(f"{result.status}: {result.summary}\nrun_dir={result.run_dir}")
        return 0 if result.status == "succeeded" else 1
    if args.command == "status":
        from .state import RunStore

        state = RunStore(args.run_dir).load()
        print(f"{state.status}: step={state.next_step} task={state.task}\nsummary={state.final_summary}")
        return 0
    if args.terminal_command == "check":
        result = check_environment()
        print(result.message)
        return 0 if result.harbor_available else 1
    if args.terminal_command == "command":
        print(build_command(agent=args.agent, model=args.model, dataset=args.dataset))
        return 0
    raise AssertionError("Unreachable parser branch.")
