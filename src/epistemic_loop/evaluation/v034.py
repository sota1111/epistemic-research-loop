"""Outcome-only B/B+/C locks, decision audit, and sealed statistics for v0.3.4."""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from statistics import fmean, median

from epistemic_loop.evaluation.v032 import SystemArm

MINIMUM_MEANINGFUL_AUC_GAIN = 0.001


class V034Status(StrEnum):
    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"
    UNMEASURED = "unmeasured"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class V034ArmCapabilities:
    performance_archive: bool = True
    semantic_descriptor: bool = True
    implementation_descriptor: bool = True
    oof_error_archive: bool = True
    predictive_slice_preregistration: bool = False
    predictive_diversity_debt: bool = False
    standalone_ensemble_eligibility_split: bool = False
    hypothesis_registry: bool = False
    competing_hypotheses: bool = False
    structure_maturation: bool = False
    null_skeptic_fork: bool = False
    validation_debt: bool = False
    falsification: bool = False
    belief_update: bool = False
    evsi_or_discrimination_value: bool = False

    @classmethod
    def for_arm(cls, arm: SystemArm) -> V034ArmCapabilities:
        predictive = arm in {SystemArm.B_PLUS, SystemArm.C}
        epistemic = arm is SystemArm.C
        return cls(
            predictive_slice_preregistration=predictive,
            predictive_diversity_debt=predictive,
            standalone_ensemble_eligibility_split=predictive,
            hypothesis_registry=epistemic,
            competing_hypotheses=epistemic,
            structure_maturation=epistemic,
            null_skeptic_fork=epistemic,
            validation_debt=epistemic,
            falsification=epistemic,
            belief_update=epistemic,
            evsi_or_discrimination_value=epistemic,
        )

    @property
    def utility_terms(self) -> tuple[str, ...]:
        terms = ["expected_performance", "qd_contribution", "robustness"]
        if self.predictive_slice_preregistration:
            terms.extend(("expected_predictive_complementarity", "slice_coverage"))
        if self.hypothesis_registry:
            terms.extend(("evsi", "discrimination_value", "validation_debt_reduction"))
        return tuple(terms)


@dataclass(frozen=True)
class OutcomeOnlyResourcePolicy:
    cpu_limit: None = None
    memory_limit_gb: None = None
    gpu_limit: None = None
    thread_limit: None = None
    wall_clock_limit: None = None
    experiment_cost_penalty: bool = False
    use_resource_in_selection: bool = False
    use_resource_in_acceptance: bool = False
    heavy_execution_order: str = "sequential"

    def __post_init__(self) -> None:
        if self.experiment_cost_penalty or self.use_resource_in_selection or self.use_resource_in_acceptance:
            raise ValueError("v0.3.4 forbids resource cost in utility, selection, and acceptance")
        if self.heavy_execution_order not in {"sequential", "isolated"}:
            raise ValueError("heavy jobs may be sequential or otherwise isolated")


@dataclass(frozen=True)
class V034CandidateEligibilityEvidence:
    artifact_contract_passed: bool
    oof_honesty_passed: bool
    strict_forward_passed: bool
    leakage_check_passed: bool
    seed_stability_passed: bool
    primary_auc: float
    quality_floor: float
    nested_marginal_auc_gain: float
    positive_gain_horizons: int
    evaluated_horizons: int
    maximum_fold_weight: float
    maximum_allowed_fold_weight: float = 0.8


@dataclass(frozen=True)
class V034CandidateEligibility:
    standalone: bool
    ensemble: bool
    standalone_failures: tuple[str, ...]
    ensemble_failures: tuple[str, ...]

    @classmethod
    def assess(cls, evidence: V034CandidateEligibilityEvidence) -> V034CandidateEligibility:
        common = {
            "artifact_contract": evidence.artifact_contract_passed,
            "oof_honesty": evidence.oof_honesty_passed,
            "strict_forward": evidence.strict_forward_passed,
            "leakage": evidence.leakage_check_passed,
            "seed_stability": evidence.seed_stability_passed,
        }
        standalone = {**common, "quality_floor": evidence.primary_auc >= evidence.quality_floor}
        required_horizons = max(2, (evidence.evaluated_horizons + 1) // 2)
        ensemble = {
            **common,
            "positive_nested_auc_gain": evidence.nested_marginal_auc_gain > 0,
            "multi_horizon_gain": evidence.positive_gain_horizons >= required_horizons,
            "weight_stability": evidence.maximum_fold_weight <= evidence.maximum_allowed_fold_weight,
        }
        return cls(
            all(standalone.values()),
            all(ensemble.values()),
            tuple(name for name, passed in standalone.items() if not passed),
            tuple(name for name, passed in ensemble.items() if not passed),
        )


@dataclass(frozen=True)
class FinalSelectionCandidate:
    candidate_id: str
    member_candidate_ids: tuple[str, ...]
    is_ensemble: bool
    nested_strict_forward_auc: float
    worst_horizon_auc: float
    seed_standard_deviation: float
    standalone_eligible: bool
    ensemble_eligible: bool
    second_level_past_only: bool
    weight_rule_sha256: str


@dataclass(frozen=True)
class LockedFinalSelection:
    candidate_id: str
    selection_reason: str
    selection_rule_sha256: str


class V034FinalMetaSelector:
    """Select only on strict-forward outcome metrics; resource fields do not exist here."""

    def select(self, candidates: Sequence[FinalSelectionCandidate]) -> LockedFinalSelection:
        if not candidates:
            raise ValueError("final selection requires candidates")
        single_auc = {
            item.candidate_id: item.nested_strict_forward_auc for item in candidates if not item.is_ensemble
        }
        eligible: list[FinalSelectionCandidate] = []
        for candidate in candidates:
            if candidate.is_ensemble:
                members_present = all(member in single_auc for member in candidate.member_candidate_ids)
                beats_members = members_present and candidate.nested_strict_forward_auc > max(
                    single_auc[member] for member in candidate.member_candidate_ids
                )
                if candidate.ensemble_eligible and candidate.second_level_past_only and beats_members:
                    eligible.append(candidate)
            elif candidate.standalone_eligible:
                eligible.append(candidate)
        if not eligible:
            raise ValueError("no candidate passed standalone or ensemble eligibility")
        selected = max(
            eligible,
            key=lambda item: (
                item.nested_strict_forward_auc,
                item.worst_horizon_auc,
                -item.seed_standard_deviation,
                item.candidate_id,
            ),
        )
        stable = {
            "primary": "nested_strict_forward_auc",
            "secondary": "worst_horizon_auc",
            "tertiary": "seed_stability",
            "tie_break": "candidate_id",
            "candidate_id": selected.candidate_id,
            "weight_rule_sha256": selected.weight_rule_sha256,
        }
        return LockedFinalSelection(
            selected.candidate_id,
            "highest nested strict-forward AUC after eligibility; worst horizon and seed stability break ties",
            _stable_hash(stable),
        )


@dataclass(frozen=True)
class FinalRetrainLock:
    candidate_id: str
    pipeline_source_sha256: str
    feature_manifest_sha256: str
    hyperparameters_sha256: str
    ensemble_weights_sha256: str
    full_train_rows: int
    expected_test_rows: int
    deterministic: bool
    sealed_dependent_changes: bool
    lock_sha256: str

    @classmethod
    def freeze(
        cls,
        *,
        candidate_id: str,
        pipeline_source_sha256: str,
        feature_manifest_sha256: str,
        hyperparameters_sha256: str,
        ensemble_weights_sha256: str,
        full_train_rows: int = 590_540,
        expected_test_rows: int = 506_691,
        deterministic: bool = True,
        sealed_dependent_changes: bool = False,
    ) -> FinalRetrainLock:
        if full_train_rows != 590_540 or expected_test_rows != 506_691:
            raise ValueError("IEEE-CIS final retrain must use all train rows and predict all test rows")
        if not deterministic or sealed_dependent_changes:
            raise ValueError("final retraining must be deterministic and cannot depend on sealed outcomes")
        stable = {
            "candidate_id": candidate_id,
            "pipeline_source_sha256": pipeline_source_sha256,
            "feature_manifest_sha256": feature_manifest_sha256,
            "hyperparameters_sha256": hyperparameters_sha256,
            "ensemble_weights_sha256": ensemble_weights_sha256,
            "full_train_rows": full_train_rows,
            "expected_test_rows": expected_test_rows,
            "deterministic": deterministic,
            "sealed_dependent_changes": sealed_dependent_changes,
        }
        return cls(
            candidate_id,
            pipeline_source_sha256,
            feature_manifest_sha256,
            hyperparameters_sha256,
            ensemble_weights_sha256,
            full_train_rows,
            expected_test_rows,
            deterministic,
            sealed_dependent_changes,
            _stable_hash(stable),
        )

    def verify(self) -> bool:
        stable = asdict(self)
        actual = str(stable.pop("lock_sha256"))
        return _stable_hash(stable) == actual


class DecisionChoice(StrEnum):
    PARENT = "parent"
    CHALLENGER = "challenger"


@dataclass(frozen=True)
class DecisionLock:
    decision_id: str
    run_id: str
    agent_id: str
    cycle: int
    parent_id: str
    challenger_id: str
    local_parent_auc: float
    local_challenger_auc: float
    local_selected: DecisionChoice
    minimum_gain: float
    stability_condition: str
    rejection_condition: str
    parent_prediction_sha256: str
    challenger_prediction_sha256: str
    lock_sha256: str

    @classmethod
    def freeze(
        cls,
        *,
        decision_id: str,
        run_id: str,
        agent_id: str,
        cycle: int,
        parent_id: str,
        challenger_id: str,
        local_parent_auc: float,
        local_challenger_auc: float,
        local_selected: DecisionChoice,
        minimum_gain: float,
        stability_condition: str,
        rejection_condition: str,
        parent_prediction_sha256: str,
        challenger_prediction_sha256: str,
    ) -> DecisionLock:
        if cycle not in {1, 2, 3}:
            raise ValueError("cycle must be one of the three adaptive cycles")
        if parent_id == challenger_id:
            raise ValueError("parent and challenger must differ")
        if any(not math.isfinite(value) or not 0 <= value <= 1 for value in (local_parent_auc, local_challenger_auc)):
            raise ValueError("local decision AUC values must be finite and in [0, 1]")
        if not math.isfinite(minimum_gain):
            raise ValueError("minimum_gain must be finite")
        stable = {
            "decision_id": decision_id,
            "run_id": run_id,
            "agent_id": agent_id,
            "cycle": cycle,
            "parent_id": parent_id,
            "challenger_id": challenger_id,
            "local_parent_auc": local_parent_auc,
            "local_challenger_auc": local_challenger_auc,
            "local_selected": local_selected,
            "minimum_gain": minimum_gain,
            "stability_condition": stability_condition,
            "rejection_condition": rejection_condition,
            "parent_prediction_sha256": parent_prediction_sha256,
            "challenger_prediction_sha256": challenger_prediction_sha256,
        }
        return cls(
            decision_id,
            run_id,
            agent_id,
            cycle,
            parent_id,
            challenger_id,
            local_parent_auc,
            local_challenger_auc,
            local_selected,
            minimum_gain,
            stability_condition,
            rejection_condition,
            parent_prediction_sha256,
            challenger_prediction_sha256,
            _stable_hash(stable),
        )

    def verify(self) -> bool:
        stable = asdict(self)
        actual = str(stable.pop("lock_sha256"))
        return _stable_hash(stable) == actual


@dataclass(frozen=True)
class SealedDecisionOutcome:
    decision_id: str
    parent_auc: float
    challenger_auc: float


@dataclass(frozen=True)
class DecisionAuditDetail:
    decision_id: str
    local_selected: DecisionChoice
    sealed_best: DecisionChoice
    sign_correct: bool
    false_rejection: bool
    false_adoption: bool
    selection_regret: float


@dataclass(frozen=True)
class DecisionQualityAudit:
    evaluated_decisions: int
    decision_sign_accuracy: float
    false_rejection_rate: float
    false_adoption_rate: float
    mean_selection_regret: float
    total_selection_regret: float
    details: tuple[DecisionAuditDetail, ...]

    @classmethod
    def assess(
        cls,
        locks: Sequence[DecisionLock],
        outcomes: Sequence[SealedDecisionOutcome],
    ) -> DecisionQualityAudit:
        if not locks:
            raise ValueError("decision audit requires at least one locked decision")
        if any(not item.verify() for item in locks):
            raise ValueError("decision lock hash is invalid")
        if len({item.decision_id for item in locks}) != len(locks):
            raise ValueError("decision identifiers must be unique")
        outcome_by_id = {item.decision_id: item for item in outcomes}
        if len(outcome_by_id) != len(outcomes) or set(outcome_by_id) != {item.decision_id for item in locks}:
            raise ValueError("sealed outcomes must cover every decision exactly once")
        details: list[DecisionAuditDetail] = []
        for lock in locks:
            outcome = outcome_by_id[lock.decision_id]
            if any(
                not math.isfinite(value) or not 0 <= value <= 1
                for value in (outcome.parent_auc, outcome.challenger_auc)
            ):
                raise ValueError("sealed decision AUC values must be finite and in [0, 1]")
            sealed_best = (
                DecisionChoice.CHALLENGER if outcome.challenger_auc > outcome.parent_auc else DecisionChoice.PARENT
            )
            selected_auc = (
                outcome.challenger_auc if lock.local_selected is DecisionChoice.CHALLENGER else outcome.parent_auc
            )
            regret = max(outcome.parent_auc, outcome.challenger_auc) - selected_auc
            false_rejection = (
                lock.local_selected is DecisionChoice.PARENT and outcome.challenger_auc > outcome.parent_auc
            )
            false_adoption = (
                lock.local_selected is DecisionChoice.CHALLENGER and outcome.challenger_auc < outcome.parent_auc
            )
            details.append(
                DecisionAuditDetail(
                    lock.decision_id,
                    lock.local_selected,
                    sealed_best,
                    not false_rejection and not false_adoption,
                    false_rejection,
                    false_adoption,
                    regret,
                )
            )
        count = len(details)
        regrets = [item.selection_regret for item in details]
        return cls(
            count,
            sum(item.sign_correct for item in details) / count,
            sum(item.false_rejection for item in details) / count,
            sum(item.false_adoption for item in details) / count,
            fmean(regrets),
            sum(regrets),
            tuple(details),
        )


@dataclass(frozen=True)
class V034RunOutputLock:
    output_id: str
    run_id: str
    arm: SystemArm
    outer_seed: int
    candidate_id: str
    base_commit: str
    dataset_sha256: str
    fold_plan_sha256: str
    row_set_sha256: str
    candidate_commit: str
    feature_manifest_sha256: str
    selection_rule_sha256: str
    test_prediction_sha256: str
    submission_sha256: str
    sealed_prediction_sha256: str
    final_retrain_lock_sha256: str
    cycle_decision_lock_sha256: tuple[str, ...]
    local_auc: float
    lock_sha256: str

    @classmethod
    def freeze(
        cls,
        *,
        output_id: str,
        run_id: str,
        arm: SystemArm,
        outer_seed: int,
        candidate_id: str,
        base_commit: str,
        dataset_sha256: str,
        fold_plan_sha256: str,
        row_set_sha256: str,
        candidate_commit: str,
        feature_manifest_sha256: str,
        selection_rule_sha256: str,
        test_prediction_sha256: str,
        submission_sha256: str,
        sealed_prediction_sha256: str,
        final_retrain_lock_sha256: str,
        cycle_decision_lock_sha256: Sequence[str],
        local_auc: float,
    ) -> V034RunOutputLock:
        decision_hashes = tuple(cycle_decision_lock_sha256)
        if len(decision_hashes) != 9:
            raise ValueError("one run must lock 3 agents x 3 cycle decisions")
        if not math.isfinite(local_auc) or not 0 <= local_auc <= 1:
            raise ValueError("local AUC must be finite and in [0, 1]")
        stable = {
            "output_id": output_id,
            "run_id": run_id,
            "arm": arm,
            "outer_seed": outer_seed,
            "candidate_id": candidate_id,
            "base_commit": base_commit,
            "dataset_sha256": dataset_sha256,
            "fold_plan_sha256": fold_plan_sha256,
            "row_set_sha256": row_set_sha256,
            "candidate_commit": candidate_commit,
            "feature_manifest_sha256": feature_manifest_sha256,
            "selection_rule_sha256": selection_rule_sha256,
            "test_prediction_sha256": test_prediction_sha256,
            "submission_sha256": submission_sha256,
            "sealed_prediction_sha256": sealed_prediction_sha256,
            "final_retrain_lock_sha256": final_retrain_lock_sha256,
            "cycle_decision_lock_sha256": decision_hashes,
            "local_auc": local_auc,
        }
        return cls(
            output_id,
            run_id,
            arm,
            outer_seed,
            candidate_id,
            base_commit,
            dataset_sha256,
            fold_plan_sha256,
            row_set_sha256,
            candidate_commit,
            feature_manifest_sha256,
            selection_rule_sha256,
            test_prediction_sha256,
            submission_sha256,
            sealed_prediction_sha256,
            final_retrain_lock_sha256,
            decision_hashes,
            local_auc,
            _stable_hash(stable),
        )

    def verify(self) -> bool:
        stable = asdict(self)
        actual = str(stable.pop("lock_sha256"))
        return _stable_hash(stable) == actual


@dataclass(frozen=True)
class ArmPolicyHash:
    arm: SystemArm
    sha256: str


@dataclass(frozen=True)
class V034SealedOutcomeBatch:
    outputs: tuple[V034RunOutputLock, ...]
    arm_policy_hashes: tuple[ArmPolicyHash, ...]
    prompt_sha256: str
    acceptance_sha256: str
    validation_constraint_sha256: str
    plan_sha256: str
    hidden_evaluator_sha256: str
    batch_sha256: str
    outputs_per_arm: int = 12
    all_outputs_locked: bool = True
    private_evaluation_only_after_lock: bool = True
    resource_metrics_used: bool = False

    @classmethod
    def freeze(
        cls,
        outputs: Sequence[V034RunOutputLock],
        *,
        arm_policy_hashes: Sequence[ArmPolicyHash],
        prompt_sha256: str,
        acceptance_sha256: str,
        validation_constraint_sha256: str,
        plan_sha256: str,
        hidden_evaluator_sha256: str,
        outputs_per_arm: int = 12,
    ) -> V034SealedOutcomeBatch:
        _validate_outcome_design(outputs, outputs_per_arm=outputs_per_arm)
        policies = tuple(sorted(arm_policy_hashes, key=lambda item: item.arm.value))
        if {item.arm for item in policies} != {SystemArm.B, SystemArm.B_PLUS, SystemArm.C}:
            raise ValueError("one frozen policy hash is required for each B/B+/C arm")
        if len({item.arm for item in policies}) != len(policies):
            raise ValueError("arm policy hashes must be unique")
        if len({item.sha256 for item in policies}) != len(policies):
            raise ValueError("B/B+/C policy hashes must differ")
        stable = {
            "outputs": [asdict(item) for item in outputs],
            "arm_policy_hashes": [asdict(item) for item in policies],
            "prompt_sha256": prompt_sha256,
            "acceptance_sha256": acceptance_sha256,
            "validation_constraint_sha256": validation_constraint_sha256,
            "plan_sha256": plan_sha256,
            "hidden_evaluator_sha256": hidden_evaluator_sha256,
            "outputs_per_arm": outputs_per_arm,
            "all_outputs_locked": True,
            "private_evaluation_only_after_lock": True,
            "resource_metrics_used": False,
        }
        return cls(
            tuple(outputs),
            policies,
            prompt_sha256,
            acceptance_sha256,
            validation_constraint_sha256,
            plan_sha256,
            hidden_evaluator_sha256,
            _stable_hash(stable),
            outputs_per_arm,
        )

    def verify(self) -> bool:
        rebuilt = self.freeze(
            self.outputs,
            arm_policy_hashes=self.arm_policy_hashes,
            prompt_sha256=self.prompt_sha256,
            acceptance_sha256=self.acceptance_sha256,
            validation_constraint_sha256=self.validation_constraint_sha256,
            plan_sha256=self.plan_sha256,
            hidden_evaluator_sha256=self.hidden_evaluator_sha256,
            outputs_per_arm=self.outputs_per_arm,
        )
        return rebuilt.batch_sha256 == self.batch_sha256


def _validate_outcome_design(outputs: Sequence[V034RunOutputLock], *, outputs_per_arm: int) -> None:
    if any(not item.verify() for item in outputs):
        raise ValueError("one or more output locks are invalid")
    arms = (SystemArm.B, SystemArm.B_PLUS, SystemArm.C)
    counts = Counter(item.arm for item in outputs)
    if set(counts) != set(arms) or any(counts[arm] != outputs_per_arm for arm in arms):
        raise ValueError(f"sealed batch requires exactly {outputs_per_arm} outputs per B/B+/C arm")
    if len({item.output_id for item in outputs}) != len(outputs):
        raise ValueError("output_id values must be unique")
    seed_sets = {arm: {item.outer_seed for item in outputs if item.arm is arm} for arm in arms}
    if (
        len({frozenset(values) for values in seed_sets.values()}) != 1
        or any(len(values) != outputs_per_arm for values in seed_sets.values())
    ):
        raise ValueError("all arms must use the same outer seed set")
    for field in ("base_commit", "dataset_sha256", "fold_plan_sha256", "row_set_sha256"):
        if len({getattr(item, field) for item in outputs}) != 1:
            raise ValueError(f"all outputs must use an identical {field}")


@dataclass(frozen=True)
class LockedOutcomeScore:
    output_id: str
    private_auc: float
    sealed_future_auc: float
    run_selection_regret: float
    nested_ensemble_gain: float
    hidden_ensemble_gain: float
    validated_structures: int
    false_structure_promotions: int
    global_validation_constraints_discovered: int
    independent_replications: int
    redundant_duplications: int
    artifact_completed: bool
    valid_submission: bool


@dataclass(frozen=True)
class PairwiseOutcomeStatistics:
    treatment: SystemArm
    comparator: SystemArm
    mean_delta: float
    median_delta: float
    bootstrap_ci_95: tuple[float, float]
    positive_delta_rate: float
    sign_test_p_value: float
    worst_seed_delta: float
    best_seed_delta: float
    paired_deltas: tuple[float, ...]


@dataclass(frozen=True)
class ArmOutcomeSummary:
    arm: SystemArm
    mean_local_auc: float
    mean_private_auc: float
    median_private_auc: float
    mean_sealed_future_auc: float
    private_win_rate: float
    cv_to_sealed_spearman: float | None
    cv_to_private_spearman: float | None
    mean_selection_regret: float
    mean_nested_ensemble_gain: float
    mean_hidden_ensemble_gain: float
    artifact_completion_rate: float
    valid_submission_rate: float
    validated_structures: int
    false_structure_promotions: int
    false_structure_promotion_rate: float
    global_validation_constraints_discovered: int
    independent_replications: int
    redundant_duplication_rate: float


@dataclass(frozen=True)
class ArmDecisionAuditSummary:
    arm: SystemArm
    evaluated_decisions: int
    decision_sign_accuracy: float
    false_rejection_rate: float
    false_adoption_rate: float
    mean_selection_regret: float


@dataclass(frozen=True)
class V034OutcomeAnalysis:
    paired_seeds: int
    arm_summaries: tuple[ArmOutcomeSummary, ...]
    decision_audit_summaries: tuple[ArmDecisionAuditSummary, ...]
    c_vs_b: PairwiseOutcomeStatistics
    c_vs_b_plus: PairwiseOutcomeStatistics
    b_plus_vs_b: PairwiseOutcomeStatistics
    hidden_batch_complete: bool = True
    resource_metrics_used: bool = False


def evaluate_outcome_batch(
    batch: V034SealedOutcomeBatch,
    scores: Sequence[LockedOutcomeScore],
    decision_audits: Mapping[str, DecisionQualityAudit],
    *,
    bootstrap_iterations: int = 10_000,
    bootstrap_seed: int = 34,
) -> V034OutcomeAnalysis:
    """Unblind one complete batch; partial scores and resource-weighted outcomes are rejected."""
    if not batch.verify():
        raise ValueError("sealed outcome batch hash is invalid")
    score_by_id = {item.output_id: item for item in scores}
    if len(score_by_id) != len(scores) or set(score_by_id) != {item.output_id for item in batch.outputs}:
        raise ValueError("hidden scores must cover all locked outputs exactly once")
    if set(decision_audits) != {item.output_id for item in batch.outputs}:
        raise ValueError("decision audits must cover all locked outputs exactly once")
    if any(item.evaluated_decisions != 9 for item in decision_audits.values()):
        raise ValueError("each run must audit all 3 agents x 3 cycle decisions")
    for score in scores:
        values = (score.private_auc, score.sealed_future_auc, score.run_selection_regret)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("outcome scores must be finite")
        if not 0 <= score.private_auc <= 1 or not 0 <= score.sealed_future_auc <= 1:
            raise ValueError("AUC values must be in [0, 1]")
        if score.run_selection_regret < 0:
            raise ValueError("selection regret cannot be negative")
        counts = (
            score.validated_structures,
            score.false_structure_promotions,
            score.global_validation_constraints_discovered,
            score.independent_replications,
            score.redundant_duplications,
        )
        if any(value < 0 for value in counts):
            raise ValueError("outcome counts cannot be negative")

    outputs = {(item.arm, item.outer_seed): item for item in batch.outputs}
    seeds = sorted({item.outer_seed for item in batch.outputs})
    private = {
        (arm, seed): score_by_id[outputs[arm, seed].output_id].private_auc
        for arm in (SystemArm.B, SystemArm.B_PLUS, SystemArm.C)
        for seed in seeds
    }
    pairwise = {
        (SystemArm.C, SystemArm.B): _paired_statistics(
            SystemArm.C,
            SystemArm.B,
            [private[SystemArm.C, seed] - private[SystemArm.B, seed] for seed in seeds],
            bootstrap_iterations,
            bootstrap_seed,
        ),
        (SystemArm.C, SystemArm.B_PLUS): _paired_statistics(
            SystemArm.C,
            SystemArm.B_PLUS,
            [private[SystemArm.C, seed] - private[SystemArm.B_PLUS, seed] for seed in seeds],
            bootstrap_iterations,
            bootstrap_seed + 1,
        ),
        (SystemArm.B_PLUS, SystemArm.B): _paired_statistics(
            SystemArm.B_PLUS,
            SystemArm.B,
            [private[SystemArm.B_PLUS, seed] - private[SystemArm.B, seed] for seed in seeds],
            bootstrap_iterations,
            bootstrap_seed + 2,
        ),
    }
    summaries: list[ArmOutcomeSummary] = []
    decision_summaries: list[ArmDecisionAuditSummary] = []
    for arm in (SystemArm.B, SystemArm.B_PLUS, SystemArm.C):
        arm_outputs = [item for item in batch.outputs if item.arm is arm]
        arm_scores = [score_by_id[item.output_id] for item in arm_outputs]
        private_values = [item.private_auc for item in arm_scores]
        sealed_values = [item.sealed_future_auc for item in arm_scores]
        local_values = [item.local_auc for item in arm_outputs]
        validated = sum(item.validated_structures for item in arm_scores)
        false_promotions = sum(item.false_structure_promotions for item in arm_scores)
        independent_replications = sum(item.independent_replications for item in arm_scores)
        redundant_duplications = sum(item.redundant_duplications for item in arm_scores)
        wins = sum(
            private[arm, seed] == max(private[candidate_arm, seed] for candidate_arm in SystemArm)
            for seed in seeds
        )
        summaries.append(
            ArmOutcomeSummary(
                arm,
                fmean(local_values),
                fmean(private_values),
                median(private_values),
                fmean(sealed_values),
                wins / len(seeds),
                _spearman(local_values, sealed_values),
                _spearman(local_values, private_values),
                fmean(item.run_selection_regret for item in arm_scores),
                fmean(item.nested_ensemble_gain for item in arm_scores),
                fmean(item.hidden_ensemble_gain for item in arm_scores),
                sum(item.artifact_completed for item in arm_scores) / len(arm_scores),
                sum(item.valid_submission for item in arm_scores) / len(arm_scores),
                validated,
                false_promotions,
                false_promotions / max(validated + false_promotions, 1),
                sum(item.global_validation_constraints_discovered for item in arm_scores),
                independent_replications,
                redundant_duplications / max(independent_replications + redundant_duplications, 1),
            )
        )
        arm_audits = [decision_audits[item.output_id] for item in arm_outputs]
        total_decisions = sum(item.evaluated_decisions for item in arm_audits)
        decision_summaries.append(
            ArmDecisionAuditSummary(
                arm,
                total_decisions,
                sum(item.decision_sign_accuracy * item.evaluated_decisions for item in arm_audits) / total_decisions,
                sum(item.false_rejection_rate * item.evaluated_decisions for item in arm_audits) / total_decisions,
                sum(item.false_adoption_rate * item.evaluated_decisions for item in arm_audits) / total_decisions,
                sum(item.total_selection_regret for item in arm_audits) / total_decisions,
            )
        )
    return V034OutcomeAnalysis(
        len(seeds),
        tuple(summaries),
        tuple(decision_summaries),
        pairwise[SystemArm.C, SystemArm.B],
        pairwise[SystemArm.C, SystemArm.B_PLUS],
        pairwise[SystemArm.B_PLUS, SystemArm.B],
    )


@dataclass(frozen=True)
class V034Acceptance:
    control_plane: V034Status
    artifact_reliability: V034Status
    global_validation_constraint: V034Status
    full_common_crossfit: V034Status
    decision_audit: V034Status
    semantic_diversity: V034Status
    quality_predictive_diversity: V034Status
    structure_falsification: V034Status
    true_structure_discovery: V034Status
    final_hidden_outcome: V034Status
    unrestricted_outcome_advantage_over_b: V034Status
    unrestricted_outcome_advantage_over_b_plus: V034Status

    @classmethod
    def preflight(cls) -> V034Acceptance:
        return cls(
            V034Status.PASS,
            V034Status.PASS,
            V034Status.PASS,
            V034Status.PASS,
            V034Status.PASS,
            V034Status.UNMEASURED,
            V034Status.UNMEASURED,
            V034Status.UNMEASURED,
            V034Status.UNMEASURED,
            V034Status.UNMEASURED,
            V034Status.INCONCLUSIVE,
            V034Status.INCONCLUSIVE,
        )

    @classmethod
    def from_outcomes(
        cls,
        analysis: V034OutcomeAnalysis,
        *,
        semantic_diversity: V034Status,
        quality_predictive_diversity: V034Status,
        structure_falsification: V034Status,
        true_structure_discovery: V034Status,
    ) -> V034Acceptance:
        summaries = {item.arm: item for item in analysis.arm_summaries}
        c_regret = summaries[SystemArm.C].mean_selection_regret
        decision_audit_passed = all(item.evaluated_decisions == 108 for item in analysis.decision_audit_summaries)
        return cls(
            V034Status.PASS,
            (
                V034Status.PASS
                if all(item.artifact_completion_rate == 1 for item in summaries.values())
                else V034Status.FAIL
            ),
            V034Status.PASS,
            V034Status.PASS,
            V034Status.PASS if decision_audit_passed else V034Status.FAIL,
            semantic_diversity,
            quality_predictive_diversity,
            structure_falsification,
            true_structure_discovery,
            V034Status.PASS,
            _advantage_status(analysis.c_vs_b, c_regret, summaries[SystemArm.B].mean_selection_regret),
            _advantage_status(
                analysis.c_vs_b_plus,
                c_regret,
                summaries[SystemArm.B_PLUS].mean_selection_regret,
            ),
        )


class V034Conclusion(StrEnum):
    FULL_C_CAPABILITY = "full_c_capability"
    B_PLUS_SUFFICIENT = "b_plus_sufficient"
    STRONG_B_SUFFICIENT = "strong_b_sufficient"
    VALIDATION_BOTTLENECK = "validation_bottleneck"
    C_REJECTED = "c_rejected"
    INCONCLUSIVE = "inconclusive"


def classify_outcome_conclusion(
    analysis: V034OutcomeAnalysis,
    *,
    equivalence_tolerance: float = MINIMUM_MEANINGFUL_AUC_GAIN,
    low_rank_correlation: float = 0.3,
) -> V034Conclusion:
    summaries = {item.arm: item for item in analysis.arm_summaries}
    c = summaries[SystemArm.C]
    b_plus = summaries[SystemArm.B_PLUS]
    b = summaries[SystemArm.B]
    full_c = (
        analysis.c_vs_b_plus.median_delta >= MINIMUM_MEANINGFUL_AUC_GAIN
        and analysis.c_vs_b_plus.bootstrap_ci_95[0] > 0
        and analysis.c_vs_b_plus.positive_delta_rate > 0.5
        and c.mean_selection_regret < b_plus.mean_selection_regret
    )
    if full_c:
        return V034Conclusion.FULL_C_CAPABILITY
    local_prefers_predictive = max(c.mean_local_auc, b_plus.mean_local_auc) > b.mean_local_auc
    private_prefers_b = b.mean_private_auc > max(c.mean_private_auc, b_plus.mean_private_auc)
    correlations = [
        item.cv_to_private_spearman
        for item in analysis.arm_summaries
        if item.cv_to_private_spearman is not None
    ]
    if local_prefers_predictive and private_prefers_b and correlations and fmean(correlations) < low_rank_correlation:
        return V034Conclusion.VALIDATION_BOTTLENECK
    if (
        analysis.b_plus_vs_b.mean_delta >= equivalence_tolerance
        and abs(analysis.c_vs_b_plus.mean_delta) < equivalence_tolerance
    ):
        return V034Conclusion.B_PLUS_SUFFICIENT
    if all(
        abs(item.mean_delta) < equivalence_tolerance
        for item in (analysis.c_vs_b, analysis.c_vs_b_plus, analysis.b_plus_vs_b)
    ):
        return V034Conclusion.STRONG_B_SUFFICIENT
    if analysis.c_vs_b_plus.mean_delta < 0:
        return V034Conclusion.C_REJECTED
    return V034Conclusion.INCONCLUSIVE


def _advantage_status(
    statistics: PairwiseOutcomeStatistics,
    treatment_regret: float,
    comparator_regret: float,
) -> V034Status:
    passed = (
        statistics.median_delta >= MINIMUM_MEANINGFUL_AUC_GAIN
        and statistics.bootstrap_ci_95[0] > 0
        and statistics.positive_delta_rate > 0.5
        and treatment_regret < comparator_regret
    )
    return V034Status.PASS if passed else V034Status.FAIL


def _paired_statistics(
    treatment: SystemArm,
    comparator: SystemArm,
    deltas: Sequence[float],
    bootstrap_iterations: int,
    seed: int,
) -> PairwiseOutcomeStatistics:
    if not deltas or bootstrap_iterations < 100:
        raise ValueError("paired analysis requires deltas and at least 100 bootstrap iterations")
    generator = random.Random(seed)
    width = len(deltas)
    bootstrap = sorted(
        fmean(deltas[generator.randrange(width)] for _ in range(width)) for _ in range(bootstrap_iterations)
    )
    nonzero = [item for item in deltas if item != 0]
    positive = sum(item > 0 for item in nonzero)
    p_value = _two_sided_sign_test(positive, len(nonzero)) if nonzero else 1.0
    return PairwiseOutcomeStatistics(
        treatment,
        comparator,
        fmean(deltas),
        median(deltas),
        (_quantile(bootstrap, 0.025), _quantile(bootstrap, 0.975)),
        sum(item > 0 for item in deltas) / len(deltas),
        p_value,
        min(deltas),
        max(deltas),
        tuple(deltas),
    )


def _two_sided_sign_test(positive: int, total: int) -> float:
    tail = min(positive, total - positive)
    probability = sum(math.comb(total, value) for value in range(tail + 1)) / 2**total
    return float(min(1.0, 2 * probability))


def _spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_ranks = _ranks(left)
    right_ranks = _ranks(right)
    left_mean = fmean(left_ranks)
    right_mean = fmean(right_ranks)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left_ranks, right_ranks, strict=True))
    denominator = math.sqrt(
        sum((item - left_mean) ** 2 for item in left_ranks)
        * sum((item - right_mean) ** 2 for item in right_ranks)
    )
    return numerator / denominator if denominator else None


def _ranks(values: Sequence[float]) -> tuple[float, ...]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(ordered):
        end = position + 1
        while end < len(ordered) and ordered[end][1] == ordered[position][1]:
            end += 1
        rank = ((position + 1) + end) / 2
        for index, _ in ordered[position:end]:
            ranks[index] = rank
        position = end
    return tuple(ranks)


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("quantile requires values")
    if probability <= 0:
        return values[0]
    if probability >= 1:
        return values[-1]
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction


def _stable_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()
