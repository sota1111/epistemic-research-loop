"""v0.3.8 evaluation: the locked v0.3.7 evaluator plus provenance, lineage, and cluster audits.

The v0.3.7 behavioral-discovery, evidence-based-rejection, matched-negative, and
controller-LOCO rules are reused verbatim so that v0.3.8 results are directly
comparable to the v0.3.7 baseline. v0.3.8 adds controller-side audits that the
baseline flagged as missing: machine-audited null provenance, controller-adjudicated
failure stages A-C, suite-by-seed cluster bootstrap intervals, and development-fit
calibration applied to qualification confidences.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import fmean

from epistemic_loop.benchmark.v037_repro_suite import V037SuiteTruth
from epistemic_loop.controller.v037_agent import NullStoppingReason
from epistemic_loop.controller.v038_agent import V038LoadedSubmission, adjudicated_failure_trace
from epistemic_loop.evaluation.calibration_v037 import IsotonicCalibrationMap
from epistemic_loop.evaluation.v037 import (
    V037Acceptance,
    V037AggregateReport,
    V037Calibration,
    _calibration,
    evaluate_v037_runs,
)

_BOOTSTRAP_ITERATIONS = 2000
_BOOTSTRAP_SEED = 20260827


@dataclass(frozen=True)
class V038BootstrapInterval:
    estimate: float
    lower: float
    upper: float
    blocks: int
    iterations: int


@dataclass(frozen=True)
class V038ProvenanceAudit:
    pack_count: int
    executed_null_packs: int
    packs_with_complete_provenance: int
    minimum_replicates: int
    maximum_replicates: int
    provenance_status: str
    interpretation: str


@dataclass(frozen=True)
class V038AgentCalibration:
    agent_id: str
    raw: V037Calibration
    calibrated: V037Calibration | None


@dataclass(frozen=True)
class V038AggregateReport:
    base: V037AggregateReport
    provenance_audit: V038ProvenanceAudit
    adjudicated_failure_stage_counts: Mapping[str, int]
    tsdr_cluster_interval: V038BootstrapInterval
    tsrr_cluster_interval: V038BootstrapInterval
    fspr_cluster_interval: V038BootstrapInterval
    agent_structure_calibration: tuple[V038AgentCalibration, ...]
    mean_pairwise_operator_jaccard: float
    per_agent_distinct_operators: Mapping[str, int]


@dataclass(frozen=True)
class V038Acceptance:
    base: V037Acceptance
    calibrated_median_structure_brier: float | None
    calibrated_median_structure_ece: float | None

    @property
    def overall(self) -> bool:
        return self.base.overall


def evaluate_v038_runs(
    loaded: Sequence[V038LoadedSubmission],
    truths: Sequence[V037SuiteTruth],
    calibration_map: IsotonicCalibrationMap | None = None,
    *,
    excluded_pairs: frozenset[tuple[str, str]] = frozenset(),
    expected_suite_count: int = 4,
) -> V038AggregateReport:
    cores = tuple(item.core for item in loaded)
    base = evaluate_v037_runs(cores, truths, excluded_pairs=excluded_pairs, expected_suite_count=expected_suite_count)
    return V038AggregateReport(
        base=base,
        provenance_audit=_provenance_audit(loaded),
        adjudicated_failure_stage_counts=_adjudicated_failure_counts(loaded, base, truths),
        tsdr_cluster_interval=_cluster_bootstrap(base, "behaviorally_discovered", positives=True),
        tsrr_cluster_interval=_cluster_bootstrap(base, "explicitly_rejected", positives=False),
        fspr_cluster_interval=_cluster_bootstrap(base, "false_promotion", positives=False),
        agent_structure_calibration=_agent_calibration(loaded, base, calibration_map),
        mean_pairwise_operator_jaccard=_operator_jaccard(loaded),
        per_agent_distinct_operators=_distinct_operators(loaded),
    )


def assess_v038(report: V038AggregateReport) -> V038Acceptance:
    calibrated = [item.calibrated for item in report.agent_structure_calibration if item.calibrated is not None]
    ordered_brier = sorted(item.brier for item in calibrated)
    ordered_ece = sorted(item.ece for item in calibrated)
    return V038Acceptance(
        base=V037Acceptance.assess(report.base),
        calibrated_median_structure_brier=_median_or_none(ordered_brier),
        calibrated_median_structure_ece=_median_or_none(ordered_ece),
    )


def _median_or_none(ordered: Sequence[float]) -> float | None:
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _provenance_audit(loaded: Sequence[V038LoadedSubmission]) -> V038ProvenanceAudit:
    executed = 0
    complete = 0
    counts: list[int] = []
    total = 0
    for submission in loaded:
        for pack in submission.core.packs:
            total += 1
            counts.append(len(pack.null_summary.replicate_gains))
            if pack.null_summary.stopping_reason is NullStoppingReason.NOT_RUN:
                continue
            executed += 1
            replicates = submission.extras.provenance.get(pack.opaque_pack_id, ())
            if len(replicates) == len(pack.null_summary.replicate_gains) and replicates:
                complete += 1
    return V038ProvenanceAudit(
        pack_count=total,
        executed_null_packs=executed,
        packs_with_complete_provenance=complete,
        minimum_replicates=min(counts) if counts else 0,
        maximum_replicates=max(counts) if counts else 0,
        provenance_status="MACHINE_AUDITED_DECLARED" if complete == executed else "INCOMPLETE",
        interpretation=(
            "Every executed null carries per-replicate permutation, feature, fold, model, and OOF "
            "artifacts that were structurally audited and hash-locked before unblinding. The "
            "artifacts are agent-computed; independent re-execution remains future work."
        ),
    )


def _adjudicated_failure_counts(
    loaded: Sequence[V038LoadedSubmission],
    base: V037AggregateReport,
    truths: Sequence[V037SuiteTruth],
) -> Mapping[str, int]:
    canonical_to_opaque: dict[tuple[str, str, str], str] = {}
    for truth in truths:
        for alias in truth.aliases:
            canonical_to_opaque[(truth.suite_id, alias.run_id, alias.canonical_pack_id)] = alias.opaque_pack_id
    stages_by_opaque: dict[tuple[str, str, str], dict[str, bool]] = {}
    for submission in loaded:
        for pack in submission.core.packs:
            key = (submission.core.suite_id, submission.core.run_id, pack.opaque_pack_id)
            stages_by_opaque[key] = adjudicated_failure_trace(pack)
    counts: dict[str, int] = {}
    for item in base.packs:
        if not item.structure_present or item.behaviorally_discovered:
            continue
        opaque_id = canonical_to_opaque.get((item.suite_id, item.run_id, item.canonical_pack_id), "")
        stages = stages_by_opaque.get((item.suite_id, item.run_id, opaque_id), {})
        if stages and not stages["hypothesis_generated"]:
            stage = "hypothesis_generation"
        elif stages and not stages["discriminating_test_proposed"]:
            stage = "experiment_design"
        elif stages and not stages["implementation_completed"]:
            stage = "implementation"
        else:
            stage = item.failure_stage
        counts[stage] = counts.get(stage, 0) + 1
    return counts


def _cluster_bootstrap(
    base: V037AggregateReport,
    field: str,
    *,
    positives: bool,
) -> V038BootstrapInterval:
    """Suite-by-seed block bootstrap; Wilson intervals ignore this correlation structure."""

    blocks: dict[tuple[str, int], list[bool]] = {}
    for item in base.packs:
        if item.structure_present is not positives:
            continue
        blocks.setdefault((item.suite_id, item.sampling_seed), []).append(bool(getattr(item, field)))
    ordered_blocks = [values for _, values in sorted(blocks.items())]
    flat = [value for values in ordered_blocks for value in values]
    estimate = sum(flat) / len(flat) if flat else 0.0
    generator = random.Random(_BOOTSTRAP_SEED)
    samples: list[float] = []
    for _ in range(_BOOTSTRAP_ITERATIONS):
        chosen = [ordered_blocks[generator.randrange(len(ordered_blocks))] for _ in ordered_blocks]
        pooled = [value for values in chosen for value in values]
        samples.append(sum(pooled) / len(pooled) if pooled else 0.0)
    samples.sort()
    lower = samples[max(0, int(0.025 * len(samples)) - 1)]
    upper = samples[min(len(samples) - 1, int(0.975 * len(samples)))]
    return V038BootstrapInterval(
        estimate=estimate,
        lower=min(lower, estimate),
        upper=max(upper, estimate),
        blocks=len(ordered_blocks),
        iterations=_BOOTSTRAP_ITERATIONS,
    )


def _agent_calibration(
    loaded: Sequence[V038LoadedSubmission],
    base: V037AggregateReport,
    calibration_map: IsotonicCalibrationMap | None,
) -> tuple[V038AgentCalibration, ...]:
    truth_by_run: dict[tuple[str, str], list[bool]] = {}
    for item in base.packs:
        truth_by_run.setdefault((item.suite_id, item.run_id), []).append(item.structure_present)
    output: list[V038AgentCalibration] = []
    for agent_id in sorted({item.core.agent_id for item in loaded}):
        probabilities: list[float] = []
        outcomes: list[bool] = []
        for submission in loaded:
            if submission.core.agent_id != agent_id:
                continue
            run_truth = truth_by_run[(submission.core.suite_id, submission.core.run_id)]
            run_probabilities = [pack.confidence.p_structure_exists for pack in submission.core.packs]
            if len(run_truth) != len(run_probabilities):
                raise ValueError("confidence and evaluated pack counts must align")
            probabilities.extend(run_probabilities)
            outcomes.extend(run_truth)
        raw = _calibration(probabilities, outcomes)
        calibrated = None
        if calibration_map is not None:
            calibrated = _calibration([calibration_map.apply(value) for value in probabilities], outcomes)
        output.append(V038AgentCalibration(agent_id=agent_id, raw=raw, calibrated=calibrated))
    return tuple(output)


def _selected_operators(loaded: Sequence[V038LoadedSubmission]) -> dict[str, set[str]]:
    operators: dict[str, set[str]] = {}
    for submission in loaded:
        bucket = operators.setdefault(submission.core.agent_id, set())
        for pack in submission.core.packs:
            for cycle in pack.cycles:
                for proposal in cycle.proposals:
                    if proposal.lineage_id == cycle.selected_lineage_id:
                        bucket.add(proposal.descriptor.experiment_operator.strip().lower())
    return operators


def _operator_jaccard(loaded: Sequence[V038LoadedSubmission]) -> float:
    operators = _selected_operators(loaded)
    agents = sorted(operators)
    pairs = [
        (operators[first], operators[second]) for index, first in enumerate(agents) for second in agents[index + 1 :]
    ]
    if not pairs:
        return 0.0
    scores = [len(left & right) / len(left | right) if left | right else 0.0 for left, right in pairs]
    return fmean(scores)


def _distinct_operators(loaded: Sequence[V038LoadedSubmission]) -> Mapping[str, int]:
    return {agent: len(values) for agent, values in sorted(_selected_operators(loaded).items())}
