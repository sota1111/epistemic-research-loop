from __future__ import annotations

from dataclasses import dataclass

from epistemic_loop.domain.models import Budget, BudgetUsage, CostEstimate, ExperimentResult


@dataclass(frozen=True)
class BudgetCheck:
    allowed: bool
    reasons: tuple[str, ...]


class BudgetManager:
    def __init__(self, budget: Budget, usage: BudgetUsage | None = None):
        self.budget = budget
        self.usage = usage or BudgetUsage()

    def check(self, estimate: CostEstimate) -> BudgetCheck:
        reasons = []
        if self.usage.experiments + 1 > self.budget.max_experiments:
            reasons.append("max_experiments")
        if self.usage.cpu_hours + estimate.cpu_hours > self.budget.max_cpu_hours:
            reasons.append("max_cpu_hours")
        if self.usage.gpu_hours + estimate.gpu_hours > self.budget.max_gpu_hours:
            reasons.append("max_gpu_hours")
        if self.usage.wall_hours + estimate.wall_hours > self.budget.max_wall_hours:
            reasons.append("max_wall_hours")
        if self.usage.llm_tokens + estimate.llm_tokens > self.budget.max_llm_tokens:
            reasons.append("max_llm_tokens")
        if self.budget.max_cost and self.usage.cost + estimate.monetary_cost > self.budget.max_cost:
            reasons.append("max_cost")
        return BudgetCheck(not reasons, tuple(reasons))

    def reserve(self, estimate: CostEstimate) -> BudgetUsage:
        check = self.check(estimate)
        if not check.allowed:
            raise ValueError(f"budget exceeded: {', '.join(check.reasons)}")
        self.usage = self.usage.model_copy(
            update={
                "experiments": self.usage.experiments + 1,
                "cpu_hours": self.usage.cpu_hours + estimate.cpu_hours,
                "gpu_hours": self.usage.gpu_hours + estimate.gpu_hours,
                "wall_hours": self.usage.wall_hours + estimate.wall_hours,
                "llm_tokens": self.usage.llm_tokens + estimate.llm_tokens,
                "cost": self.usage.cost + estimate.monetary_cost,
            }
        )
        return self.usage

    def reconcile(self, result: ExperimentResult, *, infrastructure_retry: bool = False) -> BudgetUsage:
        """Replace estimates is future work; retries never increment the research experiment count."""
        if infrastructure_retry:
            return self.usage
        return self.usage

    def remaining(self) -> dict[str, float | int]:
        return {
            "experiments": max(0, self.budget.max_experiments - self.usage.experiments),
            "cpu_hours": max(0.0, self.budget.max_cpu_hours - self.usage.cpu_hours),
            "gpu_hours": max(0.0, self.budget.max_gpu_hours - self.usage.gpu_hours),
            "wall_hours": max(0.0, self.budget.max_wall_hours - self.usage.wall_hours),
            "llm_tokens": max(0, self.budget.max_llm_tokens - self.usage.llm_tokens),
            "cost": max(0.0, self.budget.max_cost - self.usage.cost) if self.budget.max_cost else 0.0,
            "final_submissions": max(0, self.budget.max_final_submissions - self.usage.final_submissions),
        }
