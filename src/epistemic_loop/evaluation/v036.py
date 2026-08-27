"""Post-freeze evaluation for v0.3.6 blind real-agent qualification."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from statistics import fmean, median

from epistemic_loop.benchmark.v036_blind_suite import AgentAliasTruth, ContextTruth, SuiteTruth
from epistemic_loop.controller.v036_real_agent import (
    PackResearchSubmission,
    RealAgentSubmission,
    StructureResolution,
    V036ResearchMode,
)


class V036Status(StrEnum):
    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"
    UNMEASURED = "unmeasured"


@dataclass(frozen=True)
class WilsonInterval:
    estimate: float
    lower: float
    upper: float
    trials: int


@dataclass(frozen=True)
class EvaluatedPack:
    agent_id: str
    canonical_pack_id: str
    structure_present: bool
    resolution: StructureResolution
    confidence: float
    behaviorally_validated: bool
    explicitly_falsified: bool
    false_promotion: bool
    context_sealed_gains: tuple[float, ...]
    median_sealed_gain: float
    selected_sealed_auc: float
    shadow_oracle_auc: float
    selection_regret: float


@dataclass(frozen=True)
class RealAgentScorecard:
    agent_id: str
    semantic_family_count: int
    effective_family_count: float
    dominant_family_fraction: float
    action_mix: Mapping[str, int]
    exploration_to_exploitation_conversion: float
    true_structure_discovery_rate: float
    true_structure_rejection_rate: float
    false_structure_promotion_rate: float
    structure_resolution_rate: float
    useful_structure_transfer_rate: float | None
    brier_score: float
    expected_calibration_error: float
    mean_selection_regret: float


@dataclass(frozen=True)
class RealAgentPopulationReport:
    agents: tuple[RealAgentScorecard, ...]
    evaluated_packs: tuple[EvaluatedPack, ...]
    independent_research_diversity: float
    population_effective_family_count: float
    dominant_family_fraction: float
    executed_action_types: int
    dominant_action_fraction: float
    exploration_to_exploitation_conversion: float
    population_union_tsdr: float
    population_union_tsrr: float
    population_union_fspr: float
    structure_resolution_rate: float
    useful_structure_transfer_rate: float | None
    median_structure_sealed_gain: float | None
    brier_score: float
    expected_calibration_error: float
    tsdr_interval: WilsonInterval
    tsrr_interval: WilsonInterval
    fspr_interval: WilsonInterval
    best_agent_selected_auc: float
    population_selectable_auc: float
    population_oracle_auc: float
    shadow_candidate_recovery_rate: float


@dataclass(frozen=True)
class V036Reliability:
    controller_truth_leakage: int
    family_polarity_leakage: int
    sealed_label_leakage: int
    reference_probe_access: int
    artifact_completion: float
    oof_honesty: float
    sealed_isolation: float
    human_assisted_primary_runs: int

    @property
    def passed(self) -> bool:
        return (
            self.controller_truth_leakage == 0
            and self.family_polarity_leakage == 0
            and self.sealed_label_leakage == 0
            and self.reference_probe_access == 0
            and math.isclose(self.artifact_completion, 1.0)
            and math.isclose(self.oof_honesty, 1.0)
            and math.isclose(self.sealed_isolation, 1.0)
            and self.human_assisted_primary_runs == 0
        )


@dataclass(frozen=True)
class V036Acceptance:
    blindness: V036Status
    independent_diversity: V036Status
    evolution_exploration: V036Status
    structure_discovery: V036Status
    structure_rejection: V036Status
    calibration: V036Status
    transfer: V036Status
    reliability: V036Status
    overall: V036Status

    @classmethod
    def assess(cls, report: RealAgentPopulationReport, reliability: V036Reliability) -> V036Acceptance:
        diversity = (
            sum(item.semantic_family_count >= 2 for item in report.agents) >= 2
            and report.population_effective_family_count >= 2.5
            and report.dominant_family_fraction <= 0.60
        )
        evolution = report.executed_action_types >= 3 and report.exploration_to_exploitation_conversion > 0
        discovery = report.population_union_tsdr >= 0.60
        rejection = report.population_union_tsrr >= 0.80 and report.population_union_fspr <= 0.20
        resolution = report.structure_resolution_rate >= 0.70
        calibration = report.brier_score <= 0.20 and report.expected_calibration_error <= 0.20
        transfer = (
            report.useful_structure_transfer_rate is not None
            and report.useful_structure_transfer_rate >= 0.50
            and report.median_structure_sealed_gain is not None
            and report.median_structure_sealed_gain > 0
        )
        statuses = {
            "blindness": V036Status.PASS if reliability.passed else V036Status.FAIL,
            "independent_diversity": V036Status.PASS if diversity else V036Status.FAIL,
            "evolution_exploration": V036Status.PASS if evolution else V036Status.FAIL,
            "structure_discovery": V036Status.PASS if discovery else V036Status.FAIL,
            "structure_rejection": V036Status.PASS if rejection and resolution else V036Status.FAIL,
            "calibration": V036Status.PASS if calibration else V036Status.FAIL,
            "transfer": V036Status.PASS if transfer else V036Status.FAIL,
            "reliability": V036Status.PASS if reliability.passed else V036Status.FAIL,
        }
        passed = all(item is V036Status.PASS for item in statuses.values())
        if passed:
            overall = V036Status.PASS
        elif discovery and rejection and not transfer:
            overall = V036Status.PARTIAL
        else:
            overall = V036Status.FAIL
        return cls(**statuses, overall=overall)


def evaluate_real_agent_population(
    submissions: Sequence[RealAgentSubmission],
    truth: SuiteTruth,
) -> RealAgentPopulationReport:
    if len(submissions) != 3 or len({item.agent_id for item in submissions}) != 3:
        raise ValueError("v0.3.6 Phase 1 requires exactly three independent real agents")
    if any(item.suite_id != truth.suite_id for item in submissions):
        raise ValueError("submission suite does not match controller truth")
    aliases = {(item.agent_id, item.opaque_pack_id, item.opaque_context_id): item for item in truth.aliases}
    contexts = {(item.canonical_pack_id, item.canonical_context_id): item for item in truth.context_truth}
    evaluated = tuple(
        _evaluate_pack(submission.agent_id, pack, aliases, contexts)
        for submission in submissions
        for pack in submission.packs
    )
    agent_cards = tuple(_agent_scorecard(item, evaluated) for item in submissions)

    family_counts: Counter[str] = Counter(
        next(
            proposal.descriptor.hypothesis_family
            for proposal in cycle.proposals
            if proposal.mode is cycle.selected_mode
        )
        for submission in submissions
        for pack in submission.packs
        for cycle in pack.cycles
    )
    action_counts: Counter[str] = Counter(
        cycle.selected_mode.value for submission in submissions for pack in submission.packs for cycle in pack.cycles
    )
    action_counts["structure_maturation"] = sum(
        pack.resolution in {StructureResolution.VALIDATED_ACTIONABLE, StructureResolution.VALIDATED_NON_ACTIONABLE}
        for submission in submissions
        for pack in submission.packs
    )
    positive_ids = {item.canonical_pack_id for item in truth.context_truth if item.structure_present}
    negative_ids = {item.canonical_pack_id for item in truth.context_truth if not item.structure_present}
    union_discovered = {
        item.canonical_pack_id for item in evaluated if item.structure_present and item.behaviorally_validated
    }
    union_rejected = {
        item.canonical_pack_id for item in evaluated if not item.structure_present and item.explicitly_falsified
    }
    union_false = {item.canonical_pack_id for item in evaluated if not item.structure_present and item.false_promotion}
    resolved = [
        item
        for item in evaluated
        if item.resolution
        in {
            StructureResolution.VALIDATED_ACTIONABLE,
            StructureResolution.VALIDATED_NON_ACTIONABLE,
            StructureResolution.USEFUL_ENCODING_UNVALIDATED,
            StructureResolution.FALSIFIED,
        }
    ]
    actionable = [item for item in evaluated if item.structure_present and item.behaviorally_validated]
    useful = [item for item in actionable if item.median_sealed_gain > 0]
    converted, eligible = _conversion_counts(submissions)
    all_predictions = [pack.confidence for submission in submissions for pack in submission.packs]
    all_truth = [item.structure_present for item in evaluated]
    brier = fmean(
        (probability - float(outcome)) ** 2 for probability, outcome in zip(all_predictions, all_truth, strict=True)
    )
    ece = _ece(all_predictions, all_truth)
    selected_values = [item.selected_sealed_auc for item in evaluated]
    per_pack_selected: list[float] = []
    per_pack_oracle: list[float] = []
    for pack_id in sorted(positive_ids | negative_ids):
        values = [item for item in evaluated if item.canonical_pack_id == pack_id]
        selected = max(values, key=lambda item: item.selected_sealed_auc)
        per_pack_selected.append(selected.selected_sealed_auc)
        per_pack_oracle.append(max(item.shadow_oracle_auc for item in values))
    total_family = sum(family_counts.values())
    total_action = sum(action_counts.values())
    shadow_recoveries = sum(item.shadow_oracle_auc > item.selected_sealed_auc + 1e-12 for item in evaluated)
    return RealAgentPopulationReport(
        agents=agent_cards,
        evaluated_packs=evaluated,
        independent_research_diversity=sum(item.semantic_family_count >= 2 for item in agent_cards) / len(agent_cards),
        population_effective_family_count=_effective_count(family_counts),
        dominant_family_fraction=max(family_counts.values(), default=0) / total_family if total_family else 0.0,
        executed_action_types=sum(value > 0 for value in action_counts.values()),
        dominant_action_fraction=max(action_counts.values(), default=0) / total_action if total_action else 0.0,
        exploration_to_exploitation_conversion=converted / eligible if eligible else 0.0,
        population_union_tsdr=len(union_discovered) / len(positive_ids),
        population_union_tsrr=len(union_rejected) / len(negative_ids),
        population_union_fspr=len(union_false) / len(negative_ids),
        structure_resolution_rate=len(resolved) / len(evaluated),
        useful_structure_transfer_rate=len(useful) / len(actionable) if actionable else None,
        median_structure_sealed_gain=median(item.median_sealed_gain for item in actionable) if actionable else None,
        brier_score=brier,
        expected_calibration_error=ece,
        tsdr_interval=_wilson(len(union_discovered), len(positive_ids)),
        tsrr_interval=_wilson(len(union_rejected), len(negative_ids)),
        fspr_interval=_wilson(len(union_false), len(negative_ids)),
        best_agent_selected_auc=max(selected_values),
        population_selectable_auc=fmean(per_pack_selected),
        population_oracle_auc=fmean(per_pack_oracle),
        shadow_candidate_recovery_rate=shadow_recoveries / len(evaluated),
    )


def _evaluate_pack(
    agent_id: str,
    pack: PackResearchSubmission,
    aliases: Mapping[tuple[str, str, str], AgentAliasTruth],
    contexts: Mapping[tuple[str, str], ContextTruth],
) -> EvaluatedPack:
    resolved_contexts: list[tuple[ContextTruth, tuple[float, ...], tuple[float, ...]]] = []
    canonical_pack_ids: set[str] = set()
    for item in pack.contexts:
        alias = aliases[(agent_id, pack.opaque_pack_id, item.opaque_context_id)]
        truth = contexts[(alias.canonical_pack_id, alias.canonical_context_id)]
        canonical_pack_ids.add(alias.canonical_pack_id)
        if len(item.control_predictions) != len(truth.sealed_targets):
            raise ValueError("sealed prediction length does not match controller truth")
        resolved_contexts.append((truth, item.control_predictions, item.structure_predictions))
    if len(canonical_pack_ids) != 1:
        raise ValueError("an opaque pack mapped to multiple canonical packs")
    gains = tuple(
        _auc(truth.sealed_targets, structure) - _auc(truth.sealed_targets, control)
        for truth, control, structure in resolved_contexts
    )
    control_aucs = tuple(_auc(truth.sealed_targets, control) for truth, control, _ in resolved_contexts)
    structure_aucs = tuple(_auc(truth.sealed_targets, structure) for truth, _, structure in resolved_contexts)
    present = resolved_contexts[0][0].structure_present
    promoted = pack.resolution in {
        StructureResolution.VALIDATED_ACTIONABLE,
        StructureResolution.VALIDATED_NON_ACTIONABLE,
    }
    research_support = sum(item.research_gain > max(0.0, item.null_gain_95th_percentile) for item in pack.contexts) >= 2
    independent_support = sum(item.independent_implication_strength > 0.05 for item in pack.contexts) >= 2
    behaviorally_validated = bool(
        present
        and promoted
        and pack.matched_null_executed
        and pack.causal_safety_passed
        and pack.leave_one_context_out_stable
        and research_support
        and independent_support
    )
    selected = structure_aucs if pack.resolution is StructureResolution.VALIDATED_ACTIONABLE else control_aucs
    selected_auc = fmean(selected)
    shadow_oracle = fmean(max(left, right) for left, right in zip(control_aucs, structure_aucs, strict=True))
    return EvaluatedPack(
        agent_id=agent_id,
        canonical_pack_id=canonical_pack_ids.pop(),
        structure_present=present,
        resolution=pack.resolution,
        confidence=pack.confidence,
        behaviorally_validated=behaviorally_validated,
        explicitly_falsified=pack.resolution is StructureResolution.FALSIFIED,
        false_promotion=not present and promoted,
        context_sealed_gains=gains,
        median_sealed_gain=median(gains),
        selected_sealed_auc=selected_auc,
        shadow_oracle_auc=shadow_oracle,
        selection_regret=shadow_oracle - selected_auc,
    )


def _agent_scorecard(submission: RealAgentSubmission, evaluated: Sequence[EvaluatedPack]) -> RealAgentScorecard:
    families: Counter[str] = Counter(
        proposal.descriptor.hypothesis_family
        for pack in submission.packs
        for cycle in pack.cycles
        for proposal in cycle.proposals
        if proposal.mode is cycle.selected_mode
    )
    actions = Counter(cycle.selected_mode.value for pack in submission.packs for cycle in pack.cycles)
    actions["structure_maturation"] = sum(
        pack.resolution in {StructureResolution.VALIDATED_ACTIONABLE, StructureResolution.VALIDATED_NON_ACTIONABLE}
        for pack in submission.packs
    )
    values = [item for item in evaluated if item.agent_id == submission.agent_id]
    positives = [item for item in values if item.structure_present]
    negatives = [item for item in values if not item.structure_present]
    actionable = [item for item in positives if item.behaviorally_validated]
    useful = [item for item in actionable if item.median_sealed_gain > 0]
    resolved = [
        pack
        for pack in submission.packs
        if pack.resolution
        in {
            StructureResolution.VALIDATED_ACTIONABLE,
            StructureResolution.VALIDATED_NON_ACTIONABLE,
            StructureResolution.USEFUL_ENCODING_UNVALIDATED,
            StructureResolution.FALSIFIED,
        }
    ]
    converted, eligible = _conversion_counts((submission,))
    probabilities = [pack.confidence for pack in submission.packs]
    outcomes = [item.structure_present for item in values]
    total = sum(families.values())
    return RealAgentScorecard(
        agent_id=submission.agent_id,
        semantic_family_count=len(families),
        effective_family_count=_effective_count(families),
        dominant_family_fraction=max(families.values(), default=0) / total if total else 0.0,
        action_mix=dict(actions),
        exploration_to_exploitation_conversion=converted / eligible if eligible else 0.0,
        true_structure_discovery_rate=sum(item.behaviorally_validated for item in positives) / len(positives),
        true_structure_rejection_rate=sum(item.explicitly_falsified for item in negatives) / len(negatives),
        false_structure_promotion_rate=sum(item.false_promotion for item in negatives) / len(negatives),
        structure_resolution_rate=len(resolved) / len(submission.packs),
        useful_structure_transfer_rate=len(useful) / len(actionable) if actionable else None,
        brier_score=fmean((p - float(y)) ** 2 for p, y in zip(probabilities, outcomes, strict=True)),
        expected_calibration_error=_ece(probabilities, outcomes),
        mean_selection_regret=fmean(item.selection_regret for item in values),
    )


def _conversion_counts(submissions: Sequence[RealAgentSubmission]) -> tuple[int, int]:
    cycles = [
        cycle
        for submission in submissions
        for pack in submission.packs
        for cycle in pack.cycles
        if cycle.selected_mode in {V036ResearchMode.EXPLORE, V036ResearchMode.EPISTEMIC}
    ]
    return sum(item.converted_to_parent_or_final for item in cycles), len(cycles)


def _effective_count(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if not total:
        return 0.0
    probabilities = [value / total for value in counts.values()]
    return math.exp(-sum(value * math.log(value) for value in probabilities))


def _ece(probabilities: Sequence[float], outcomes: Sequence[bool], *, bins: int = 5) -> float:
    total = len(probabilities)
    if not total:
        return 0.0
    value = 0.0
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        selected = []
        for probability, outcome in zip(probabilities, outcomes, strict=True):
            in_bin = lower <= probability <= upper if index == bins - 1 else lower <= probability < upper
            if in_bin:
                selected.append((probability, outcome))
        if selected:
            mean_probability = fmean(item[0] for item in selected)
            empirical = fmean(float(item[1]) for item in selected)
            value += len(selected) / total * abs(mean_probability - empirical)
    return value


def _wilson(successes: int, trials: int, *, z: float = 1.959963984540054) -> WilsonInterval:
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("Wilson interval requires valid binomial counts")
    estimate = successes / trials
    denominator = 1 + z * z / trials
    center = (estimate + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(estimate * (1 - estimate) / trials + z * z / (4 * trials * trials)) / denominator
    return WilsonInterval(estimate, max(0.0, center - half), min(1.0, center + half), trials)


def _auc(targets: Sequence[int], predictions: Sequence[float]) -> float:
    positives = sum(targets)
    negatives = len(targets) - positives
    if len(targets) != len(predictions) or not targets or not positives or not negatives:
        raise ValueError("AUC inputs must be aligned and contain both classes")
    ordered = sorted(zip(predictions, targets, strict=True), key=lambda item: item[0])
    rank_sum = 0.0
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][0] == ordered[start][0]:
            end += 1
        rank_sum += (start + 1 + end) / 2 * sum(target for _, target in ordered[start:end])
        start = end
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)
