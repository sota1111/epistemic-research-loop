from __future__ import annotations

import hashlib
import itertools
import math
import random
from collections import Counter, defaultdict
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from statistics import fmean, pstdev
from typing import Any

from epistemic_loop.domain.enums import StructureClassification
from epistemic_loop.domain.models import FoldAssignment
from epistemic_loop.validation.splits import time_folds


@dataclass(frozen=True)
class UIDCandidate:
    name: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class UIDValidation:
    temporal_reappearance: bool
    feature_consistency: bool
    fraud_label_structure: bool
    beats_uid_free_generalization: bool
    reproduced_forward_folds: int
    fold_safe_aggregation_improves: bool
    frequency_artifact_rejected: bool

    @property
    def validated(self) -> bool:
        return all(
            (
                self.temporal_reappearance,
                self.feature_consistency,
                self.fraud_label_structure,
                self.beats_uid_free_generalization,
                self.reproduced_forward_folds >= 2,
                self.fold_safe_aggregation_improves,
                self.frequency_artifact_rejected,
            )
        )


@dataclass(frozen=True)
class IEEERunAcceptance:
    validated_behavioral_client_proxies: int
    forward_horizons: int
    fold_safe_uid_candidates: int
    known_new_client_slice: bool
    model_families: frozenset[str]
    oof_candidates: int
    ensemble_candidates: int
    locked_submissions: int

    @property
    def passed(self) -> bool:
        return (
            self.validated_behavioral_client_proxies >= 1
            and self.forward_horizons >= 3
            and self.fold_safe_uid_candidates >= 1
            and self.known_new_client_slice
            and len(self.model_families) >= 2
            and self.oof_candidates >= 3
            and self.ensemble_candidates >= 1
            and self.locked_submissions >= 1
        )

    @property
    def validated_uid_candidates(self) -> int:
        """Deprecated reporting alias; a UID is not itself a validated identity."""

        return self.validated_behavioral_client_proxies


UID_ABLATION_MODELS = (
    "M0_BASE",
    "M1_COMPONENTS",
    "M2_FREQUENCY",
    "M3_UID_MEMORY",
    "M4_LINK_SHUFFLED",
    "M5_MATCHED_NULL",
)


@dataclass(frozen=True)
class UIDNestedAblationEvidence:
    score_by_model: Mapping[str, float]
    uid_free_gain_blocks: tuple[float, ...]
    frequency_gain_blocks: tuple[float, ...]
    identity_gain_blocks: tuple[float, ...]
    linkage_gain_blocks: tuple[float, ...]
    matched_null_gains: tuple[float, ...]
    construct_validity_gains: tuple[float, ...]
    temporal_persistence_gains: tuple[float, ...]
    horizon_identity_gains: tuple[float, ...]
    seed_identity_gains: tuple[float, ...]
    known_identity_gain: float
    new_identity_gain: float
    matched_null_interactions: tuple[float, ...]
    fold_safe: bool
    decision_adopted: bool
    hypothesis_present: bool = True
    candidate_code_present: bool = True
    forward_candidate_executed: bool = True
    common_model_family: str = "shared_model"
    common_hyperparameters_ref: str = "shared_hyperparameters"
    common_forward_fold_ref: str = "shared_forward_folds"
    common_seeds: tuple[int, ...] = (42, 43, 44)
    common_resource_ref: str = "shared_resource_profile"

    def __post_init__(self) -> None:
        missing = set(UID_ABLATION_MODELS) - set(self.score_by_model)
        if missing:
            raise ValueError(f"nested UID ablation is missing candidates: {sorted(missing)}")
        if len(self.matched_null_gains) < 20:
            raise ValueError("behavioral client validation requires at least 20 matched-null gains")
        if len(self.matched_null_interactions) < 20:
            raise ValueError("known/new interaction requires at least 20 matched-null interactions")
        if len(self.horizon_identity_gains) < 3 or len(self.seed_identity_gains) < 3:
            raise ValueError("behavioral client validation requires at least three horizons and three seeds")
        if len(set(self.common_seeds)) < 3:
            raise ValueError("nested ablation requires one shared set of at least three seeds")
        common_refs = (
            self.common_model_family,
            self.common_hyperparameters_ref,
            self.common_forward_fold_ref,
            self.common_resource_ref,
        )
        if any(not item.strip() for item in common_refs):
            raise ValueError("nested ablation requires a common model, hyperparameters, folds and resource profile")
        block_fields = (
            self.uid_free_gain_blocks,
            self.frequency_gain_blocks,
            self.identity_gain_blocks,
            self.linkage_gain_blocks,
            self.construct_validity_gains,
            self.temporal_persistence_gains,
        )
        if any(not values for values in block_fields):
            raise ValueError("every nested-ablation and construct check requires paired blocks")

    @property
    def component_gain(self) -> float:
        return self.score_by_model["M1_COMPONENTS"] - self.score_by_model["M0_BASE"]

    @property
    def frequency_gain(self) -> float:
        return self.score_by_model["M2_FREQUENCY"] - self.score_by_model["M1_COMPONENTS"]

    @property
    def identity_gain(self) -> float:
        return self.score_by_model["M3_UID_MEMORY"] - self.score_by_model["M2_FREQUENCY"]

    @property
    def linkage_gain(self) -> float:
        return self.score_by_model["M3_UID_MEMORY"] - self.score_by_model["M4_LINK_SHUFFLED"]

    @property
    def known_new_interaction(self) -> float:
        return self.known_identity_gain - self.new_identity_gain


@dataclass(frozen=True)
class BehavioralClientProxyGateResult:
    gates: Mapping[str, bool]
    structural_validity_passed: bool
    predictive_improvement_passed: bool
    classification: StructureClassification
    acceptance_level: float
    diagnostics: Mapping[str, float]

    @property
    def passed(self) -> bool:
        return self.structural_validity_passed and self.predictive_improvement_passed


@dataclass(frozen=True)
class StructureValidatorControlReport:
    positive_control_acceptance_rate: float
    negative_control_rejection_rate: float
    false_structure_promotion_rate: float
    time_to_structure_validation_minutes: float
    validation_experiment_cost: float

    @property
    def passed(self) -> bool:
        return (
            self.positive_control_acceptance_rate >= 0.9
            and self.negative_control_rejection_rate >= 0.9
            and self.false_structure_promotion_rate <= 0.1
        )


def generate_uid_candidates(columns: Sequence[str], *, maximum: int = 64) -> tuple[UIDCandidate, ...]:
    """Generate client identities from all IEEE-CIS structural families present."""

    available = set(columns)
    family_order: tuple[tuple[str, ...], ...] = (
        tuple(item for item in ("card1", "card2", "card3", "card4", "card5", "card6") if item in available),
        tuple(item for item in ("addr1", "addr2") if item in available),
        tuple(item for item in ("P_emaildomain", "R_emaildomain") if item in available),
        tuple(item for item in ("DeviceType", "DeviceInfo") if item in available),
        tuple(item for item in ("D1", "D2", "D4", "D10", "D15") if item in available),
        tuple(item for item in ("reference_date", "TransactionDT") if item in available),
    )
    candidates: dict[tuple[str, ...], UIDCandidate] = {}
    for base in family_order[0] or ():
        singleton_key = (base,)
        candidates[singleton_key] = UIDCandidate("uid_" + "_".join(singleton_key), singleton_key)
    non_empty = [family for family in family_order if family]
    for width in range(2, min(5, len(non_empty)) + 1):
        for families in itertools.combinations(non_empty, width):
            for values in itertools.product(*families):
                combined_key = tuple(dict.fromkeys(values))
                candidates.setdefault(
                    combined_key,
                    UIDCandidate("uid_" + "_".join(combined_key), combined_key),
                )
                if len(candidates) >= maximum:
                    return tuple(candidates.values())
    return tuple(candidates.values())


def uid_value(row: Mapping[str, Any], candidate: UIDCandidate) -> str:
    canonical = "|".join("<NA>" if row.get(column) is None else str(row.get(column)) for column in candidate.columns)
    return hashlib.sha256(canonical.encode()).hexdigest()[:24]


def uid_competing_hypotheses() -> dict[str, str]:
    """Mandatory alternatives for a client-proxy structural claim."""

    return {
        "H_client": "the UID proxy represents persistent behavioral clients",
        "H_frequency": "gain comes from group size or observation frequency",
        "H_time": "the UID proxies registration time or a collection batch",
        "H_components": "raw UID component columns, not grouping, explain the gain",
        "H_linkage_noise": "arbitrary groups produce the same memory-feature gain",
        "H_leakage": "future or validation rows leak into the aggregate",
        "H_sparse_overfit": "rare-group fragmentation causes an unstable forward gain",
    }


def frequency_matched_null_assignments(
    uids: Sequence[Hashable],
    time_bins: Sequence[Hashable],
    missingness_buckets: Sequence[Hashable],
    *,
    seed: int,
    known_new_status: Sequence[Hashable] | None = None,
) -> list[Hashable]:
    """Break long-lived linkage while preserving frequency/time/missingness strata.

    Shuffling the existing labels, rather than drawing new group IDs, preserves
    each stratum's complete UID multiset and therefore its group-size histogram.
    """

    status = list(known_new_status) if known_new_status is not None else ["unspecified"] * len(uids)
    if not (len(uids) == len(time_bins) == len(missingness_buckets) == len(status)):
        raise ValueError("matched-null inputs must align")
    frequencies = Counter(uids)
    strata: dict[tuple[int, Hashable, Hashable, Hashable], list[int]] = defaultdict(list)
    for index, (uid, time_bin, missingness, client_status) in enumerate(
        zip(uids, time_bins, missingness_buckets, status, strict=True)
    ):
        strata[(_frequency_bucket(frequencies[uid]), time_bin, missingness, client_status)].append(index)
    output = list(uids)
    generator = random.Random(seed)
    for indices in strata.values():
        labels = [uids[index] for index in indices]
        generator.shuffle(labels)
        for index, label in zip(indices, labels, strict=True):
            output[index] = label
    return output


def linkage_shuffle_assignments(
    uids: Sequence[Hashable],
    time_bins: Sequence[Hashable],
    *,
    seed: int,
) -> list[Hashable]:
    return frequency_matched_null_assignments(uids, time_bins, ["all"] * len(uids), seed=seed)


def heldout_feature_consistency(
    groups: Sequence[Hashable],
    heldout_values: Sequence[Hashable],
) -> float:
    """Weighted within-group modal agreement for a UID-unused attribute."""

    if len(groups) != len(heldout_values) or not groups:
        raise ValueError("construct-validity inputs must be aligned and non-empty")
    values_by_group: dict[Hashable, Counter[Hashable]] = defaultdict(Counter)
    for group, value in zip(groups, heldout_values, strict=True):
        values_by_group[group][value] += 1
    correct = sum(max(counts.values()) for counts in values_by_group.values())
    return correct / len(groups)


def temporal_persistence(
    early_uids: Sequence[Hashable],
    later_uids: Sequence[Hashable],
) -> float:
    """Account-weighted reappearance, avoiding inflated row-weighted overlap."""

    early = set(early_uids)
    if not early:
        raise ValueError("early window must contain at least one UID")
    return len(early & set(later_uids)) / len(early)


def paired_block_bootstrap_lower_bound(
    paired_differences: Sequence[float],
    *,
    confidence: float = 0.95,
    repetitions: int = 2000,
    seed: int = 42,
) -> float:
    if not paired_differences or not 0.5 < confidence < 1 or repetitions < 100:
        raise ValueError("bootstrap requires differences, confidence > .5 and at least 100 repetitions")
    generator = random.Random(seed)
    width = len(paired_differences)
    means = [fmean(paired_differences[generator.randrange(width)] for _ in range(width)) for _ in range(repetitions)]
    return _quantile(means, 1 - confidence)


def evaluate_behavioral_client_proxy(
    evidence: UIDNestedAblationEvidence,
    *,
    confidence: float = 0.95,
    null_quantile: float = 0.95,
    major_reversal_tolerance: float = 0.0,
) -> BehavioralClientProxyGateResult:
    """Apply G1--G9 without treating an AUC gain as identity evidence."""

    uid_free_lower = paired_block_bootstrap_lower_bound(evidence.uid_free_gain_blocks, confidence=confidence)
    frequency_lower = paired_block_bootstrap_lower_bound(evidence.identity_gain_blocks, confidence=confidence)
    linkage_lower = paired_block_bootstrap_lower_bound(evidence.linkage_gain_blocks, confidence=confidence)
    construct_lower = paired_block_bootstrap_lower_bound(evidence.construct_validity_gains, confidence=confidence)
    persistence_lower = paired_block_bootstrap_lower_bound(evidence.temporal_persistence_gains, confidence=confidence)
    real_interaction = evidence.known_new_interaction
    null_gain_threshold = _quantile(evidence.matched_null_gains, null_quantile)
    null_interaction_threshold = _quantile(evidence.matched_null_interactions, null_quantile)
    horizon_positive = sum(value > 0 for value in evidence.horizon_identity_gains)
    seeds_stable = all(value > 0 for value in evidence.seed_identity_gains)
    no_major_reversal = min(evidence.horizon_identity_gains) >= -major_reversal_tolerance
    gates = {
        "G1_fold_safety": evidence.fold_safe,
        "G2_uid_free_ablation": evidence.score_by_model["M3_UID_MEMORY"] > evidence.score_by_model["M1_COMPONENTS"]
        and uid_free_lower > 0,
        "G3_frequency_separation": evidence.identity_gain > 0 and frequency_lower > 0,
        "G4_matched_null_rejection": evidence.identity_gain > null_gain_threshold,
        "G5_linkage_dependence": evidence.linkage_gain > 0 and linkage_lower > 0,
        "G6_construct_or_persistence": construct_lower > 0 or persistence_lower > 0,
        "G7_replication": horizon_positive >= 2 and no_major_reversal and seeds_stable,
        "G8_client_interaction": real_interaction > 0 and real_interaction > null_interaction_threshold,
        "G9_decision_adoption": evidence.decision_adopted,
    }
    structural = all(gates.values())
    predictive = evidence.score_by_model["M3_UID_MEMORY"] > evidence.score_by_model["M0_BASE"]
    classification = {
        (True, True): StructureClassification.VALIDATED_ACTIONABLE_STRUCTURE,
        (True, False): StructureClassification.VALIDATED_NON_ACTIONABLE_STRUCTURE,
        (False, True): StructureClassification.USEFUL_ENCODING_UNVALIDATED_STRUCTURE,
        (False, False): StructureClassification.REJECTED_STRUCTURE,
    }[(structural, predictive)]
    if structural and predictive:
        level = 1.0
    elif gates["G2_uid_free_ablation"] or gates["G4_matched_null_rejection"]:
        level = 0.75
    elif evidence.forward_candidate_executed:
        level = 0.50
    elif evidence.candidate_code_present:
        level = 0.25
    else:
        level = 0.0 if not evidence.hypothesis_present else 0.25
    diagnostics = {
        "delta_component": evidence.component_gain,
        "delta_frequency": evidence.frequency_gain,
        "delta_identity": evidence.identity_gain,
        "delta_linkage": evidence.linkage_gain,
        "delta_known_new_interaction": real_interaction,
        "matched_null_95th": null_gain_threshold,
        "uid_free_bootstrap_lower": uid_free_lower,
        "frequency_bootstrap_lower": frequency_lower,
        "linkage_bootstrap_lower": linkage_lower,
        "construct_bootstrap_lower": construct_lower,
        "persistence_bootstrap_lower": persistence_lower,
    }
    return BehavioralClientProxyGateResult(
        gates=gates,
        structural_validity_passed=structural,
        predictive_improvement_passed=predictive,
        classification=classification,
        acceptance_level=level,
        diagnostics=diagnostics,
    )


def generate_behavioral_client_synthetic_control(
    *,
    persistent_link: bool,
    clients: int = 40,
    periods: int = 12,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Positive/negative controls with identical UID frequency and time density.

    The negative arm keeps every surface UID's group size and period counts but
    removes persistent behavior and fraud risk from the link between its rows.
    """

    if clients < 8 or periods < 6:
        raise ValueError("synthetic control needs at least 8 clients and 6 periods")
    generator = random.Random(seed)
    rows: list[dict[str, Any]] = []
    devices = [f"device-{index % 7}" for index in range(clients)]
    risks = [0.80 if index % 5 == 0 else 0.08 for index in range(clients)]
    for period in range(periods):
        for client in range(clients):
            if persistent_link:
                device = devices[client]
                risk = risks[client]
            else:
                device = f"device-{generator.randrange(7)}"
                risk = 0.20
            rows.append(
                {
                    "uid": f"uid-{client}",
                    "card": f"card-{client % 13}",
                    "addr": f"addr-{client % 11}",
                    "email": f"mail-{client % 9}",
                    "period": period,
                    "missingness": client % 3,
                    "heldout_device": device,
                    "is_fraud": int(generator.random() < risk),
                }
            )
    return rows


def synthetic_behavioral_client_evidence(
    rows: Sequence[Mapping[str, Any]],
    *,
    seed: int = 42,
) -> UIDNestedAblationEvidence:
    if not rows:
        raise ValueError("synthetic rows cannot be empty")
    ordered = sorted(rows, key=lambda row: (int(row["period"]), str(row["uid"])))
    uids = [row["uid"] for row in ordered]
    periods = [row["period"] for row in ordered]
    missingness = [row["missingness"] for row in ordered]
    targets = [int(row["is_fraud"]) for row in ordered]
    devices = [row["heldout_device"] for row in ordered]
    predictions = _causal_group_rate_predictions(uids, targets)
    evaluation = [index for index, period in enumerate(periods) if int(period) >= 3]
    real_score = binary_auc([targets[index] for index in evaluation], [predictions[index] for index in evaluation])
    null_scores: list[float] = []
    null_interactions: list[float] = []
    shuffled_predictions_by_seed: list[list[float]] = []
    construct_gains: list[float] = []
    persistence_gains: list[float] = []
    real_consistency = heldout_feature_consistency(uids, devices)
    early = [uid for uid, period in zip(uids, periods, strict=True) if int(period) < 4]
    late = [uid for uid, period in zip(uids, periods, strict=True) if int(period) >= 8]
    real_persistence = temporal_persistence(early, late)
    for repetition in range(20):
        shuffled = frequency_matched_null_assignments(
            uids,
            periods,
            missingness,
            seed=seed + repetition + 1,
        )
        shuffled_predictions = _causal_group_rate_predictions(shuffled, targets)
        shuffled_predictions_by_seed.append(shuffled_predictions)
        score = binary_auc(
            [targets[index] for index in evaluation],
            [shuffled_predictions[index] for index in evaluation],
        )
        null_scores.append(score - 0.5)
        null_interactions.append(score - 0.5)
        construct_gains.append(real_consistency - heldout_feature_consistency(shuffled, devices))
        shuffled_early = [uid for uid, period in zip(shuffled, periods, strict=True) if int(period) < 4]
        shuffled_late = [uid for uid, period in zip(shuffled, periods, strict=True) if int(period) >= 8]
        persistence_gains.append(real_persistence - temporal_persistence(shuffled_early, shuffled_late))
    horizon_periods = sorted(set(int(item) for item in periods if int(item) >= 3))
    chunks = [horizon_periods[index::3] for index in range(3)]
    horizon_gains = []
    linkage_blocks = []
    first_shuffled = shuffled_predictions_by_seed[0]
    for chunk in chunks:
        indices = [index for index, period in enumerate(periods) if int(period) in chunk]
        target_slice = [targets[index] for index in indices]
        real = binary_auc(target_slice, [predictions[index] for index in indices])
        shuffled_score = binary_auc(target_slice, [first_shuffled[index] for index in indices])
        horizon_gains.append(real - 0.5)
        linkage_blocks.append(real - shuffled_score)
    score_by_model = {
        "M0_BASE": 0.5,
        "M1_COMPONENTS": 0.5,
        "M2_FREQUENCY": 0.5,
        "M3_UID_MEMORY": real_score,
        "M4_LINK_SHUFFLED": 0.5 + fmean(null_scores),
        "M5_MATCHED_NULL": 0.5 + fmean(null_scores),
    }
    return UIDNestedAblationEvidence(
        score_by_model=score_by_model,
        uid_free_gain_blocks=tuple(horizon_gains),
        frequency_gain_blocks=tuple(horizon_gains),
        identity_gain_blocks=tuple(horizon_gains),
        linkage_gain_blocks=tuple(linkage_blocks),
        matched_null_gains=tuple(null_scores),
        construct_validity_gains=tuple(construct_gains),
        temporal_persistence_gains=tuple(persistence_gains),
        horizon_identity_gains=tuple(horizon_gains),
        seed_identity_gains=tuple(real_score - 0.5 for _ in range(3)),
        known_identity_gain=real_score - 0.5,
        new_identity_gain=0.0,
        matched_null_interactions=tuple(null_interactions),
        fold_safe=True,
        decision_adopted=True,
    )


def evaluate_structure_validator_controls(
    positive_results: Sequence[BehavioralClientProxyGateResult],
    negative_results: Sequence[BehavioralClientProxyGateResult],
    *,
    elapsed_minutes: float,
    experiment_cost: float,
) -> StructureValidatorControlReport:
    if not positive_results or not negative_results:
        raise ValueError("both positive and negative synthetic controls are required")
    positive_rate = sum(item.structural_validity_passed for item in positive_results) / len(positive_results)
    negative_rejection = sum(not item.structural_validity_passed for item in negative_results) / len(negative_results)
    return StructureValidatorControlReport(
        positive_control_acceptance_rate=positive_rate,
        negative_control_rejection_rate=negative_rejection,
        false_structure_promotion_rate=1 - negative_rejection,
        time_to_structure_validation_minutes=elapsed_minutes,
        validation_experiment_cost=experiment_cost,
    )


def multi_horizon_forward_folds(
    row_ids: Sequence[str],
    timestamps: Sequence[Any],
    *,
    horizons: int = 3,
    gap_rows: int = 1,
    world_id: str = "W-multi-horizon-time-gap",
) -> list[FoldAssignment]:
    if horizons < 3:
        raise ValueError("IEEE-CIS candidate validation requires at least three horizons")
    if gap_rows < 1:
        raise ValueError("IEEE-CIS forward validation requires a non-zero time gap")
    return time_folds(row_ids, timestamps, world_id=world_id, n_splits=horizons, gap_rows=gap_rows)


def rolling_window_forward_folds(
    row_ids: Sequence[str],
    timestamps: Sequence[Any],
    *,
    horizons: int = 3,
    gap_rows: int = 1,
    train_window_rows: int,
) -> list[FoldAssignment]:
    if train_window_rows < 1:
        raise ValueError("rolling train window must be positive")
    expanding = multi_horizon_forward_folds(row_ids, timestamps, horizons=horizons, gap_rows=gap_rows)
    return [fold.model_copy(update={"train_row_ids": fold.train_row_ids[-train_window_rows:]}) for fold in expanding]


def fold_safe_uid_aggregates(
    fit_rows: Sequence[Mapping[str, Any]],
    transform_rows: Sequence[Mapping[str, Any]],
    *,
    uid: UIDCandidate,
    amount_column: str = "TransactionAmt",
    time_column: str = "TransactionDT",
    aggregate_columns: Sequence[str] = (),
) -> list[dict[str, float]]:
    """Fit target-independent UID aggregates on one fold, then transform another."""

    amounts: dict[str, list[float]] = defaultdict(list)
    times: dict[str, list[float]] = defaultdict(list)
    values: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in fit_rows:
        key = uid_value(row, uid)
        amount = _number(row.get(amount_column))
        timestamp = _number(row.get(time_column))
        if amount is not None:
            amounts[key].append(amount)
        if timestamp is not None:
            times[key].append(timestamp)
        for column in aggregate_columns:
            value = _number(row.get(column))
            if value is not None:
                values[(key, column)].append(value)

    result = []
    for row in transform_rows:
        key = uid_value(row, uid)
        group_amounts = amounts.get(key, [])
        timestamp = _number(row.get(time_column))
        features = {
            "uid_count": float(len(group_amounts)),
            "uid_amount_mean": fmean(group_amounts) if group_amounts else 0.0,
            "uid_amount_std": pstdev(group_amounts) if len(group_amounts) > 1 else 0.0,
            "uid_frequency": len(group_amounts) / max(1, len(fit_rows)),
            "uid_time_delta": (timestamp - max(times[key]) if timestamp is not None and times.get(key) else 0.0),
        }
        for column in aggregate_columns:
            group = values.get((key, column), [])
            features[f"uid_{column}_mean"] = fmean(group) if group else 0.0
            features[f"uid_{column}_std"] = pstdev(group) if len(group) > 1 else 0.0
        result.append(features)
    return result


def fold_safe_uid_history_features(
    fit_rows: Sequence[Mapping[str, Any]],
    transform_rows: Sequence[Mapping[str, Any]],
    *,
    uid: UIDCandidate,
    target_column: str = "isFraud",
    time_column: str = "TransactionDT",
) -> list[dict[str, float]]:
    """Use only strictly earlier fit-row labels; transform labels are never read."""

    history: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for row in fit_rows:
        key = uid_value(row, uid)
        target = _number(row.get(target_column))
        timestamp = _number(row.get(time_column))
        if target is not None and timestamp is not None:
            history[key].append((timestamp, int(target > 0.5)))
    for values in history.values():
        values.sort()
    output = []
    for row in transform_rows:
        key = uid_value(row, uid)
        timestamp = _number(row.get(time_column))
        prior = [item for item in history[key] if timestamp is not None and item[0] < timestamp]
        count = len(prior)
        output.append(
            {
                "uid_history_count": float(count),
                "uid_history_fraud_rate": sum(item[1] for item in prior) / count if count else 0.0,
                "uid_history_recency": timestamp - prior[-1][0] if timestamp is not None and prior else 0.0,
            }
        )
    return output


def client_slices(
    fit_uids: Sequence[Hashable],
    validation_uids: Sequence[Hashable],
) -> dict[str, list[int]]:
    counts = Counter(fit_uids)
    slices: dict[str, list[int]] = {"known": [], "new": [], "questionable": []}
    for index, value in enumerate(validation_uids):
        if counts[value] >= 2:
            slices["known"].append(index)
        elif counts[value] == 1:
            slices["questionable"].append(index)
        else:
            slices["new"].append(index)
    return slices


def client_frequency_slices(fit_uids: Sequence[Hashable], validation_uids: Sequence[Hashable]) -> dict[str, list[int]]:
    counts = Counter(fit_uids)
    result: dict[str, list[int]] = {"frequency_0": [], "frequency_1": [], "frequency_2_5": [], "frequency_6_plus": []}
    for index, uid in enumerate(validation_uids):
        count = counts[uid]
        if count == 0:
            key = "frequency_0"
        elif count == 1:
            key = "frequency_1"
        elif count <= 5:
            key = "frequency_2_5"
        else:
            key = "frequency_6_plus"
        result[key].append(index)
    return result


def client_slice_auc(
    targets: Sequence[int],
    predictions: Sequence[float],
    slices: Mapping[str, Sequence[int]],
) -> dict[str, float | None]:
    if len(targets) != len(predictions):
        raise ValueError("targets and predictions must align")
    result: dict[str, float | None] = {}
    for name, indices in slices.items():
        labels = [targets[index] for index in indices]
        scores = [predictions[index] for index in indices]
        result[f"{name}_client_auc"] = binary_auc(labels, scores) if len(set(labels)) == 2 else None
    return result


def client_level_average(predictions: Sequence[float], uids: Sequence[Hashable]) -> list[float]:
    if len(predictions) != len(uids):
        raise ValueError("predictions and uids must align")
    totals: dict[Hashable, list[float]] = defaultdict(list)
    for prediction, uid in zip(predictions, uids, strict=True):
        totals[uid].append(float(prediction))
    means = {uid: fmean(values) for uid, values in totals.items()}
    return [means[uid] for uid in uids]


def known_new_routing(
    global_predictions: Sequence[float],
    client_predictions: Sequence[float],
    known_indices: Sequence[int],
) -> list[float]:
    if len(global_predictions) != len(client_predictions):
        raise ValueError("routing predictions must align")
    known = set(known_indices)
    return [
        float(client_predictions[index] if index in known else global_predictions[index])
        for index in range(len(global_predictions))
    ]


def temporal_smoothing(
    predictions: Sequence[float],
    uids: Sequence[Hashable],
    *,
    strength: float = 0.25,
) -> list[float]:
    if not 0 <= strength <= 1 or len(predictions) != len(uids):
        raise ValueError("invalid smoothing strength or unaligned data")
    history: dict[Hashable, list[float]] = defaultdict(list)
    output = []
    for prediction, uid in zip(predictions, uids, strict=True):
        prior = fmean(history[uid]) if history[uid] else float(prediction)
        output.append((1 - strength) * float(prediction) + strength * prior)
        history[uid].append(float(prediction))
    return output


def histogram_calibration(
    fit_predictions: Sequence[float],
    fit_targets: Sequence[int],
    transform_predictions: Sequence[float],
    *,
    bins: int = 20,
) -> list[float]:
    """Fit calibration bins on one fold and transform another fold."""

    if len(fit_predictions) != len(fit_targets) or not fit_predictions or bins < 2:
        raise ValueError("calibration fit data must be aligned and bins >= 2")
    totals = [0] * bins
    positives = [0] * bins
    for prediction, target in zip(fit_predictions, fit_targets, strict=True):
        index = min(bins - 1, max(0, int(float(prediction) * bins)))
        totals[index] += 1
        positives[index] += int(target)
    rates = [positives[index] / totals[index] if totals[index] else (index + 0.5) / bins for index in range(bins)]
    return [rates[min(bins - 1, max(0, int(float(value) * bins)))] for value in transform_predictions]


def rank_blend(predictions: Mapping[str, Sequence[float]], weights: Mapping[str, float] | None = None) -> list[float]:
    if len(predictions) < 2 or len({len(values) for values in predictions.values()}) != 1:
        raise ValueError("rank blend requires at least two aligned candidates")
    identifiers = sorted(predictions)
    if weights is None:
        weights = {identifier: 1 / len(identifiers) for identifier in identifiers}
    if set(weights) != set(identifiers) or any(value < 0 for value in weights.values()):
        raise ValueError("rank blend weights must cover candidates and be non-negative")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("rank blend weights must have positive mass")
    ranks = {identifier: _normalized_ranks(predictions[identifier]) for identifier in identifiers}
    width = len(next(iter(predictions.values())))
    return [sum(weights[item] / total * ranks[item][index] for item in identifiers) for index in range(width)]


def model_rank_stability(scores_by_horizon: Mapping[str, Sequence[float]]) -> float:
    """Mean Spearman correlation of model ranks between forward horizons."""

    if len(scores_by_horizon) < 2:
        raise ValueError("rank stability requires at least two model families")
    lengths = {len(scores) for scores in scores_by_horizon.values()}
    if len(lengths) != 1 or next(iter(lengths)) < 2:
        raise ValueError("rank stability requires at least two aligned horizons")
    models = sorted(scores_by_horizon)
    horizon_ranks = []
    for horizon in range(next(iter(lengths))):
        horizon_ranks.append(_normalized_ranks([scores_by_horizon[model][horizon] for model in models]))
    correlations = []
    for left, right in itertools.combinations(horizon_ranks, 2):
        left_mean = fmean(left)
        right_mean = fmean(right)
        numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
        denominator = math.sqrt(
            sum((value - left_mean) ** 2 for value in left) * sum((value - right_mean) ** 2 for value in right)
        )
        correlations.append(numerator / denominator if denominator else 1.0)
    return fmean(correlations)


def make_model_family(name: str, *, seed: int = 42) -> Any:
    """Lazy solver-extra factory; orchestration remains free of ML dependencies."""

    if name == "logistic":
        from sklearn.linear_model import LogisticRegression

        return LogisticRegression(max_iter=500, random_state=seed)
    if name == "lightgbm":
        from lightgbm import LGBMClassifier

        return LGBMClassifier(n_estimators=500, learning_rate=0.05, random_state=seed, verbosity=-1)
    raise ValueError(f"unsupported IEEE-CIS model family: {name}")


def require_adversarial_followup(*, adversarial_auc_changed: bool, forward_fraud_validation_completed: bool) -> None:
    if adversarial_auc_changed and not forward_fraud_validation_completed:
        raise ValueError(
            "adversarial AUC is diagnostic only; run multi-horizon forward fraud-label validation before adoption"
        )


def ieee_cis_capabilities() -> dict[str, object]:
    return {
        "uid_generation": True,
        "validated_identity_label": "validated_behavioral_client_proxy",
        "nested_uid_ablation": list(UID_ABLATION_MODELS),
        "frequency_matched_null_repetitions_minimum": 20,
        "linkage_shuffle": True,
        "construct_validity": True,
        "temporal_persistence": True,
        "known_new_interaction": True,
        "synthetic_structure_controls": ["stable_latent_client", "frequency_matched_no_link"],
        "forward_horizons_minimum": 3,
        "time_gap": True,
        "fold_safe_uid_aggregation": True,
        "client_slices": ["known", "new", "questionable"],
        "model_families": ["lightgbm", "logistic"],
        "post_processing": ["client_average", "known_new_routing", "temporal_smoothing", "calibration"],
        "ensemble": ["weighted_blend", "rank_blend", "stack", "nested_cross_fit"],
        "oof_required": True,
    }


def binary_auc(targets: Sequence[int], predictions: Sequence[float]) -> float:
    if len(targets) != len(predictions) or not targets:
        raise ValueError("AUC requires aligned non-empty targets and predictions")
    positives = sum(targets)
    negatives = len(targets) - positives
    if positives == 0 or negatives == 0:
        raise ValueError("AUC requires both classes")
    ordered = sorted(enumerate(predictions), key=lambda item: item[1])
    ranks = [0.0] * len(predictions)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and ordered[end][1] == ordered[cursor][1]:
            end += 1
        average_rank = (cursor + 1 + end) / 2
        for original, _ in ordered[cursor:end]:
            ranks[original] = average_rank
        cursor = end
    positive_rank_sum = sum(rank for rank, target in zip(ranks, targets, strict=True) if target == 1)
    return (positive_rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(result) else result


def _frequency_bucket(frequency: int) -> int:
    if frequency <= 1:
        return frequency
    if frequency <= 5:
        return 2
    if frequency <= 20:
        return 6
    return 21


def _causal_group_rate_predictions(groups: Sequence[Hashable], targets: Sequence[int]) -> list[float]:
    if len(groups) != len(targets):
        raise ValueError("causal group history inputs must align")
    positives: Counter[Hashable] = Counter()
    totals: Counter[Hashable] = Counter()
    predictions = []
    for group, target in zip(groups, targets, strict=True):
        predictions.append((positives[group] + 1) / (totals[group] + 2))
        totals[group] += 1
        positives[group] += int(target)
    return predictions


def _quantile(values: Sequence[float], quantile: float) -> float:
    if not values or not 0 <= quantile <= 1:
        raise ValueError("quantile requires non-empty values and a probability")
    ordered = sorted(float(item) for item in values)
    index = min(len(ordered) - 1, max(0, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index]


def _normalized_ranks(values: Sequence[float]) -> list[float]:
    if not values:
        raise ValueError("rank vector cannot be empty")
    ordered = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[cursor]]:
            end += 1
        average = (cursor + end - 1) / 2
        for index in ordered[cursor:end]:
            ranks[index] = average / max(1, len(values) - 1)
        cursor = end
    return ranks
