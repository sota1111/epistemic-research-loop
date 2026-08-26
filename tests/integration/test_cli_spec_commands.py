from pathlib import Path

from typer.testing import CliRunner

from epistemic_loop.adapters.executor.local import LocalExecutor
from epistemic_loop.cli import app
from epistemic_loop.config import load_config
from epistemic_loop.domain.models import ExperimentRequest, ResourceRequest


def test_ablation_command_writes_a_runnable_component_variant(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    destination = tmp_path / "ablation.yaml"
    result = CliRunner().invoke(
        app,
        [
            "ablation",
            "--config",
            str(root / "configs" / "system_c.yaml"),
            "--remove",
            "eig",
            "--remove",
            "falsifier",
            "--remove",
            "preferred-state",
            "--out",
            str(destination),
        ],
    )

    assert result.exit_code == 0, result.output
    assert load_config(destination).ablation.remove == ["eig", "falsifier", "preferred-state"]


def test_contamination_command_creates_column_neutral_csv(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    destination = tmp_path / "anonymous.csv"
    source.write_text("customer,time,target\na,1,0\n", encoding="utf-8")
    result = CliRunner().invoke(
        app,
        [
            "contamination",
            "anonymize-csv",
            "--from",
            str(source),
            "--out",
            str(destination),
            "--salt",
            "run-1",
        ],
    )

    assert result.exit_code == 0, result.output
    content = destination.read_text(encoding="utf-8")
    assert "customer" not in content
    assert "a,1,0" in content


def test_manifest_rerun_reproduces_metrics_in_a_separate_result_root(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    fixture = root / "examples" / "local_mock" / "run_experiment.py"
    request = ExperimentRequest(
        request_id="req-replay",
        experiment_id="exp-replay",
        run_id="run-replay",
        idempotency_key="run-replay:exp-replay:attempt-1",
        base_commit_sha="abc123",
        implementation_mode="replay-test",
        objective="produce deterministic fixture metrics",
        command=f"python3 {fixture}",
        container_image="local",
        dataset_mounts=[],
        resources=ResourceRequest(timeout_seconds=10),
        seeds=[11],
        required_outputs=["metrics.json", "fold_metrics.json", "predictions.parquet", "run_manifest.json"],
    )
    original = LocalExecutor(tmp_path, tmp_path / "original").submit(request)
    assert original.manifest_ref is not None
    replay_root = tmp_path / "replayed"

    result = CliRunner().invoke(
        app,
        [
            "experiments",
            "rerun-manifest",
            "--manifest",
            original.manifest_ref,
            "--workspace",
            str(tmp_path),
            "--result-root",
            str(replay_root),
        ],
    )

    assert result.exit_code == 0, result.output
    assert '"metric_delta": {' in result.output
    assert '"score": 0.0' in result.output
    assert list(replay_root.rglob("erl_manifest.json"))
