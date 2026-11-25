# Agent Systems Lab

`agent-systems-lab` is a small, reproducible runtime for tool-using agents. It is designed to make agent work inspectable: every decision, tool call, verifier result, checkpoint, and recovery is recorded locally.

The first milestone targets terminal-based software-engineering tasks. It intentionally separates:

```text
model policy → agent runtime → tool policy → sandbox/workspace → verifier → traces + reports
```

This is not a benchmark score claim. The included Terminal-Bench integration is an adapter and environment check; published benchmark runs must pin the benchmark release, model, prompt, budget, container image, and result artifacts.

## What v0.1 includes

- JSONL traces for model decisions, tool calls, errors, and verifier outcomes
- Durable checkpoints and `resume` support
- Workspace-bounded shell and file tools
- Explicit command allowlist and timeout policy
- Deterministic scripted-model mode for tests and local demos
- Terminal-Bench command builder and environment validator
- Docker image, example task, and regression tests

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"

asl run --workspace examples/hello_workspace \
  --task "Create greeting.txt containing hello from the agent." \
  --plan examples/hello_plan.json
```

Inspect an interrupted or completed run:

```bash
asl status --run-dir .asl-runs/<run-id>
asl resume --run-dir .asl-runs/<run-id>
```

The example uses a deterministic plan instead of a hosted model, so it runs without credentials. Production model adapters belong behind the `AgentModel` protocol in `src/agent_systems_lab/model.py`; model credentials must not be stored in traces or committed to this repository.

## Run model

Each run writes:

```text
.asl-runs/<run-id>/
├── state.json          # durable run state
├── trace.jsonl         # append-only decision and tool trace
└── report.json         # final outcome summary
```

The runtime checkpoints after every completed step. `resume` replays no successful action: it loads the previous state and continues with remaining steps.

## Tool policy

Tools are intentionally narrow:

- file writes must stay under `--workspace`;
- shell commands must be in the configured executable allowlist;
- shell calls have an explicit timeout;
- dangerous shell syntax (`;`, `&&`, `|`, redirects, command substitution) is rejected in v0.1.

This is a baseline policy, not a complete sandbox. Benchmark runs should execute inside a disposable container or benchmark-provided sandbox.

## Terminal-Bench

Install [Harbor](https://github.com/harbor-framework/terminal-bench) separately, then check the adapter:

```bash
asl terminal-bench check
asl terminal-bench command --agent <your-harbor-agent> --model <model-id>
```

The command prints a pinned-command template. Before publishing a result, run the benchmark oracle repeatedly in your target environment and retain the exact dataset tag, Harbor version, image digest, model configuration, and generated traces.

## Development

```bash
pytest
python -m compileall src
```

## Roadmap

1. **v0.1** — deterministic runtime, policy, checkpoints, traces, and Terminal-Bench adapter
2. **v0.2** — OpenAI-compatible model adapter, tool-result compaction, structured failure taxonomy
3. **v0.3** — Harbor agent package, reproducible Terminal-Bench report, and SWE-bench adapter

## Safety and disclosure

Do not run this runtime against production repositories, credentials, or untrusted instructions. Use throwaway workspaces and containers. Benchmark traces may contain source code or task contents; review artifacts before publishing.
