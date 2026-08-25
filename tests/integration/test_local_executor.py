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


def test_a_failure_carries_its_own_explanation_back(tmp_path: Path) -> None:
    """A failure class says a design did not run. It does not say what to change.

    The eighth unattended run proposed `--baseline-split kfold`, which the runner rejects because it
    accepts `random_kfold`. The next round saw only `failure_class: model` and had no way to learn
    that, so the loop can repeat an invalid argument indefinitely. The sentence the runner printed is
    the evidence, and it has to reach the proposer.
    """
    executor = LocalExecutor(tmp_path, tmp_path / "results")
    script = tmp_path / "fail.py"
    script.write_text("import sys; sys.stderr.write('ValueError: unknown split strategy: kfold\\n'); sys.exit(1)")

    request = ExperimentRequest(
        request_id="req-3",
        experiment_id="exp-3",
        run_id="run-3",
        idempotency_key="run-3:exp-3:attempt-1",
        base_commit_sha="abc123",
        implementation_mode="existing",
        objective="a split the runner does not accept",
        command=f"python3 {script}",
        container_image="local",
        dataset_mounts=[DatasetMount(name="fixture")],
        resources=ResourceRequest(timeout_seconds=10),
        seeds=[11],
        required_outputs=["metrics.json"],
    )
    result = executor.submit(request)

    assert result.status == "failed"
    assert result.failure_excerpt is not None
    assert "unknown split strategy: kfold" in result.failure_excerpt

    state_view = {"failure_excerpt": result.failure_excerpt}
    assert state_view["failure_excerpt"], "the excerpt is what run_state.failed_experiments() forwards"
