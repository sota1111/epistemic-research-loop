"""Evaluation for v0.3.7 individual reproducibility and shared blind spots."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from statistics import fmean, median

from epistemic_loop.benchmark.v037_repro_suite import V037AliasTruth, V037ContextTruth, V037SuiteTruth
from epistemic_loop.controller.v037_agent import (
    V037AgentSubmission,
    V037ContextArtifact,
    V037PackSubmission,
    V037ResearchMode,
    V037Resolution,
)


@dataclass(frozen=True)
class V037WilsonInterval:
    estimate: float
    lower: float
    upper: float
    trials: int


@dataclass(frozen=True)
class V037Calibration:
    brier: float
    log_score: float
    ece: float


@dataclass(frozen=True)
class V037EvaluatedPack:
    suite_id: str
    run_id: str
    agent_id: str
    sampling_seed: int
    canonical_pack_id: str
    family: str
    matched_pair: str
    ladder_level: int | None
    structure_present: bool
    predictive_utility: bool
    behaviorally_discovered: bool
    explicitly_rejected: bool
    false_promotion: bool
    resolution: V037Resolution
    agent_reported_failure_stage: str
    failure_stage: str
    confirmation_selected_gain: float
    transfer_selected_gain: float
    transfer_best_translation_gain: float
    transfer_selection_regret: float
    null_replicates: int
    full_refit_null: bool
    controller_loco_stable: bool


@dataclass(frozen=True)
class V037RunScorecard:
    suite_id: str
    run_id: str
    agent_id: str
    sampling_seed: int
    prompt_arm: str
    lineage_policy: str
    tsdr: float
    tsrr: float
    fspr: float
    resolution_rate: float
    ustr: float | None
    semantic_family_count: int
    effective_family_count: float
    dominant_family_fraction: float
    action_types: int
    eecr: float
    deep_lineage_completion_rate: float
    premature_lineage_rejection_rate: float
    calibration_structure: V037Calibration
    calibration_evidence: V037Calibration
    calibration_actionable: V037Calibration
    calibration_transfer: V037Calibration
    mean_transfer_selection_regret: float


@dataclass(frozen=True)
class V037AgentAggregate:
    """Repeated-suite capability estimate for one generic agent identity."""

    agent_id: str
    sampling_seed: int | None
    runs: int
    positive_packs: int
    negative_packs: int
    tsdr: float
    tsrr: float
    fspr: float
    resolution_rate: float
    ustr: float | None
    calibration_structure: V037Calibration
    tsdr_interval: V037WilsonInterval
    tsrr_interval: V037WilsonInterval
    fspr_interval: V037WilsonInterval


@dataclass(frozen=True)
class V037PopulationBlock:
    suite_id: str
    sampling_seed: int
    union_tsdr: float
    union_tsrr: float
    union_fspr: float
    shared_blind_spot_rate: float
    discovery_complementarity: float
    rejection_complementarity: float
    leave_one_agent_out_tsrr: float
    marginal_agent_contribution_tsdr: Mapping[str, float]
    marginal_agent_contribution_tsrr: Mapping[str, float]
    persistent_levels_discovered: int
    persistent_agents_discovering: int


@dataclass(frozen=True)
class V037AggregateReport:
    runs: tuple[V037RunScorecard, ...]
    agent_aggregates: tuple[V037AgentAggregate, ...]
    agent_seed_aggregates: tuple[V037AgentAggregate, ...]
    packs: tuple[V037EvaluatedPack, ...]
    population_blocks: tuple[V037PopulationBlock, ...]
    median_agent_tsdr: float
    median_agent_tsrr: float
    worst_agent_fspr: float
    minimum_leave_one_agent_out_tsrr: float
    median_ustr: float | None
    overall_ustr: float | None
    median_structure_gain: float | None
    shared_blind_spot_rate: float
    median_structure_brier: float
    median_structure_ece: float
    worst_structure_brier: float
    worst_structure_ece: float
    persistent_levels_discovered: int
    persistent_agents_discovering: int
    independent_research_diversity: float
    population_effective_family_count: float
    population_dominant_family_fraction: float
    population_action_types: int
    overall_eecr: float
    overall_deep_lineage_completion_rate: float
    prompt_arm_summary: Mapping[str, Mapping[str, float]]
    lineage_policy_summary: Mapping[str, Mapping[str, float]]
    failure_stage_counts: Mapping[str, int]
    tsdr_interval: V037WilsonInterval
    tsrr_interval: V037WilsonInterval
    fspr_interval: V037WilsonInterval


@dataclass(frozen=True)
class V037Acceptance:
    median_agent_tsdr: bool
    median_agent_tsrr: bool
    all_agent_fspr: bool
    shared_blind_spots: bool
    leave_one_agent_out_rejection: bool
    transfer: bool
    calibration: bool
    persistent_ladder: bool
    overall: bool

    @classmethod
    def assess(cls, report: V037AggregateReport) -> V037Acceptance:
        calibration_pass = all(
            card.calibration_structure.brier <= 0.20 and card.calibration_structure.ece <= 0.20
            for card in report.agent_aggregates
        )
        values = {
            "median_agent_tsdr": report.median_agent_tsdr >= 0.50,
            "median_agent_tsrr": report.median_agent_tsrr >= 0.67,
            "all_agent_fspr": report.worst_agent_fspr <= 0.20,
            "shared_blind_spots": report.shared_blind_spot_rate <= 0.20,
            "leave_one_agent_out_rejection": report.minimum_leave_one_agent_out_tsrr >= 0.67,
            "transfer": report.overall_ustr is not None
            and report.overall_ustr >= 0.50
            and report.median_structure_gain is not None
            and report.median_structure_gain > 0,
            "calibration": calibration_pass,
            "persistent_ladder": report.persistent_levels_discovered >= 3 and report.persistent_agents_discovering >= 2,
        }
        return cls(**values, overall=all(values.values()))


def evaluate_v037_runs(
    submissions: Sequence[V037AgentSubmission],
    truths: Sequence[V037SuiteTruth],
    *,
    excluded_pairs: frozenset[tuple[str, str]] = frozenset(),
    expected_suite_count: int = 4,
) -> V037AggregateReport:
    """Evaluate locked outputs across a fixed number of suites without using transfer labels
    for discovery.

    ``excluded_pairs`` names (suite_id, run_id) slots that a preregistered, pre-unblinding
    deviation dropped from the batch (e.g. an infrastructure failure recorded before truth
    was opened). It defaults to empty, so the v0.3.7/8/9 callers that never pass it keep the
    exact 24-run gate unchanged.

    ``expected_suite_count`` names how many distinct suite instances (replicates) the study
    preregistered. It defaults to 4 (the v0.3.7 baseline every subsequent version reused), so
    v0.3.7/8/9 and any caller that doesn't pass it are unaffected. Nothing else in this module
    depends on the suite count being exactly 4 -- population blocks, cluster bootstrap blocks,
    and Wilson intervals are all computed generically over whatever suites are present -- so a
    study preregistering a different replicate count (chosen for its own statistical-power
    reasons, not to route around this default) should pass its own count explicitly here.
    """

    truth_by_suite = {item.suite_id: item for item in truths}
    if len(truth_by_suite) != expected_suite_count:
        raise ValueError(f"this study requires exactly {expected_suite_count} distinct locked qualification suites")
    full_grid = {(suite_id, run_id) for suite_id in truth_by_suite for run_id in _run_ids(truth_by_suite[suite_id])}
    if not excluded_pairs <= full_grid:
        raise ValueError("excluded_pairs must be a subset of the preregistered 24-run grid")
    expected_pairs = full_grid - excluded_pairs
    expected_total = len(expected_pairs)
    actual_pairs = {(item.suite_id, item.run_id) for item in submissions}
    if actual_pairs != expected_pairs or len(submissions) != expected_total:
        raise ValueError(f"v0.3.7 primary evaluation requires exactly {expected_total} unique agent runs")
    preliminary = tuple(
        _evaluate_submission_pack(submission, pack, truth_by_suite[submission.suite_id])
        for submission in submissions
        for pack in submission.packs
    )
    evaluated = _apply_matched_negative_gate(preliminary)
    cards = tuple(_run_scorecard(submission, evaluated) for submission in submissions)
    agent_aggregates = tuple(
        _agent_aggregate(agent_id, submissions, evaluated)
        for agent_id in sorted({submission.agent_id for submission in submissions})
    )
    agent_seed_aggregates = tuple(
        _agent_aggregate(agent_id, submissions, evaluated, sampling_seed)
        for agent_id in sorted({submission.agent_id for submission in submissions})
        for sampling_seed in sorted({submission.sampling_seed for submission in submissions})
    )
    blocks = tuple(
        _population_block(suite_id, sampling_seed, evaluated, truth)
        for suite_id, truth in sorted(truth_by_suite.items())
        for sampling_seed in sorted({alias.sampling_seed for alias in truth.aliases})
    )
    positives = [item for item in evaluated if item.structure_present]
    negatives = [item for item in evaluated if not item.structure_present]
    discovered = sum(item.behaviorally_discovered for item in positives)
    rejected = sum(item.explicitly_rejected for item in negatives)
    false = sum(item.false_promotion for item in negatives)
    actionable = [item for item in positives if item.behaviorally_discovered and item.predictive_utility]
    ustr_values = [card.ustr for card in cards if card.ustr is not None]
    selected_cycles = [cycle for submission in submissions for pack in submission.packs for cycle in pack.cycles]
    eligible_cycles = [cycle for cycle in selected_cycles if cycle.selected_mode is not V037ResearchMode.EXPLOIT]
    selected_families = Counter(
        proposal.descriptor.hypothesis_family
        for submission in submissions
        for pack in submission.packs
        for cycle in pack.cycles
        for proposal in cycle.proposals
        if proposal.lineage_id == cycle.selected_lineage_id
    )
    selected_family_total = sum(selected_families.values())
    ladder_levels = {
        item.ladder_level for item in positives if item.behaviorally_discovered and item.ladder_level is not None
    }
    ladder_agents = {
        item.agent_id for item in positives if item.behaviorally_discovered and item.ladder_level is not None
    }
    return V037AggregateReport(
        runs=cards,
        agent_aggregates=agent_aggregates,
        agent_seed_aggregates=agent_seed_aggregates,
        packs=evaluated,
        population_blocks=blocks,
        median_agent_tsdr=median(card.tsdr for card in agent_aggregates),
        median_agent_tsrr=median(card.tsrr for card in agent_aggregates),
        worst_agent_fspr=max(card.fspr for card in agent_aggregates),
        minimum_leave_one_agent_out_tsrr=min(block.leave_one_agent_out_tsrr for block in blocks),
        median_ustr=median(ustr_values) if ustr_values else None,
        overall_ustr=(
            sum(item.transfer_selected_gain > 0 for item in actionable) / len(actionable) if actionable else None
        ),
        median_structure_gain=(median(item.transfer_selected_gain for item in actionable) if actionable else None),
        # Sampling seeds are independent population replications.  Do not let a
        # discovery under one sampling seed erase a shared miss under another.
        shared_blind_spot_rate=fmean(block.shared_blind_spot_rate for block in blocks),
        median_structure_brier=median(card.calibration_structure.brier for card in agent_aggregates),
        median_structure_ece=median(card.calibration_structure.ece for card in agent_aggregates),
        worst_structure_brier=max(card.calibration_structure.brier for card in agent_aggregates),
        worst_structure_ece=max(card.calibration_structure.ece for card in agent_aggregates),
        persistent_levels_discovered=len(ladder_levels),
        persistent_agents_discovering=len(ladder_agents),
        independent_research_diversity=sum(card.semantic_family_count >= 2 for card in cards) / len(cards),
        population_effective_family_count=_effective_count(selected_families),
        population_dominant_family_fraction=(
            max(selected_families.values(), default=0) / selected_family_total if selected_family_total else 0.0
        ),
        population_action_types=len({cycle.selected_mode for cycle in selected_cycles}),
        overall_eecr=(
            sum(cycle.converted_to_parent_or_final for cycle in eligible_cycles) / len(eligible_cycles)
            if eligible_cycles
            else 0.0
        ),
        overall_deep_lineage_completion_rate=(
            sum(cycle.lineage_followup or cycle.lineage_explicitly_closed for cycle in eligible_cycles)
            / len(eligible_cycles)
            if eligible_cycles
            else 0.0
        ),
        prompt_arm_summary=_arm_summary(cards, "prompt_arm"),
        lineage_policy_summary=_arm_summary(cards, "lineage_policy"),
        failure_stage_counts=dict(
            Counter(item.failure_stage for item in positives if not item.behaviorally_discovered)
        ),
        tsdr_interval=_wilson(discovered, len(positives)),
        tsrr_interval=_wilson(rejected, len(negatives)),
        fspr_interval=_wilson(false, len(negatives)),
    )


def _agent_aggregate(
    agent_id: str,
    submissions: Sequence[V037AgentSubmission],
    evaluated: Sequence[V037EvaluatedPack],
    sampling_seed: int | None = None,
) -> V037AgentAggregate:
    """Pool locked repetitions for an agent without collapsing sampling seeds."""

    selected_submissions = [
        item
        for item in submissions
        if item.agent_id == agent_id and (sampling_seed is None or item.sampling_seed == sampling_seed)
    ]
    packs = [
        item
        for item in evaluated
        if item.agent_id == agent_id and (sampling_seed is None or item.sampling_seed == sampling_seed)
    ]
    positives = [item for item in packs if item.structure_present]
    negatives = [item for item in packs if not item.structure_present]
    discovered = sum(item.behaviorally_discovered for item in positives)
    rejected = sum(item.explicitly_rejected for item in negatives)
    false = sum(item.false_promotion for item in negatives)
    actionable = [item for item in positives if item.behaviorally_discovered and item.predictive_utility]
    confidence = [pack.confidence for submission in selected_submissions for pack in submission.packs]
    structure_truth = [item.structure_present for item in packs]
    if len(confidence) != len(packs):
        raise ValueError("agent confidence and evaluated packs must align")
    return V037AgentAggregate(
        agent_id=agent_id,
        sampling_seed=sampling_seed,
        runs=len(selected_submissions),
        positive_packs=len(positives),
        negative_packs=len(negatives),
        tsdr=discovered / len(positives),
        tsrr=rejected / len(negatives),
        fspr=false / len(negatives),
        resolution_rate=sum(item.resolution is not V037Resolution.INCONCLUSIVE for item in packs) / len(packs),
        ustr=(sum(item.transfer_selected_gain > 0 for item in actionable) / len(actionable) if actionable else None),
        calibration_structure=_calibration(
            [item.p_structure_exists for item in confidence],
            structure_truth,
        ),
        tsdr_interval=_wilson(discovered, len(positives)),
        tsrr_interval=_wilson(rejected, len(negatives)),
        fspr_interval=_wilson(false, len(negatives)),
    )


def _evaluate_submission_pack(
    submission: V037AgentSubmission,
    pack: V037PackSubmission,
    truth: V037SuiteTruth,
) -> V037EvaluatedPack:
    aliases = {(item.run_id, item.opaque_pack_id, item.opaque_context_id): item for item in truth.aliases}
    contexts = {(item.canonical_pack_id, item.canonical_context_id): item for item in truth.context_truth}
    resolved: list[tuple[V037ContextTruth, V037AliasTruth, V037ContextArtifact]] = []
    pack_ids: set[str] = set()
    for artifact in pack.contexts:
        alias = aliases[(submission.run_id, pack.opaque_pack_id, artifact.opaque_context_id)]
        context = contexts[(alias.canonical_pack_id, alias.canonical_context_id)]
        pack_ids.add(alias.canonical_pack_id)
        resolved.append((context, alias, artifact))
    if len(pack_ids) != 1:
        raise ValueError("one opaque pack mapped to multiple canonical packs")
    first = resolved[0][0]
    promoted = pack.resolution in {
        V037Resolution.VALIDATED_ACTIONABLE_TRANSFERRED,
        V037Resolution.VALIDATED_ACTIONABLE_NOT_TRANSFERRED,
        V037Resolution.VALIDATED_NON_ACTIONABLE,
    }
    research_support = sum(artifact.research_gain > _null_percentile(pack, 0.95) for _, _, artifact in resolved) >= 2
    implication_support = sum(artifact.independent_implication_strength > 0.05 for _, _, artifact in resolved) >= 2
    confirmation_gains: list[float] = []
    transfer_selected_gains: list[float] = []
    transfer_best_gains: list[float] = []
    for _, alias, raw_artifact in resolved:
        artifact = raw_artifact
        control_confirmation = _auc(
            alias.confirmation_targets_in_view_order,
            artifact.control_confirmation_predictions,
        )
        selected_translation = next(
            item for item in artifact.translations if item.candidate_id == pack.selected_translation_id
        )
        confirmation_gains.append(
            _auc(alias.confirmation_targets_in_view_order, selected_translation.confirmation_predictions)
            - control_confirmation
        )
        control_transfer = _auc(alias.transfer_targets_in_view_order, artifact.control_transfer_predictions)
        translation_transfer = {
            item.candidate_id: _auc(alias.transfer_targets_in_view_order, item.transfer_predictions)
            for item in artifact.translations
        }
        transfer_selected_gains.append(translation_transfer[pack.selected_translation_id] - control_transfer)
        transfer_best_gains.append(max(translation_transfer.values()) - control_transfer)
    confirmation_support = sum(value > 0 for value in confirmation_gains) >= 2 and min(confirmation_gains) > -0.01
    if first.predictive_utility:
        stability_values = confirmation_gains
    else:
        stability_values = [artifact.independent_implication_strength - 0.05 for _, _, artifact in resolved]
    controller_loco_stable = all(
        median(value for position, value in enumerate(stability_values) if position != held_out) > 0
        for held_out in range(len(stability_values))
    )
    persistent_behavior = (
        pack.failure_trace.above_row_unit_considered and pack.failure_trace.history_or_link_intervention_considered
        if first.ladder_level is not None
        else True
    )
    primary_research_support = research_support if first.predictive_utility else implication_support
    discovery_support = confirmation_support if first.predictive_utility else implication_support
    discovered = bool(
        first.structure_present
        and promoted
        and primary_research_support
        and implication_support
        and discovery_support
        and persistent_behavior
        and pack.causal_safety_passed
        and controller_loco_stable
        and pack.null_summary.all_replicates_refit_features_and_model
        and len(pack.null_summary.replicate_gains) >= 5
    )
    explicitly_rejected = bool(
        pack.resolution is V037Resolution.FALSIFIED
        and not research_support
        and not implication_support
        and not confirmation_support
        and pack.causal_safety_passed
        and pack.null_summary.all_replicates_refit_features_and_model
        and len(pack.null_summary.replicate_gains) >= 5
    )
    reported_failure_stage = pack.failure_trace.failure_stage
    if discovered:
        failure_stage = "none"
    elif reported_failure_stage != "none":
        failure_stage = reported_failure_stage
    elif not (primary_research_support and implication_support and discovery_support and persistent_behavior):
        # The agent reported every procedural step complete, but the locked
        # evidence did not satisfy the preregistered behavioral discovery gate.
        failure_stage = "evidence"
    else:
        # Supporting evidence existed, but the terminal claim or a promotion
        # safety/stability requirement did not pass.
        failure_stage = "promotion"
    selected_gain = median(transfer_selected_gains)
    best_gain = median(transfer_best_gains)
    return V037EvaluatedPack(
        suite_id=submission.suite_id,
        run_id=submission.run_id,
        agent_id=submission.agent_id,
        sampling_seed=submission.sampling_seed,
        canonical_pack_id=pack_ids.pop(),
        family=first.family,
        matched_pair=first.matched_pair,
        ladder_level=first.ladder_level,
        structure_present=first.structure_present,
        predictive_utility=first.predictive_utility,
        behaviorally_discovered=discovered,
        explicitly_rejected=explicitly_rejected,
        false_promotion=not first.structure_present and promoted,
        resolution=pack.resolution,
        agent_reported_failure_stage=reported_failure_stage,
        failure_stage=failure_stage,
        confirmation_selected_gain=median(confirmation_gains),
        transfer_selected_gain=selected_gain,
        transfer_best_translation_gain=best_gain,
        transfer_selection_regret=max(0.0, best_gain - selected_gain),
        null_replicates=len(pack.null_summary.replicate_gains),
        full_refit_null=pack.null_summary.all_replicates_refit_features_and_model,
        controller_loco_stable=controller_loco_stable,
    )


def _apply_matched_negative_gate(
    evaluated: Sequence[V037EvaluatedPack],
) -> tuple[V037EvaluatedPack, ...]:
    """Require paired negative rejection for persistent-unit promotion.

    The paired negative is evaluated for the same suite, run, and matched
    surface statistics.  This prevents a generic grouping/linkage pipeline
    from receiving discovery credit when it also promotes the nonpersistent
    control.
    """

    negative_by_pair = {
        (item.suite_id, item.run_id, item.matched_pair): item for item in evaluated if not item.structure_present
    }
    output: list[V037EvaluatedPack] = []
    for item in evaluated:
        if item.structure_present and item.ladder_level is not None and item.behaviorally_discovered:
            paired_negative = negative_by_pair.get((item.suite_id, item.run_id, item.matched_pair))
            paired_rejected = bool(
                paired_negative is not None
                and paired_negative.explicitly_rejected
                and not paired_negative.false_promotion
            )
            if not paired_rejected:
                item = replace(item, behaviorally_discovered=False, failure_stage="matched_negative")
        output.append(item)
    return tuple(output)


def _run_scorecard(
    submission: V037AgentSubmission,
    evaluated: Sequence[V037EvaluatedPack],
) -> V037RunScorecard:
    packs = [item for item in evaluated if item.suite_id == submission.suite_id and item.run_id == submission.run_id]
    positives = [item for item in packs if item.structure_present]
    negatives = [item for item in packs if not item.structure_present]
    actionable = [item for item in positives if item.behaviorally_discovered and item.predictive_utility]
    families = Counter(
        proposal.descriptor.hypothesis_family
        for pack in submission.packs
        for cycle in pack.cycles
        for proposal in cycle.proposals
        if proposal.lineage_id == cycle.selected_lineage_id
    )
    selected_cycles = [cycle for pack in submission.packs for cycle in pack.cycles]
    eligible = [cycle for cycle in selected_cycles if cycle.selected_mode is not V037ResearchMode.EXPLOIT]
    deep = [cycle for cycle in eligible if cycle.lineage_followup or cycle.lineage_explicitly_closed]
    premature = [cycle for cycle in eligible if not cycle.lineage_followup and not cycle.lineage_explicitly_closed]
    total = sum(families.values())
    structure_truth = [item.structure_present for item in packs]
    discovered_truth = [item.behaviorally_discovered for item in packs]
    actionable_truth = [item.structure_present and item.predictive_utility for item in packs]
    transfer_truth = [item.transfer_selected_gain > 0 for item in packs]
    confidence = [pack.confidence for pack in submission.packs]
    return V037RunScorecard(
        suite_id=submission.suite_id,
        run_id=submission.run_id,
        agent_id=submission.agent_id,
        sampling_seed=submission.sampling_seed,
        prompt_arm=submission.prompt_arm,
        lineage_policy=submission.lineage_policy.value,
        tsdr=sum(item.behaviorally_discovered for item in positives) / len(positives),
        tsrr=sum(item.explicitly_rejected for item in negatives) / len(negatives),
        fspr=sum(item.false_promotion for item in negatives) / len(negatives),
        resolution_rate=sum(item.resolution is not V037Resolution.INCONCLUSIVE for item in packs) / len(packs),
        ustr=(sum(item.transfer_selected_gain > 0 for item in actionable) / len(actionable) if actionable else None),
        semantic_family_count=len(families),
        effective_family_count=_effective_count(families),
        dominant_family_fraction=max(families.values(), default=0) / total if total else 0.0,
        action_types=len({cycle.selected_mode for cycle in selected_cycles}),
        eecr=(sum(cycle.converted_to_parent_or_final for cycle in eligible) / len(eligible) if eligible else 0.0),
        deep_lineage_completion_rate=len(deep) / len(eligible) if eligible else 0.0,
        premature_lineage_rejection_rate=len(premature) / len(eligible) if eligible else 0.0,
        calibration_structure=_calibration([item.p_structure_exists for item in confidence], structure_truth),
        calibration_evidence=_calibration([item.p_evidence_sufficient for item in confidence], discovered_truth),
        calibration_actionable=_calibration([item.p_actionable for item in confidence], actionable_truth),
        calibration_transfer=_calibration([item.p_positive_transfer for item in confidence], transfer_truth),
        mean_transfer_selection_regret=fmean(item.transfer_selection_regret for item in packs),
    )


def _population_block(
    suite_id: str,
    sampling_seed: int,
    evaluated: Sequence[V037EvaluatedPack],
    truth: V037SuiteTruth,
) -> V037PopulationBlock:
    values = [item for item in evaluated if item.suite_id == suite_id and item.sampling_seed == sampling_seed]
    positive_ids = {item.canonical_pack_id for item in truth.context_truth if item.structure_present}
    negative_ids = {item.canonical_pack_id for item in truth.context_truth if not item.structure_present}
    union_discovered = {item.canonical_pack_id for item in values if item.behaviorally_discovered}
    union_rejected = {
        item.canonical_pack_id for item in values if not item.structure_present and item.explicitly_rejected
    }
    union_false = {item.canonical_pack_id for item in values if item.false_promotion}
    per_agent_discovered = {
        agent: {item.canonical_pack_id for item in values if item.agent_id == agent and item.behaviorally_discovered}
        for agent in sorted({item.agent_id for item in values})
    }
    per_agent_rejected = {
        agent: {
            item.canonical_pack_id
            for item in values
            if item.agent_id == agent and not item.structure_present and item.explicitly_rejected
        }
        for agent in sorted({item.agent_id for item in values})
    }
    leave_out_tsrr: list[float] = []
    mac_tsdr: dict[str, float] = {}
    mac_tsrr: dict[str, float] = {}
    union_tsdr = len(union_discovered) / len(positive_ids)
    union_tsrr = len(union_rejected) / len(negative_ids)
    for agent in per_agent_discovered:
        discovered_without = set().union(*(ids for name, ids in per_agent_discovered.items() if name != agent))
        rejected_without = set().union(*(ids for name, ids in per_agent_rejected.items() if name != agent))
        without_tsdr = len(discovered_without) / len(positive_ids)
        without_tsrr = len(rejected_without) / len(negative_ids)
        leave_out_tsrr.append(without_tsrr)
        mac_tsdr[agent] = union_tsdr - without_tsdr
        mac_tsrr[agent] = union_tsrr - without_tsrr
    missed = positive_ids - union_discovered
    persistent = [item for item in values if item.ladder_level is not None and item.behaviorally_discovered]
    return V037PopulationBlock(
        suite_id=suite_id,
        sampling_seed=sampling_seed,
        union_tsdr=union_tsdr,
        union_tsrr=union_tsrr,
        union_fspr=len(union_false) / len(negative_ids),
        shared_blind_spot_rate=len(missed) / len(positive_ids),
        discovery_complementarity=union_tsdr
        - max((len(ids) / len(positive_ids) for ids in per_agent_discovered.values()), default=0.0),
        rejection_complementarity=union_tsrr
        - max((len(ids) / len(negative_ids) for ids in per_agent_rejected.values()), default=0.0),
        leave_one_agent_out_tsrr=min(leave_out_tsrr),
        marginal_agent_contribution_tsdr=mac_tsdr,
        marginal_agent_contribution_tsrr=mac_tsrr,
        persistent_levels_discovered=len({item.ladder_level for item in persistent}),
        persistent_agents_discovering=len({item.agent_id for item in persistent}),
    )


def _arm_summary(cards: Sequence[V037RunScorecard], field: str) -> Mapping[str, Mapping[str, float]]:
    arms = sorted({str(getattr(card, field)) for card in cards})
    output: dict[str, Mapping[str, float]] = {}
    for arm in arms:
        selected = [card for card in cards if str(getattr(card, field)) == arm]
        output[arm] = {
            "runs": float(len(selected)),
            "mean_tsdr": fmean(card.tsdr for card in selected),
            "median_tsdr": median(card.tsdr for card in selected),
            "mean_tsrr": fmean(card.tsrr for card in selected),
            "median_tsrr": median(card.tsrr for card in selected),
            "mean_fspr": fmean(card.fspr for card in selected),
            "median_fspr": median(card.fspr for card in selected),
            "maximum_fspr": max(card.fspr for card in selected),
            "median_eecr": median(card.eecr for card in selected),
            "median_deep_lineage_completion": median(card.deep_lineage_completion_rate for card in selected),
        }
    return output


def _run_ids(truth: V037SuiteTruth) -> set[str]:
    return {item.run_id for item in truth.aliases}


def _null_percentile(pack: V037PackSubmission, quantile: float) -> float:
    values = sorted(pack.null_summary.replicate_gains)
    if not values:
        return math.inf
    index = min(len(values) - 1, max(0, math.ceil(quantile * len(values)) - 1))
    return values[index]


def _calibration(probabilities: Sequence[float], outcomes: Sequence[bool]) -> V037Calibration:
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("calibration inputs must be aligned")
    clipped = [min(1 - 1e-12, max(1e-12, value)) for value in probabilities]
    brier = fmean((probability - float(outcome)) ** 2 for probability, outcome in zip(clipped, outcomes, strict=True))
    log_score = -fmean(
        float(outcome) * math.log(probability) + (1 - float(outcome)) * math.log(1 - probability)
        for probability, outcome in zip(clipped, outcomes, strict=True)
    )
    return V037Calibration(brier=brier, log_score=log_score, ece=_ece(clipped, outcomes))


def _ece(probabilities: Sequence[float], outcomes: Sequence[bool], bins: int = 5) -> float:
    value = 0.0
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        selected = [
            (probability, outcome)
            for probability, outcome in zip(probabilities, outcomes, strict=True)
            if (lower <= probability <= upper if index == bins - 1 else lower <= probability < upper)
        ]
        if selected:
            value += (
                len(selected)
                / len(probabilities)
                * abs(fmean(item[0] for item in selected) - fmean(float(item[1]) for item in selected))
            )
    return value


def _effective_count(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if not total:
        return 0.0
    probabilities = [value / total for value in counts.values()]
    return math.exp(-sum(value * math.log(value) for value in probabilities))


def _wilson(successes: int, trials: int, z: float = 1.959963984540054) -> V037WilsonInterval:
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("Wilson interval requires valid binomial counts")
    estimate = successes / trials
    denominator = 1 + z * z / trials
    center = (estimate + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(estimate * (1 - estimate) / trials + z * z / (4 * trials * trials)) / denominator
    return V037WilsonInterval(estimate, max(0.0, center - half), min(1.0, center + half), trials)


def _auc(targets: Sequence[int], predictions: Sequence[float]) -> float:
    if len(targets) != len(predictions) or not targets:
        raise ValueError("AUC inputs must be non-empty and aligned")
    positives = sum(targets)
    negatives = len(targets) - positives
    if not positives or not negatives:
        return 0.5
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
