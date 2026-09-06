from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from epistemic_loop.belief.calibration import summarize_calibration
from epistemic_loop.controller.run_state import RunState
from epistemic_loop.domain.enums import HypothesisStatus, HypothesisType
from epistemic_loop.domain.models import ResearchStateSnapshot, StructurePromotionAssessment
from epistemic_loop.domain.preferred_state import (
    MEASURED_DIMENSIONS,
    SPECIFICATION_STATES,
    UNMEASURED_STATES,
    unknown_dimensions,
)
from epistemic_loop.qd.archive import QDArchive
from epistemic_loop.qd.descriptors import descriptor_names_for_mode
from epistemic_loop.validation.worlds import posterior_entropy, validation_fidelity

RESOLVED = {HypothesisStatus.SUPPORTED, HypothesisStatus.CONTESTED, HypothesisStatus.FALSIFIED}


def derive_research_state(
    state: RunState,
    *,
    maximum_archive_size: int = 100,
    preferred_targets: Mapping[str, float] | None = None,
    preferred_weights: Mapping[str, float] | None = None,
    structural_assessments: Sequence[StructurePromotionAssessment] = (),
) -> ResearchStateSnapshot:
    worlds = list(state.validation_worlds.values())
    fidelity_values = [
        (world.posterior_probability, value)
        for world in worlds
        if (value := validation_fidelity(world.diagnostics)) is not None
    ]
    fidelity_mass = sum(probability for probability, _ in fidelity_values)
    fidelity = (
        sum(probability * value for probability, value in fidelity_values) / fidelity_mass if fidelity_mass else None
    )
    hypotheses = list(state.hypotheses.values())
    active = [item for item in hypotheses if item.status != HypothesisStatus.RETIRED]
    entropy = sum(_binary_entropy(item.current_confidence) for item in active)
    covered_types = {item.type for item in active}
    attacked = {record.hypothesis_id for record in state.falsifications.values()}
    descriptors = descriptor_names_for_mode(state.run.mode)
    if descriptors and state.qd_candidates:
        archive = QDArchive.rebuild(
            state.qd_candidates.values(),
            descriptor_names=descriptors,
            maximum_size=maximum_archive_size,
        )
        occupancy = archive.occupancy / maximum_archive_size
        candidates = list(archive.candidates)
    else:
        occupancy = 0.0
        candidates = []
    best = max(candidates, key=lambda item: item.expected_hidden_score, default=None)
    spread = math.sqrt(best.score_variance) if best is not None else 0.0
    latest_oof = state.oof_analyses[-1] if state.oof_analyses else {}
    effective_rank = float(latest_oof.get("covariance_effective_rank", 0.0))
    calibration = summarize_calibration(state.forecast_calibrations) if state.forecast_calibrations else None
    dgp_understanding = (
        sum(item.structural_validity_passed for item in structural_assessments) / len(structural_assessments)
        if structural_assessments
        else 0.0
    )
    resolution = sum(item.status in RESOLVED for item in hypotheses) / len(hypotheses) if hypotheses else 0.0
    falsification_coverage = len(attacked & {item.id for item in active}) / len(active) if active else 0.0
    current_dimensions = {
        "validation_fidelity": fidelity or 0.0,
        "hypothesis_resolution": resolution,
        "falsification_coverage": falsification_coverage,
        "representation_coverage": min(1.0, occupancy),
        "error_diversity": min(1.0, effective_rank / max(1, len(candidates))),
        "robustness": 1 / (1 + best.score_variance) if best is not None else 0.0,
        "dgp_understanding": dgp_understanding,
    }
    # No default vector. A state with no supplied target is *missing*, and a missing state must not
    # be reported as a gap of zero: that is indistinguishable from a state in perfect health, and it
    # is how seven hand-written constants stood in for a world model for as long as they did
    # (`docs/v050_course_correction.md` §1.2). Until an independently coded world model supplies
    # targets (`docs/world_model/coding_rules.md` §7 forbids wiring the single-coder fit in as a
    # default), the honest report is that every dimension is unset.
    targets = dict(preferred_targets or {})
    unknown = unknown_dimensions(targets)
    if unknown:
        raise ValueError(f"preferred-state targets name dimensions the loop cannot compute: {', '.join(unknown)}")
    weights = {name: float((preferred_weights or {}).get(name, 1.0)) for name in targets}
    gaps = {name: max(0.0, target - current_dimensions[name]) for name, target in targets.items()}
    weight_total = sum(weights.values())
    total_gap = sum(weights[name] * gaps[name] for name in gaps) / weight_total if weight_total else None
    missing = tuple(name for name in MEASURED_DIMENSIONS if name not in targets)
    evidence_ids = sorted(
        {identifier for world in worlds for identifier in world.evidence_ids}
        | {identifier for item in hypotheses for identifier in [*item.evidence_for, *item.evidence_against]}
    )
    return ResearchStateSnapshot(
        run_id=state.run_id,
        validation_fidelity=fidelity,
        validation_uncertainty=posterior_entropy(worlds, normalized=True),
        active_hypotheses=len(active),
        resolved_hypotheses=sum(item.status in RESOLVED for item in hypotheses),
        hypothesis_entropy_bits=entropy,
        hypothesis_coverage=len(covered_types) / len(HypothesisType),
        falsification_coverage=falsification_coverage,
        qd_occupancy=min(1.0, occupancy),
        oof_effective_rank=effective_rank,
        best_score_variance=best.score_variance if best is not None else None,
        expected_hidden_score=best.expected_hidden_score if best is not None else None,
        expected_hidden_interval=(
            (best.expected_hidden_score - 1.96 * spread, best.expected_hidden_score + 1.96 * spread)
            if best is not None
            else None
        ),
        hypothesis_calibration_brier=calibration.brier_score if calibration else None,
        preferred_state_gaps=gaps,
        preferred_state_total_gap=total_gap,
        preferred_state_missing=list(missing),
        unmeasured_states=[SPECIFICATION_STATES[key] for key in UNMEASURED_STATES],
        dgp_understanding=dgp_understanding,
        evidence_ids=evidence_ids,
    )


def _binary_entropy(probability: float) -> float:
    if probability <= 0 or probability >= 1:
        return 0.0
    return -probability * math.log2(probability) - (1 - probability) * math.log2(1 - probability)
