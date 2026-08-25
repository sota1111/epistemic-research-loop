from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from epistemic_loop.domain.enums import ExperimentType, HoldoutAccess, HoldoutPolicyName, Risk
from epistemic_loop.domain.models import Budget, BudgetUsage, ExperimentProposal
from epistemic_loop.holdout.adaptivity import exhausted as validation_budget_exhausted
from epistemic_loop.holdout.adaptivity import validation_fingerprint

#: Declared here rather than imported from the contract module, which imports this one.
NETWORK_POLICIES = ("disabled", "source_policy_proxy", "enabled")


@dataclass(frozen=True)
class GateContext:
    hypothesis_ids: frozenset[str]
    budget: Budget
    usage: BudgetUsage
    holdout_policy: HoldoutPolicyName
    prior_fingerprints: frozenset[str] = frozenset()
    recent_experiment_types: tuple[ExperimentType, ...] = ()
    source_policy_strict: bool = True
    validation_reuse: Mapping[str, int] = field(default_factory=dict)
    max_validation_reuse: int = 0
    #: Consecutive optimization experiments allowed before a non-optimization run is required.
    #: 0 disables the rule, which is what an exploiter-only control arm needs.
    max_consecutive_optimization: int = 3
    #: Lineages the research brief approved. Empty means no brief has been published, and the
    #: restriction does not apply -- exploitation cannot be entered without one anyway.
    approved_lineages: frozenset[str] = frozenset()
    #: Executables a shell executor will accept. Empty means the executor imposes no list.
    command_allowlist: tuple[str, ...] = ()
    #: What the configured executor needs a proposal to carry. Checked here so a proposal is never
    #: refused at dispatch -- after design, gating and selection have all succeeded -- for
    #: something that could have been refused before any of them.
    required_request_fields: tuple[str, ...] = ()
    required_brief_fields: tuple[str, ...] = ()
    #: Shortcuts the brief prohibited, matched against the experiment's holdout access.
    prohibited_shortcuts: tuple[str, ...] = ()


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
    unlinked_forecasts = sorted(
        {item.hypothesis_id for item in experiment.outcome_forecasts} - set(experiment.hypothesis_ids)
    )
    if unlinked_forecasts:
        reasons.append(f"outcome forecasts target unlinked hypotheses: {', '.join(unlinked_forecasts)}")
    if not experiment.predicted_outcomes:
        reasons.append("predicted outcomes are required")
    if not experiment.decision_rule.strip():
        reasons.append("decision rule is required")
    request = experiment.implementation_request
    if not request.get("command") and not request.get("brief"):
        reasons.append("implementation_request needs a reproducible `command` or a `brief`")
    missing = [name for name in context.required_request_fields if not request.get(name)]
    if missing:
        reasons.append(f"implementation_request is missing {missing}, which the configured executor requires")
    if context.required_brief_fields:
        brief = request.get("brief")
        if brief is not None and not isinstance(brief, dict):
            reasons.append("implementation_request.brief must be an object")
        elif isinstance(brief, dict):
            absent = [name for name in context.required_brief_fields if not str(brief.get(name) or "").strip()]
            if absent:
                reasons.append(f"implementation_request.brief is missing {absent}")
    command = str(experiment.implementation_request.get("command") or "")
    if command and context.command_allowlist:
        import shlex

        try:
            head = shlex.split(command)[:1]
        except ValueError:
            head = []
        # Refused here rather than at dispatch, where the executor's PermissionError takes the whole
        # round -- and the loop -- down for a constraint the proposal could have been checked against.
        if not head:
            reasons.append("implementation_request.command could not be parsed as a shell command")
        elif Path(head[0]).name not in context.command_allowlist:
            reasons.append(
                f"command must start with one of {list(context.command_allowlist)}, not {Path(head[0]).name!r}"
            )
    policy = experiment.implementation_request.get("network_policy")
    if policy is not None and policy not in NETWORK_POLICIES:
        # Caught here rather than when the contract is built, because by then the experiment has
        # already been selected and the round is spent on a value the gate could have refused.
        reasons.append(f"implementation_request.network_policy {policy!r} must be one of {list(NETWORK_POLICIES)}")
    resources = experiment.implementation_request.get("resources")
    if resources is not None and not isinstance(resources, dict):
        reasons.append("implementation_request.resources must be an object")
    if not experiment.required_artifacts:
        reasons.append("required artifacts are required")
    for artifact in experiment.required_artifacts:
        # Checked for existence after the run, so a sentence describing a file is a guaranteed
        # failure -- and one discovered only after the experiment has already been executed.
        if not artifact or " " in artifact or artifact.startswith("/") or ".." in artifact:
            reasons.append(f"required_artifacts must be plain relative file names, not {artifact!r}")
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
    if validation_budget_exhausted(experiment, dict(context.validation_reuse), context.max_validation_reuse):
        reasons.append(
            f"validation adaptivity budget of {context.max_validation_reuse} selecting queries is exhausted "
            f"for split {validation_fingerprint(experiment)[:12]}; rotate the split or run a diagnostic"
        )

    if context.approved_lineages and experiment.lineage not in context.approved_lineages:
        # A research brief that the exploiter can ignore is a record of a decision, not a hand-off.
        # Once one is published, the search space it defines is the search space -- an experiment
        # outside it is proposing to explore, which is what the hand-off ended.
        reasons.append(
            f"lineage {experiment.lineage!r} is outside the research brief's approved set "
            f"{sorted(context.approved_lineages)}"
        )
    if experiment.holdout_access == HoldoutAccess.SEALED_HOLDOUT and any(
        "sealed holdout" in shortcut.lower() for shortcut in context.prohibited_shortcuts
    ):
        reasons.append("the research brief prohibits sealed holdout optimization")

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

    limit = context.max_consecutive_optimization
    tail = context.recent_experiment_types[-limit:] if limit else ()
    if (
        limit
        and len(tail) == limit
        and all(kind == ExperimentType.OPTIMIZATION for kind in tail)
        and experiment.experiment_type == ExperimentType.OPTIMIZATION
    ):
        reasons.append(f"{limit} consecutive optimization runs require a diagnostic, replication, or falsification run")

    return GateResult(passed=not reasons, reasons=tuple(reasons), fingerprint=fingerprint)
