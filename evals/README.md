# Evaluation manifests

These files define how a public Agent Systems Lab result should be produced and packaged. They are reproducibility contracts, not score claims.

## Terminal-Bench 2.0 smoke (`terminal_bench_2_small.yaml`)

Goal: run a small, pinned Terminal-Bench sample with the Harbor external agent and retain every artifact needed for someone else to rerun the same experiment.

### 1. Record the environment

```bash
pip install -e ".[dev,terminal-bench]"
python scripts/record_eval_environment.py \
  --output evals/artifacts/environment_versions.json \
  --model <model-id>
```

### 2. Write the resolved command

```bash
python scripts/prepare_terminal_bench_smoke.py \
  --model <model-id> \
  --output-dir evals/artifacts
```

### 3. Run Harbor

First validate the harness with the oracle agent (no model key):

```bash
python scripts/run_terminal_bench_smoke.py --mode oracle --tasks openssl-selfsigned-cert
```

Then run the Agent Systems Lab smoke (requires `ASL_OPENAI_API_KEY`):

```bash
python scripts/run_terminal_bench_smoke.py --mode agent --model <model-id> \
  --tasks openssl-selfsigned-cert regex-log
```

Keep concurrency at `1` for the first smoke run. Pass credentials with Harbor `--agent-env` / `--ae` or via the smoke script environment.

### 4. Package artifacts

Before publishing any number, retain:

- `resolved_command.txt`
- `environment_versions.json`
- Harbor result JSON
- `agent-systems-lab.trace.jsonl`
- `report.md` filled from `report.template.md`

Do not publish a success rate until the same dataset tag, Harbor version, model settings, and container/image digest can be rerun.
