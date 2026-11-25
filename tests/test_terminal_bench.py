from pathlib import Path

from agent_systems_lab.integrations.harbor_agent import AgentSystemsLabHarborAgent, build_write_command
from agent_systems_lab.terminal_bench import DEFAULT_DATASET, build_command


def test_terminal_bench_command_defaults_to_v2() -> None:
    command = build_command(
        agent="agent_systems_lab.integrations.harbor_agent:AgentSystemsLabHarborAgent",
        model="example/model",
        tasks=["openssl-selfsigned-cert"],
        jobs_dir="evals/artifacts/jobs",
    )
    assert f"--dataset {DEFAULT_DATASET}" in command
    assert "--n-concurrent 1" in command
    assert "AgentSystemsLabHarborAgent" in command
    assert "--include-task-name openssl-selfsigned-cert" in command
    assert "--jobs-dir evals/artifacts/jobs" in command


def test_oracle_command_omits_model() -> None:
    command = build_command(agent="oracle", model="", include_model=False, tasks=["regex-log"])
    assert "--agent oracle" in command
    assert "--model" not in command
    assert "--include-task-name regex-log" in command


def test_harbor_write_command_base64_encodes_content() -> None:
    command = build_write_command("nested/result.txt", "hello 'agent'")
    assert "mkdir -p nested" in command
    assert "base64 -d > nested/result.txt" in command
    assert "hello 'agent'" not in command


def test_harbor_agent_exposes_required_methods() -> None:
    required = {"name", "version", "setup", "run"}
    for method_name in required:
        assert hasattr(AgentSystemsLabHarborAgent, method_name)
    assert AgentSystemsLabHarborAgent.name() == "agent-systems-lab"
    assert not getattr(AgentSystemsLabHarborAgent, "__abstractmethods__", set())


def test_prepare_smoke_script_writes_artifacts(tmp_path: Path) -> None:
    import subprocess
    import sys

    script = Path("scripts/prepare_terminal_bench_smoke.py")
    output_dir = tmp_path / "artifacts"
    completed = subprocess.run(
        [sys.executable, str(script), "--model", "example/model", "--output-dir", str(output_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "harbor run --dataset terminal-bench@2.0" in completed.stdout
    assert (output_dir / "resolved_command.txt").exists()
    assert (output_dir / "environment_versions.json").exists()
