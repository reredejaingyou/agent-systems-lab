"""Command-line entry point for Agent Systems Lab."""

from __future__ import annotations

import argparse
from pathlib import Path

from .model import ScriptedModel
from .openai_compat import ModelProviderError, OpenAICompatibleModel
from .runtime import AgentRuntime
from .terminal_bench import build_command, check_environment
from .tools import ToolPolicy, WorkspaceTools


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asl", description="Reproducible tool-using agent runtime.")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="Run a deterministic plan in a bounded workspace.")
    run.add_argument("--workspace", required=True, type=Path)
    run.add_argument("--task", required=True)
    run.add_argument("--plan", type=Path, help="Deterministic local action plan for tests and demos.")
    run.add_argument("--provider", choices=("scripted", "openai-compatible"), default="scripted")
    run.add_argument("--model", help="Model ID for the OpenAI-compatible provider.")
    run.add_argument("--base-url", help="OpenAI-compatible API base URL. Defaults to ASL_OPENAI_BASE_URL.")
    run.add_argument("--runs-root", type=Path, default=Path(".asl-runs"))
    run.add_argument("--max-steps", type=int, default=20)

    resume = commands.add_parser("resume", help="Resume a previously interrupted run.")
    resume.add_argument("--run-dir", required=True, type=Path)
    resume.add_argument("--plan", type=Path, help="The deterministic plan used for the run.")
    resume.add_argument("--provider", choices=("scripted", "openai-compatible"), default="scripted")
    resume.add_argument("--model", help="Model ID for the OpenAI-compatible provider.")
    resume.add_argument("--base-url", help="OpenAI-compatible API base URL. Defaults to ASL_OPENAI_BASE_URL.")
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


def _runtime_for_args(args: argparse.Namespace, workspace: Path) -> AgentRuntime:
    policy = ToolPolicy(workspace)
    if args.provider == "scripted":
        if not args.plan:
            raise ModelProviderError("--plan is required when --provider scripted.")
        model = ScriptedModel.from_json_file(args.plan)
    else:
        model = OpenAICompatibleModel.from_environment(model=args.model, base_url=args.base_url)
    return AgentRuntime(model, WorkspaceTools(policy), max_steps=args.max_steps)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            runtime = _runtime_for_args(args, args.workspace)
            result = runtime.start(task=args.task, runs_root=args.runs_root)
            print(f"{result.status}: {result.summary}\nrun_dir={result.run_dir}")
            return 0 if result.status == "succeeded" else 1
        if args.command == "resume":
            from .state import RunStore

            state = RunStore(args.run_dir).load()
            runtime = _runtime_for_args(args, Path(state.workspace))
            result = runtime.resume(args.run_dir)
            print(f"{result.status}: {result.summary}\nrun_dir={result.run_dir}")
            return 0 if result.status == "succeeded" else 1
    except ModelProviderError as error:
        print(f"configuration error: {error}")
        return 2
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
