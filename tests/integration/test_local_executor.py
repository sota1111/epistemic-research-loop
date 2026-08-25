from pathlib import Path

from epistemic_loop.adapters.executor.local import LocalExecutor
from epistemic_loop.domain.models import DatasetMount, ExperimentRequest, ResourceRequest


def test_local_executor_collects_required_outputs(tmp_path) -> None:
    fixture = Path(__file__).resolve().parents[2] / "examples" / "local_mock" / "run_experiment.py"
    request = ExperimentRequest(
        request_id="req-1",
        experiment_id="exp-1",
        run_id="run-1",
        idempotency_key="run-1:exp-1:attempt-1",
        base_commit_sha="abc123",
        implementation_mode="existing",
        objective="smoke test",
        command=f"python3 {fixture}",
        container_image="local",
        dataset_mounts=[DatasetMount(name="fixture")],
        resources=ResourceRequest(timeout_seconds=10),
        seeds=[11],
        required_outputs=["metrics.json", "fold_metrics.json", "predictions.parquet", "run_manifest.json"],
    )
    result = LocalExecutor(tmp_path, tmp_path / "results").submit(request)
    assert result.status == "completed"
    assert result.metrics == {"score": 0.75}
    assert len(result.artifact_refs) == 4


def test_the_command_can_name_the_output_directory_symbolically(tmp_path) -> None:
    """A proposal is written before its output directory exists, so it must be able to refer to it.

    Without a substitution the only way to pass `--output` is to guess a path, and an experiment
    that runs correctly but writes somewhere else is recorded as a failure -- which is exactly what
    happened on the seventh unattended run: the metrics were computed, and scored as missing.
    """
    from epistemic_loop.adapters.executor.local import LocalExecutor
    from epistemic_loop.domain.models import DatasetMount, ExperimentRequest, ResourceRequest

    script = tmp_path / "writer.py"
    script.write_text(
        "import json, os, sys, pathlib\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'metrics.json').write_text(json.dumps({'roc_auc': 0.9}))\n",
        encoding="utf-8",
    )
    request = ExperimentRequest(
        request_id="req-1",
        experiment_id="EXP-001",
        run_id="run-1",
        idempotency_key="run-1:EXP-001:attempt-1",
        base_commit_sha="abc123",
        implementation_mode="preregistered_experiment",
        objective="write metrics where the loop will look",
        command=f"python3 {script} --output $ERL_OUTPUT_DIR",
        container_image="python:3.11-slim",
        dataset_mounts=[DatasetMount(name="d")],
        resources=ResourceRequest(),
        seeds=[11],
        required_outputs=["metrics.json"],
    )

    result = LocalExecutor(tmp_path, tmp_path / "results").submit(request)

    assert result.status == "completed", result.failure_class
    assert result.metrics == {"roc_auc": 0.9}
    assert any(item.endswith("metrics.json") for item in result.artifact_refs)
