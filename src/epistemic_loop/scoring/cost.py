from __future__ import annotations

from epistemic_loop.domain.models import CostEstimate


def normalized_cost(
    estimate: CostEstimate,
    *,
    cpu_scale: float = 10.0,
    gpu_scale: float = 5.0,
    wall_scale: float = 10.0,
    token_scale: float = 100_000.0,
    monetary_scale: float = 25.0,
) -> float:
    resource = (
        estimate.cpu_hours / cpu_scale
        + estimate.gpu_hours / gpu_scale
        + estimate.wall_hours / wall_scale
        + estimate.llm_tokens / token_scale
        + estimate.monetary_cost / monetary_scale
    ) / 5.0
    return min(1.0, max(0.0, resource + 0.25 * estimate.failure_probability))
