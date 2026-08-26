from epistemic_loop.domain.enums import TerminalStatus
from epistemic_loop.domain.models import ExperimentResult
from epistemic_loop.reporting.reliability import summarize_reliability


def result(identifier: str, status: TerminalStatus, artifacts: list[str] | None = None) -> ExperimentResult:
    return ExperimentResult(
        experiment_id=identifier,
        run_id="run",
        attempt=1,
        status="completed" if status == TerminalStatus.COMPLETED else "failed",
        terminal_status=status,
        commit_sha="abc",
        environment_hash="env",
        dataset_fingerprint="data",
        artifact_refs=artifacts or [],
    )


def test_reliability_rates_use_candidate_trials_for_oof_rate() -> None:
    results = [
        result("diagnostic", TerminalStatus.COMPLETED),
        result("candidate", TerminalStatus.COMPLETED, ["candidate.yaml", "oof_predictions.parquet"]),
    ]
    summary = summarize_reliability(results, candidate_experiment_ids={"candidate"})
    assert summary.experiment_completion_rate == 1
    assert summary.oof_artifact_generation_rate == 1
