from __future__ import annotations

from collections.abc import Mapping, Sequence

from epistemic_loop.controller.mode_policy import capabilities
from epistemic_loop.domain.enums import RunMode
from epistemic_loop.domain.models import ValidationWorld
from epistemic_loop.validation.worlds import posterior_entropy

BUCKETS = ("exploit", "qd_explore", "epistemic")


def adaptive_allocation(
    base: Mapping[str, float],
    *,
    mode: RunMode,
    validation_worlds: Sequence[ValidationWorld] = (),
    qd_occupancy: int = 0,
    preferred_state_gap: float | None = None,
) -> dict[str, float]:
    """Adapt phase defaults to uncertainty while preserving system-arm boundaries."""

    if set(base) != set(BUCKETS) or any(value < 0 for value in base.values()):
        raise ValueError(f"allocation must define non-negative fractions for {BUCKETS}")
    policy = capabilities(mode)
    if not policy.solution_qd:
        return {"exploit": 1.0, "qd_explore": 0.0, "epistemic": 0.0}
    values = dict(base)
    if not policy.information_value:
        values["qd_explore"] += values["epistemic"]
        values["epistemic"] = 0.0
        return _normalize(values)

    entropy = posterior_entropy(validation_worlds, normalized=True) if validation_worlds else 1.0
    gap = 1.0 if preferred_state_gap is None else min(1.0, max(0.0, preferred_state_gap))
    epistemic_boost = min(values["exploit"], 0.15 * entropy * (0.5 + 0.5 * gap))
    values["exploit"] -= epistemic_boost
    values["epistemic"] += epistemic_boost
    if qd_occupancy == 0:
        qd_boost = min(values["exploit"], 0.05)
        values["exploit"] -= qd_boost
        values["qd_explore"] += qd_boost
    return _normalize(values)


def _normalize(values: Mapping[str, float]) -> dict[str, float]:
    total = sum(values.values())
    if total <= 0:
        raise ValueError("allocation must contain positive mass")
    return {name: values[name] / total for name in BUCKETS}
