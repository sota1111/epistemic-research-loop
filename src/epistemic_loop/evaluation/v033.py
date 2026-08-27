"""v0.3.3 contracts for incremental-value verification over strong QD.

The module intentionally does not provide an IEEE-CIS optimisation loop.  It
freezes the three research policies and separates evidence that was already
observed in v0.3.2 from the still-sealed B/B+/C comparison.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum

from epistemic_loop.evaluation.acceptance import AcceptanceStatus
from epistemic_loop.evaluation.v032 import SystemArm


class VerificationStatus(StrEnum):
    OPEN = "open"
    PARTIAL = "partial"
    PROVISIONAL_PASS = "provisional_pass"
    PASS = "pass"
    FAIL = "fail"
    UNMEASURED = "unmeasured"


@dataclass(frozen=True)
class HiddenEndpointBreakdown:
    candidate_level_transfer: VerificationStatus
    w02_standalone_transfer: VerificationStatus
    ensemble_transfer: VerificationStatus
    system_c_vs_b: VerificationStatus = VerificationStatus.UNMEASURED
    system_c_vs_b_plus: VerificationStatus = VerificationStatus.UNMEASURED


@dataclass(frozen=True)
class ValidationFidelityDebt:
    candidate_ranking: VerificationStatus
    ensemble_transfer: VerificationStatus
    private_rank_calibration: VerificationStatus
    required_selector_evidence: tuple[str, ...] = (
        "horizon_rank_stability",
        "leave_one_horizon_out_selection_regret",
        "seed_stability",
        "slice_complementarity",
        "ensemble_weight_stability",
    )


@dataclass(frozen=True)
class ArchiveBreadthAssessment:
    effective_rank: float
    pilot_threshold: float
    status: VerificationStatus
    blocking: bool = False
    purpose: str = "diagnostic_only"

    @classmethod
    def assess(cls, effective_rank: float, *, pilot_threshold: float = 1.2) -> ArchiveBreadthAssessment:
        status = VerificationStatus.PASS if effective_rank >= pilot_threshold else VerificationStatus.PARTIAL
        return cls(effective_rank, pilot_threshold, status)


class EffectSign(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class ComponentEffectPrediction:
    component: str
    expected_sign: EffectSign
    minimum_effect: float
    maximum_effect: float
    predicted_importance_rank: int
    strongest_slices: tuple[str, ...]
    transfers_across_learners: bool

    def __post_init__(self) -> None:
        if self.minimum_effect > self.maximum_effect:
            raise ValueError("minimum_effect must not exceed maximum_effect")
        if self.predicted_importance_rank < 1:
            raise ValueError("predicted_importance_rank must be positive")


@dataclass(frozen=True)
class ComponentEffectObservation:
    component: str
    effect: float
    observed_importance_rank: int
    strongest_slices: tuple[str, ...]
    transferred_across_learners: bool


@dataclass(frozen=True)
class MechanismCalibration:
    status: VerificationStatus
    sign_accuracy: float
    range_accuracy: float
    rank_accuracy: float
    slice_accuracy: float
    learner_transfer_accuracy: float
    mismatches: tuple[str, ...]

    @classmethod
    def assess(
        cls,
        predictions: Sequence[ComponentEffectPrediction],
        observations: Sequence[ComponentEffectObservation],
    ) -> MechanismCalibration:
        if not predictions:
            return cls(VerificationStatus.UNMEASURED, 0.0, 0.0, 0.0, 0.0, 0.0, ("no_predictions",))
        observed = {item.component: item for item in observations}
        if set(observed) != {item.component for item in predictions}:
            raise ValueError("predictions and observations must cover identical components")
        sign_hits = 0
        range_hits = 0
        rank_hits = 0
        slice_hits = 0
        transfer_hits = 0
        mismatches: list[str] = []
        for prediction in predictions:
            observation = observed[prediction.component]
            actual_sign = _effect_sign(observation.effect)
            checks = {
                "sign": actual_sign is prediction.expected_sign,
                "range": prediction.minimum_effect <= observation.effect <= prediction.maximum_effect,
                "rank": prediction.predicted_importance_rank == observation.observed_importance_rank,
                "slice": bool(set(prediction.strongest_slices) & set(observation.strongest_slices)),
                "learner_transfer": (prediction.transfers_across_learners == observation.transferred_across_learners),
            }
            sign_hits += checks["sign"]
            range_hits += checks["range"]
            rank_hits += checks["rank"]
            slice_hits += checks["slice"]
            transfer_hits += checks["learner_transfer"]
            mismatches.extend(f"{prediction.component}:{name}" for name, passed in checks.items() if not passed)
        count = len(predictions)
        accuracy = (sign_hits + range_hits + rank_hits + slice_hits + transfer_hits) / (5 * count)
        status = VerificationStatus.PASS if accuracy == 1 else VerificationStatus.PARTIAL
        return cls(
            status,
            sign_hits / count,
            range_hits / count,
            rank_hits / count,
            slice_hits / count,
            transfer_hits / count,
            tuple(mismatches),
        )


def _effect_sign(effect: float, *, epsilon: float = 1e-12) -> EffectSign:
    if effect > epsilon:
        return EffectSign.POSITIVE
    if effect < -epsilon:
        return EffectSign.NEGATIVE
    return EffectSign.NEUTRAL


@dataclass(frozen=True)
class V033Acceptance:
    locked_portfolio_gain_vs_previous_archive: AcceptanceStatus
    w02_standalone_hidden_transfer: AcceptanceStatus
    ensemble_hidden_transfer: AcceptanceStatus
    local_candidate_ranking_fidelity: AcceptanceStatus
    quality_conditioned_predictive_diversity: AcceptanceStatus
    archive_wide_predictive_breadth: AcceptanceStatus
    archive_wide_breadth_blocking: bool
    mechanism_attribution: AcceptanceStatus
    structural_falsification: AcceptanceStatus
    true_structure_discovery: AcceptanceStatus
    system_c_vs_b: AcceptanceStatus
    system_c_vs_b_plus: AcceptanceStatus

    @classmethod
    def from_v032_observations(cls) -> V033Acceptance:
        """Record the frozen v0.3.2 result without widening its claim."""

        return cls(
            locked_portfolio_gain_vs_previous_archive=AcceptanceStatus.PASS,
            w02_standalone_hidden_transfer=AcceptanceStatus.FAIL,
            ensemble_hidden_transfer=AcceptanceStatus.PASS,
            local_candidate_ranking_fidelity=AcceptanceStatus.PARTIAL_PASS,
            quality_conditioned_predictive_diversity=AcceptanceStatus.PASS,
            archive_wide_predictive_breadth=AcceptanceStatus.PARTIAL_PASS,
            archive_wide_breadth_blocking=False,
            mechanism_attribution=AcceptanceStatus.PARTIAL_PASS,
            structural_falsification=AcceptanceStatus.PASS,
            true_structure_discovery=AcceptanceStatus.PARTIAL_PASS,
            system_c_vs_b=AcceptanceStatus.UNMEASURED,
            system_c_vs_b_plus=AcceptanceStatus.UNMEASURED,
        )


@dataclass(frozen=True)
class AblationOutputLock:
    output_id: str
    arm: SystemArm
    seed: int
    candidate_commit: str
    feature_manifest_sha256: str
    fold_plan_sha256: str
    selection_rule_sha256: str
    test_prediction_sha256: str
    submission_sha256: str


@dataclass(frozen=True)
class SealedAblationBatch:
    outputs: tuple[AblationOutputLock, ...]
    policy_sha256: str
    prompt_sha256: str
    budget_sha256: str
    observed_resource_ledger_sha256: str
    acceptance_sha256: str
    batch_sha256: str
    outputs_per_arm: int = 12
    private_evaluation_only_after_lock: bool = True
    interim_private_scores_forbidden: bool = True

    @classmethod
    def freeze(
        cls,
        outputs: Sequence[AblationOutputLock],
        *,
        policy_sha256: str,
        prompt_sha256: str,
        budget_sha256: str,
        observed_resource_ledger_sha256: str,
        acceptance_sha256: str,
        realized_budget_match_verified: bool,
        outputs_per_arm: int = 12,
    ) -> SealedAblationBatch:
        if not realized_budget_match_verified:
            raise ValueError("sealed Private batch requires verified realized budget matching")
        _validate_output_design(outputs, outputs_per_arm=outputs_per_arm)
        stable = {
            "outputs": [asdict(item) for item in outputs],
            "policy_sha256": policy_sha256,
            "prompt_sha256": prompt_sha256,
            "budget_sha256": budget_sha256,
            "observed_resource_ledger_sha256": observed_resource_ledger_sha256,
            "acceptance_sha256": acceptance_sha256,
            "realized_budget_match_verified": True,
            "outputs_per_arm": outputs_per_arm,
            "private_evaluation_only_after_lock": True,
            "interim_private_scores_forbidden": True,
        }
        digest = hashlib.sha256(
            json.dumps(stable, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        return cls(
            tuple(outputs),
            policy_sha256,
            prompt_sha256,
            budget_sha256,
            observed_resource_ledger_sha256,
            acceptance_sha256,
            digest,
            outputs_per_arm,
        )

    def verify(self) -> bool:
        rebuilt = self.freeze(
            self.outputs,
            policy_sha256=self.policy_sha256,
            prompt_sha256=self.prompt_sha256,
            budget_sha256=self.budget_sha256,
            observed_resource_ledger_sha256=self.observed_resource_ledger_sha256,
            acceptance_sha256=self.acceptance_sha256,
            realized_budget_match_verified=True,
            outputs_per_arm=self.outputs_per_arm,
        )
        return rebuilt.batch_sha256 == self.batch_sha256


def _validate_output_design(outputs: Sequence[AblationOutputLock], *, outputs_per_arm: int) -> None:
    expected = {SystemArm.B, SystemArm.B_PLUS, SystemArm.C}
    counts = Counter(item.arm for item in outputs)
    if set(counts) != expected or any(counts[arm] != outputs_per_arm for arm in expected):
        raise ValueError(f"sealed batch requires exactly {outputs_per_arm} outputs per B/B+/C arm")
    identifiers = [item.output_id for item in outputs]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("output_id values must be unique")
    seed_sets = {arm: {item.seed for item in outputs if item.arm is arm} for arm in expected}
    if len(set(map(frozenset, seed_sets.values()))) != 1 or len(next(iter(seed_sets.values()))) != outputs_per_arm:
        raise ValueError("all arms must use the same unique seed set")


@dataclass(frozen=True)
class PrivateAblationResult:
    mean_private_auc: Mapping[SystemArm, float]
    private_auc_c_minus_b: float
    private_auc_c_minus_b_plus: float
    private_auc_b_plus_minus_b: float
    paired_seeds: int


def evaluate_sealed_private_batch(
    batch: SealedAblationBatch,
    scores: Mapping[str, float],
) -> PrivateAblationResult:
    """Evaluate one complete sealed batch; partial/interim score access is rejected."""

    expected_ids = {item.output_id for item in batch.outputs}
    if not batch.verify():
        raise ValueError("sealed batch hash is invalid")
    if set(scores) != expected_ids:
        raise ValueError("private scores must be supplied once for every locked output and no others")
    if any(not math.isfinite(score) or not 0 <= score <= 1 for score in scores.values()):
        raise ValueError("private AUC scores must be finite values in [0, 1]")
    by_arm_seed = {(item.arm, item.seed): scores[item.output_id] for item in batch.outputs}
    seeds = sorted({item.seed for item in batch.outputs})
    means = {
        arm: sum(by_arm_seed[arm, seed] for seed in seeds) / len(seeds)
        for arm in (SystemArm.B, SystemArm.B_PLUS, SystemArm.C)
    }
    return PrivateAblationResult(
        mean_private_auc=means,
        private_auc_c_minus_b=means[SystemArm.C] - means[SystemArm.B],
        private_auc_c_minus_b_plus=means[SystemArm.C] - means[SystemArm.B_PLUS],
        private_auc_b_plus_minus_b=means[SystemArm.B_PLUS] - means[SystemArm.B],
        paired_seeds=len(seeds),
    )


class PrivateResultUse(StrEnum):
    RESEARCH_CONCLUSION = "research_conclusion"
    FEATURE_TUNING = "feature_tuning"
    MODEL_TUNING = "model_tuning"
    ENSEMBLE_WEIGHT_TUNING = "ensemble_weight_tuning"
    CONFIRMATORY_EXTERNAL = "confirmatory_external"


def assert_private_result_use_allowed(purpose: PrivateResultUse) -> None:
    if purpose not in {PrivateResultUse.RESEARCH_CONCLUSION, PrivateResultUse.CONFIRMATORY_EXTERNAL}:
        raise PermissionError("IEEE-CIS private results are frozen evaluation evidence, not a development signal")
