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
- OpenAI-compatible model adapter with strict JSON action parsing
- Common API-key redaction before observations, traces, state, and reports are persisted
- Structured failure categories (`model_error`, `invalid_action`, `tool_policy`, `tool_execution`, `step_budget`)
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

The example uses a deterministic plan instead of a hosted model, so it runs without credentials.

### Run with an OpenAI-compatible endpoint

```bash
# PowerShell
$env:ASL_OPENAI_API_KEY = "<key>"
$env:ASL_OPENAI_BASE_URL = "https://api.openai.com/v1"

asl run --provider openai-compatible --model <model-id> \
  --workspace examples/hello_workspace \
  --task "Create greeting.txt containing hello from the agent."
```

The provider must implement the `/chat/completions` request shape. The runtime requests one strict JSON action at a time. API keys are read only from environment variables and are redacted from persisted run artifacts; do not place secrets in task instructions or workspace files.

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

Install the pinned Harbor extra, then check the adapter:

```bash
pip install -e ".[terminal-bench]"
asl terminal-bench check
asl terminal-bench command --agent <your-harbor-agent> --model <model-id>
```

The command prints a pinned-command template for Terminal-Bench 2.0. Before publishing a result, run the benchmark oracle repeatedly in your target environment and retain the exact dataset tag, Harbor version, image digest, model configuration, and generated traces.

### Run this runtime as a Harbor custom agent

`agent_systems_lab.integrations.harbor_agent:AgentSystemsLabHarborAgent` implements Harbor's external `BaseAgent` interface. Its loop runs on the Harbor host; commands are executed exclusively through Harbor's task environment.

```bash
export ASL_OPENAI_API_KEY="<key>"
export ASL_OPENAI_BASE_URL="https://api.openai.com/v1"

harbor run --dataset terminal-bench@2.0 \
  --agent agent_systems_lab.integrations.harbor_agent:AgentSystemsLabHarborAgent \
  --model <model-id> \
  --n-concurrent 1
```

Start with the reproducibility manifest at `evals/terminal_bench_2_small.yaml`. Do not publish a score until the same pinned dataset, Harbor version, model settings, and artifact bundle can be rerun.

## Development

```bash
pytest
python -m compileall src
```

## Roadmap

1. **v0.1** — deterministic runtime, policy, checkpoints, traces, and Terminal-Bench adapter
2. **v0.2** — OpenAI-compatible model adapter, secret redaction, and structured failure taxonomy
3. **v0.3** — Harbor external-agent entrypoint, Terminal-Bench 2.0 reproducibility manifest, and artifact contract
4. **v0.4** — Verified Terminal-Bench smoke report and SWE-bench adapter

## Safety and disclosure

Do not run this runtime against production repositories, credentials, or untrusted instructions. Use throwaway workspaces and containers. Benchmark traces may contain source code or task contents; review artifacts before publishing.
