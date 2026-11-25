# Terminal-Bench 2.0 oracle smoke report

## Claim boundary

This is a harness connectivity / reproducibility smoke using Harbor's `oracle` agent. It is **not** an Agent Systems Lab model score.

## Identity

- Recorded at: `2026-11-25T16:38:30+08:00`
- Git revision: see accompanying commit on `main`
- Agent: `oracle`
- Dataset: `terminal-bench@2.0`
- Harbor version: `0.27.0`
- Model: n/a
- Max agent steps: n/a
- Concurrency: `1`
- Task count: `1`
- Tasks: `openssl-selfsigned-cert`

## Results

| Metric | Value |
|---|---|
| Solved / total | 1 / 1 |
| Success rate | 1.000 |
| Exceptions | 0 |
| Mean wall time | ~35s |
| Job id | `2026-11-25__16-37-46` |

## Artifacts retained locally

- `evals/artifacts/resolved_command.txt`
- `evals/artifacts/environment_versions.json`
- `evals/artifacts/jobs/2026-11-25__16-37-46/result.json`
- `evals/artifacts/smoke_summary.json`

## Next gate

Run the Agent Systems Lab Harbor agent on the same pinned tasks after setting:

```powershell
$env:ASL_OPENAI_API_KEY = "<key>"
$env:ASL_OPENAI_BASE_URL = "https://api.openai.com/v1"  # or compatible endpoint
python scripts/run_terminal_bench_smoke.py --mode agent --model <model-id> `
  --tasks openssl-selfsigned-cert regex-log
```
