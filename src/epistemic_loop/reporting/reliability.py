from __future__ import annotations

from dataclasses import dataclass

from epistemic_loop.domain.enums import TerminalStatus
from epistemic_loop.domain.models import ExperimentResult


@dataclass(frozen=True)
class ReliabilitySummary:
    experiment_completion_rate: float
    invalid_artifact_rate: float
    resource_failure_rate: float
    oof_artifact_generation_rate: float
    reproduction_success_rate: float

    @property
    def meets_initial_targets(self) -> bool:
        return (
            self.experiment_completion_rate >= 0.90
            and self.invalid_artifact_rate <= 0.05
            and self.resource_failure_rate <= 0.05
            and self.oof_artifact_generation_rate >= 0.90
            and self.reproduction_success_rate >= 0.90
        )


def summarize_reliability(
    results: list[ExperimentResult],
    *,
    candidate_experiment_ids: set[str] | None = None,
) -> ReliabilitySummary:
    if not results:
        raise ValueError("reliability summary requires terminal results")
    if any(item.terminal_status is None for item in results):
        raise ValueError("reliability summary accepts terminal results only")
    count = len(results)
    completed = [item for item in results if item.terminal_status == TerminalStatus.COMPLETED]
    candidate_trials = (
        [item for item in results if item.experiment_id in candidate_experiment_ids]
        if candidate_experiment_ids is not None
        else [item for item in results if any("candidate.yaml" in ref for ref in item.artifact_refs)]
    )
    candidates_with_oof = [
        item for item in candidate_trials if any("oof_predictions" in ref for ref in item.artifact_refs)
    ]
    reproduced = [item for item in completed if item.metrics.get("reproduction_passed", 0.0) >= 1.0]
    reproduction_trials = [item for item in results if "reproduction_passed" in item.metrics]
    return ReliabilitySummary(
        experiment_completion_rate=len(completed) / count,
        invalid_artifact_rate=(
            sum(item.terminal_status == TerminalStatus.INVALID_ARTIFACT for item in results) / count
        ),
        resource_failure_rate=(sum(item.terminal_status == TerminalStatus.FAILED_RESOURCE for item in results) / count),
        oof_artifact_generation_rate=(len(candidates_with_oof) / len(candidate_trials) if candidate_trials else 0.0),
        reproduction_success_rate=(len(reproduced) / len(reproduction_trials) if reproduction_trials else 0.0),
    )
