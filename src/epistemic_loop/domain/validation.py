from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from epistemic_loop.domain.enums import ExperimentType, HoldoutAccess, HoldoutPolicyName, Risk
from epistemic_loop.domain.models import Budget, BudgetUsage, ExperimentProposal


@dataclass(frozen=True)
class GateContext:
    hypothesis_ids: frozenset[str]
    budget: Budget
    usage: BudgetUsage
    holdout_policy: HoldoutPolicyName
    prior_fingerprints: frozenset[str] = frozenset()
    recent_experiment_types: tuple[ExperimentType, ...] = ()
    source_policy_strict: bool = True


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    fingerprint: str = ""


def experiment_fingerprint(experiment: ExperimentProposal) -> str:
    identity = {
        "hypothesis_ids": sorted(experiment.hypothesis_ids),
        "protocol": experiment.protocol.strip(),
        "split_strategy": experiment.split_strategy.strip(),
        "seeds": sorted(experiment.seeds),
        "metrics": sorted(experiment.metrics),
        "implementation_request": experiment.implementation_request,
    }
    value = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(value.encode()).hexdigest()


def hard_gate(experiment: ExperimentProposal, context: GateContext) -> GateResult:
    reasons: list[str] = []
    fingerprint = experiment_fingerprint(experiment)

    unknown = sorted(set(experiment.hypothesis_ids) - context.hypothesis_ids)
    if unknown:
        reasons.append(f"unknown hypotheses: {', '.join(unknown)}")
    if not experiment.predicted_outcomes:
        reasons.append("predicted outcomes are required")
    if not experiment.decision_rule.strip():
        reasons.append("decision rule is required")
    if not experiment.implementation_request.get("command"):
        reasons.append("reproducible implementation_request.command is required")
    if not experiment.required_artifacts:
        reasons.append("required artifacts are required")
    if experiment.contamination_risk == Risk.HIGH:
        reasons.append("high contamination risk")
    if context.source_policy_strict and any(not source.allowed for source in experiment.source_refs):
        reasons.append("experiment includes a prohibited source")
    if (
        context.holdout_policy == HoldoutPolicyName.STRICT_BLIND
        and experiment.holdout_access == HoldoutAccess.SEALED_HOLDOUT
    ):
        reasons.append("sealed holdout access is forbidden in strict_blind mode")
    if fingerprint in context.prior_fingerprints and experiment.experiment_type != ExperimentType.REPLICATION:
        reasons.append("duplicate experiment (only explicit replication may repeat)")

    cost = experiment.estimated_cost
    if context.usage.experiments + 1 > context.budget.max_experiments:
        reasons.append("experiment budget exceeded")
    if context.usage.cpu_hours + cost.cpu_hours > context.budget.max_cpu_hours:
        reasons.append("CPU budget exceeded")
    if context.usage.gpu_hours + cost.gpu_hours > context.budget.max_gpu_hours:
        reasons.append("GPU budget exceeded")
    if context.usage.wall_hours + cost.wall_hours > context.budget.max_wall_hours:
        reasons.append("wall-clock budget exceeded")
    if context.usage.llm_tokens + cost.llm_tokens > context.budget.max_llm_tokens:
        reasons.append("LLM token budget exceeded")
    if context.budget.max_cost and context.usage.cost + cost.monetary_cost > context.budget.max_cost:
        reasons.append("monetary budget exceeded")

    tail = context.recent_experiment_types[-3:]
    if (
        len(tail) == 3
        and all(kind == ExperimentType.OPTIMIZATION for kind in tail)
        and experiment.experiment_type == ExperimentType.OPTIMIZATION
    ):
        reasons.append("three consecutive optimization runs require a diagnostic, replication, or falsification run")

    return GateResult(passed=not reasons, reasons=tuple(reasons), fingerprint=fingerprint)
