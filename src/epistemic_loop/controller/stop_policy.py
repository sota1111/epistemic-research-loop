from __future__ import annotations

from dataclasses import dataclass

from epistemic_loop.domain.models import Budget, BudgetUsage


@dataclass(frozen=True)
class StopDecision:
    stop: bool
    reasons: tuple[str, ...]
    blocked: bool = False


def should_stop(
    budget: Budget,
    usage: BudgetUsage,
    *,
    maximum_candidate_utility: float | None,
    minimum_utility: float,
    rounds_without_information: int = 0,
    max_rounds_without_information: int = 3,
    validation_stable: bool = True,
    holdout_violation: bool = False,
    rule_violation: bool = False,
    human_stop: bool = False,
) -> StopDecision:
    reasons: list[str] = []
    blocked = False
    if usage.experiments >= budget.max_experiments:
        reasons.append("experiment budget exhausted")
    # A budget of zero means the run does not use that resource. Reading it as "exhausted" stops
    # every CPU-only run on its first round for having consumed no GPU at all.
    if budget.max_cpu_hours and usage.cpu_hours >= budget.max_cpu_hours:
        reasons.append("CPU budget exhausted")
    if budget.max_gpu_hours and usage.gpu_hours >= budget.max_gpu_hours:
        reasons.append("GPU budget exhausted")
    if maximum_candidate_utility is not None and maximum_candidate_utility < minimum_utility:
        reasons.append("maximum candidate utility is below threshold")
    if rounds_without_information >= max_rounds_without_information:
        reasons.append(f"{rounds_without_information} rounds produced no new information")
    if not validation_stable:
        reasons.append("validation scheme is unstable")
        blocked = True
    if holdout_violation:
        reasons.append("holdout violation")
        blocked = True
    if rule_violation:
        reasons.append("competition rule violation")
        blocked = True
    if human_stop:
        reasons.append("human stop")
    return StopDecision(bool(reasons), tuple(reasons), blocked)
