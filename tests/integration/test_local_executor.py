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
