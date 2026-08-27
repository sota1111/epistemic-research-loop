"""Blind positive/negative structure controls and a generic reference probe policy.

The agent-facing view exposes only an opaque case identifier, schema, labelled
research rows, and unlabelled sealed rows.  Family and polarity remain in the
controller-owned truth record until every decision is frozen.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from statistics import fmean, median

from epistemic_loop.evaluation.v035 import SeedControlObservation, StructureValidationBundle

CONTROL_SEEDS = (17, 42, 20260826)
OPERATORS = ("repeated_unit_history", "temporal_state", "observation_regime", "conditional_routing")


@dataclass(frozen=True)
class ControlRow:
    row_id: int
    time: float
    unit: int
    signal: float
    heldout_attribute: float
    measure_a: float | None
    measure_b: float | None
    route_hint: int
    target: int

    @property
    def missing_pattern(self) -> int:
        if self.measure_a is None and self.measure_b is not None:
            return 1
        if self.measure_b is None and self.measure_a is not None:
            return 2
        if self.measure_a is None and self.measure_b is None:
            return 3
        return 0

    @property
    def missing_count(self) -> int:
        return int(self.measure_a is None) + int(self.measure_b is None)


@dataclass(frozen=True)
class AgentControlView:
    opaque_case_id: str
    schema: tuple[str, ...]
    research_rows: tuple[ControlRow, ...]
    sealed_rows: tuple[ControlRow, ...]

    def __post_init__(self) -> None:
        if any(row.target not in {0, 1} for row in self.research_rows):
            raise ValueError("research target must be binary")
        if any(row.target != -1 for row in self.sealed_rows):
            raise ValueError("sealed targets must be absent from the agent view")


@dataclass(frozen=True)
class StructureControlTruth:
    opaque_case_id: str
    family_label: str
    structure_present: bool
    expected_operator: str
    generator_seed: int
    sealed_targets: tuple[int, ...]


@dataclass(frozen=True)
class BlindStructureControl:
    view: AgentControlView
    truth: StructureControlTruth


@dataclass(frozen=True)
class BlindAgentDecision:
    operator: str
    validation_gain: float
    null_95th_percentile: float
    independent_implication_strength: float
    positive_contexts: int
    context_count: int
    confidence: float
    decision_changed: bool
    bundle: StructureValidationBundle
    structure_free_sealed_predictions: tuple[float, ...]
    structure_informed_sealed_predictions: tuple[float, ...]


class GenericBlindStructureAgent:
    """Run the same generic operator set without control-family or polarity hints."""

    def __init__(
        self,
        *,
        minimum_validation_gain: float = 0.008,
        minimum_independent_strength: float = 0.18,
        minimum_null_margin: float = 0.002,
        null_repetitions: int = 20,
        orthogonalize_temporal_probe: bool = True,
    ):
        if null_repetitions < 20:
            raise ValueError("v0.3.5 structure qualification requires at least 20 null repetitions")
        self.minimum_validation_gain = minimum_validation_gain
        self.minimum_independent_strength = minimum_independent_strength
        self.minimum_null_margin = minimum_null_margin
        self.null_repetitions = null_repetitions
        self.orthogonalize_temporal_probe = orthogonalize_temporal_probe

    def investigate(self, view: AgentControlView, *, seed: int) -> BlindAgentDecision:
        research = view.research_rows
        split = int(len(research) * 0.67)
        train, validation = research[:split], research[split:]
        base_model = _fit_model(train, "base", orthogonalize_temporal=self.orthogonalize_temporal_probe)
        base_validation = _auc([row.target for row in validation], base_model.predict(validation))
        candidates: list[tuple[str, float, _LinearRanker]] = []
        for operator in OPERATORS:
            model = _fit_model(train, operator, orthogonalize_temporal=self.orthogonalize_temporal_probe)
            score = _auc([row.target for row in validation], model.predict(validation))
            candidates.append((operator, score - base_validation, model))
        operator, gain, _ = max(candidates, key=lambda item: (item[1], item[0]))
        null_gains = self._null_gains(train, validation, operator, base_validation, seed=seed)
        null_threshold = _quantile(null_gains, 0.95)
        implication = _independent_implication(train, operator)
        context_gains = _context_gains(
            train,
            validation,
            operator,
            orthogonalize_temporal=self.orthogonalize_temporal_probe,
        )
        positive_contexts = sum(value > 0 for value in context_gains)
        null_passed = gain > null_threshold + self.minimum_null_margin
        implication_passed = implication >= self.minimum_independent_strength
        context_passed = positive_contexts >= 2 and min(context_gains) >= -0.01
        decision_changed = (
            gain >= self.minimum_validation_gain and null_passed and implication_passed and context_passed
        )
        evidence_margin = (
            35 * (gain - self.minimum_validation_gain)
            + 20 * (gain - null_threshold - self.minimum_null_margin)
            + 2 * (implication - self.minimum_independent_strength)
        )
        confidence = _sigmoid(evidence_margin)
        full_research = research
        base_full = _fit_model(full_research, "base", orthogonalize_temporal=self.orthogonalize_temporal_probe)
        informed_full = _fit_model(full_research, operator, orthogonalize_temporal=self.orthogonalize_temporal_probe)
        bundle = StructureValidationBundle(
            competing_hypotheses_registered=True,
            fold_causal_safety=True,
            confounder_preserving_null=null_passed,
            independent_implication=implication_passed,
            multi_context_replication=context_passed,
            negative_control_discrimination=confidence >= 0.5,
            decision_changed=decision_changed,
        )
        return BlindAgentDecision(
            operator=operator,
            validation_gain=gain,
            null_95th_percentile=null_threshold,
            independent_implication_strength=implication,
            positive_contexts=positive_contexts,
            context_count=len(context_gains),
            confidence=confidence,
            decision_changed=decision_changed,
            bundle=bundle,
            structure_free_sealed_predictions=tuple(base_full.predict(view.sealed_rows)),
            structure_informed_sealed_predictions=tuple(informed_full.predict(view.sealed_rows)),
        )

    def _null_gains(
        self,
        train: Sequence[ControlRow],
        validation: Sequence[ControlRow],
        operator: str,
        base_validation_auc: float,
        *,
        seed: int,
    ) -> list[float]:
        gains: list[float] = []
        generator = random.Random(seed ^ 0x5A17)
        for _ in range(self.null_repetitions):
            null_train = _shuffle_context(train, operator, generator)
            null_validation = _shuffle_context(validation, operator, generator)
            null_model = _fit_model(
                null_train,
                operator,
                orthogonalize_temporal=self.orthogonalize_temporal_probe,
            )
            null_auc = _auc([row.target for row in null_validation], null_model.predict(null_validation))
            gains.append(null_auc - base_validation_auc)
        return gains


class _LinearRanker:
    def __init__(
        self,
        means: tuple[float, ...],
        scales: tuple[float, ...],
        weights: tuple[float, ...],
        bias: float,
        operator: str,
        unit_priors: Mapping[int, float],
        orthogonalize_temporal: bool,
    ):
        self.means = means
        self.scales = scales
        self.weights = weights
        self.bias = bias
        self.operator = operator
        self.unit_priors = dict(unit_priors)
        self.orthogonalize_temporal = orthogonalize_temporal

    def predict(self, rows: Sequence[ControlRow]) -> list[float]:
        output: list[float] = []
        for row in rows:
            vector = _feature_vector(
                row,
                self.operator,
                self.unit_priors,
                orthogonalize_temporal=self.orthogonalize_temporal,
            )
            standardized = [
                (value - mean) / scale for value, mean, scale in zip(vector, self.means, self.scales, strict=True)
            ]
            output.append(_sigmoid(self.bias + sum(w * x for w, x in zip(self.weights, standardized, strict=True))))
        return output


def generate_blind_structure_controls(
    *,
    seeds: Sequence[int] = CONTROL_SEEDS,
    rows: int = 1200,
) -> tuple[BlindStructureControl, ...]:
    if len(set(seeds)) < 3:
        raise ValueError("control generation requires at least three unique seeds")
    definitions = (
        ("control-01", "P1_persistent_entity", True, "repeated_unit_history"),
        ("control-02", "P2_temporal_regime", True, "temporal_state"),
        ("control-03", "P3_observation_process", True, "observation_regime"),
        ("control-04", "P4_problem_decomposition", True, "conditional_routing"),
        ("control-05", "N1_frequency_artifact", False, "repeated_unit_history"),
        ("control-06", "N2_temporal_looking_noise", False, "temporal_state"),
        ("control-07", "N3_missingness_artifact", False, "observation_regime"),
        ("control-08", "N4_random_routing", False, "conditional_routing"),
    )
    controls: list[BlindStructureControl] = []
    for seed in seeds:
        for opaque_id, family, present, operator in definitions:
            full = _generate_rows(family, seed=seed, count=rows)
            split = int(len(full) * 0.70)
            research = full[:split]
            sealed_true = full[split:]
            sealed_view = tuple(replace(row, target=-1) for row in sealed_true)
            case_id = "case-" + hashlib.sha256(f"{opaque_id}:{seed}".encode()).hexdigest()[:16]
            controls.append(
                BlindStructureControl(
                    view=AgentControlView(
                        opaque_case_id=case_id,
                        schema=(
                            "row_id",
                            "time",
                            "unit",
                            "signal",
                            "heldout_attribute",
                            "measure_a",
                            "measure_b",
                            "route_hint",
                            "target",
                        ),
                        research_rows=tuple(research),
                        sealed_rows=sealed_view,
                    ),
                    truth=StructureControlTruth(
                        opaque_case_id=case_id,
                        family_label=family,
                        structure_present=present,
                        expected_operator=operator,
                        generator_seed=seed,
                        sealed_targets=tuple(row.target for row in sealed_true),
                    ),
                )
            )
    return tuple(controls)


def run_blind_control_suite(
    agent: GenericBlindStructureAgent,
    controls: Sequence[BlindStructureControl],
) -> tuple[SeedControlObservation, ...]:
    output: list[SeedControlObservation] = []
    for control in controls:
        analysis_seed = int.from_bytes(hashlib.sha256(control.view.opaque_case_id.encode()).digest()[:4], "big")
        decision = agent.investigate(control.view, seed=analysis_seed)
        targets = control.truth.sealed_targets
        output.append(
            SeedControlObservation(
                control_id=control.truth.family_label,
                seed=control.truth.generator_seed,
                structure_present=control.truth.structure_present,
                predicted_structure_probability=decision.confidence,
                selected_operator=decision.operator,
                ground_truth_operator_match=decision.operator == control.truth.expected_operator,
                bundle=decision.bundle,
                structure_free_sealed_auc=_auc(targets, decision.structure_free_sealed_predictions),
                structure_informed_sealed_auc=_auc(targets, decision.structure_informed_sealed_predictions),
            )
        )
    return tuple(output)


def _generate_rows(family: str, *, seed: int, count: int) -> list[ControlRow]:
    generator = random.Random(seed ^ sum(ord(char) for char in family))
    group_effects = {group: generator.gauss(0, 1) for group in range(48)}
    rows: list[ControlRow] = []
    for index in range(count):
        time = index / (count - 1)
        unit = (index * 17 + seed) % 48
        signal = generator.gauss(0, 1)
        route = generator.randrange(2)
        pattern = index % 3
        measure_a = None if pattern == 1 else generator.gauss(0, 1)
        measure_b = None if pattern == 2 else generator.gauss(0, 1)
        missing_count = int(measure_a is None) + int(measure_b is None)
        heldout = generator.gauss(0, 1)
        logit = 0.9 * signal
        if family == "P1_persistent_entity":
            heldout = group_effects[unit] + generator.gauss(0, 0.35)
            logit = 0.45 * signal + 1.8 * group_effects[unit]
        elif family == "N1_frequency_artifact":
            logit = 0.9 * signal + 0.15 * math.log1p(unit % 6)
        elif family == "P2_temporal_regime":
            coefficient = -1.6 + 3.8 * time
            logit = coefficient * signal + 0.35 * time
        elif family == "N2_temporal_looking_noise":
            logit = 1.25 * signal + 0.8 * time
        elif family == "P3_observation_process":
            coefficient = {0: 0.7, 1: 2.2, 2: -2.0}[pattern]
            logit = coefficient * signal + 0.25 * missing_count
        elif family == "N3_missingness_artifact":
            logit = 1.2 * signal + 0.9 * missing_count
        elif family == "P4_problem_decomposition":
            logit = (-2.0 if route == 0 else 2.1) * signal + 0.2 * route
        elif family == "N4_random_routing":
            logit = 1.25 * signal + 0.35 * route
        target = int(generator.random() < _sigmoid(logit))
        rows.append(
            ControlRow(
                row_id=index,
                time=time,
                unit=unit,
                signal=signal,
                heldout_attribute=heldout,
                measure_a=measure_a,
                measure_b=measure_b,
                route_hint=route,
                target=target,
            )
        )
    return rows


def _fit_model(
    rows: Sequence[ControlRow],
    operator: str,
    *,
    orthogonalize_temporal: bool = True,
) -> _LinearRanker:
    if not rows:
        raise ValueError("model fit requires rows")
    unit_values: dict[int, list[int]] = defaultdict(list)
    for row in rows:
        unit_values[row.unit].append(row.target)
    global_mean = fmean(row.target for row in rows)
    unit_priors = {unit: (sum(values) + 8 * global_mean) / (len(values) + 8) for unit, values in unit_values.items()}
    vectors = [
        _feature_vector(
            row,
            operator,
            unit_priors,
            orthogonalize_temporal=orthogonalize_temporal,
        )
        for row in rows
    ]
    width = len(vectors[0])
    means = tuple(fmean(vector[index] for vector in vectors) for index in range(width))
    scales = tuple(
        max(math.sqrt(fmean((vector[index] - means[index]) ** 2 for vector in vectors)), 1e-6) for index in range(width)
    )
    standardized = [
        [(value - mean) / scale for value, mean, scale in zip(vector, means, scales, strict=True)] for vector in vectors
    ]
    weights = [0.0] * width
    bias = math.log(max(global_mean, 1e-4) / max(1 - global_mean, 1e-4))
    learning_rate = 0.12
    for _ in range(100):
        gradient = [0.0] * width
        bias_gradient = 0.0
        for vector, row in zip(standardized, rows, strict=True):
            prediction = _sigmoid(bias + sum(w * x for w, x in zip(weights, vector, strict=True)))
            error = prediction - row.target
            bias_gradient += error
            for index, value in enumerate(vector):
                gradient[index] += error * value
        count = len(rows)
        bias -= learning_rate * bias_gradient / count
        for index in range(width):
            weights[index] -= learning_rate * (gradient[index] / count + 0.01 * weights[index])
    return _LinearRanker(
        means,
        scales,
        tuple(weights),
        bias,
        operator,
        unit_priors,
        orthogonalize_temporal,
    )


def _feature_vector(
    row: ControlRow,
    operator: str,
    unit_priors: Mapping[int, float],
    *,
    orthogonalize_temporal: bool,
) -> list[float]:
    vector = [row.signal, row.time, float(row.missing_count), float(row.route_hint)]
    if operator == "repeated_unit_history":
        fallback = fmean(unit_priors.values()) if unit_priors else 0.5
        vector.append(unit_priors.get(row.unit, fallback))
    elif operator == "temporal_state":
        if orthogonalize_temporal:
            # Center the interaction in the early research window so a changing
            # relationship is identifiable instead of being absorbed by ``signal``.
            vector.extend((row.signal * (row.time - 0.25), row.signal * float(row.time >= 0.35)))
        else:
            vector.extend((row.signal * row.time, row.signal * float(row.time >= 0.5)))
    elif operator == "observation_regime":
        vector.extend(
            (
                row.signal * float(row.missing_pattern == 1),
                row.signal * float(row.missing_pattern == 2),
            )
        )
    elif operator == "conditional_routing":
        vector.append(row.signal * float(row.route_hint))
    elif operator != "base":
        raise ValueError(f"unknown generic structure operator: {operator}")
    return vector


def _independent_implication(rows: Sequence[ControlRow], operator: str) -> float:
    if operator == "repeated_unit_history":
        by_unit: dict[int, list[float]] = defaultdict(list)
        for row in rows:
            by_unit[row.unit].append(row.heldout_attribute)
        group_means = [fmean(values) for values in by_unit.values()]
        total_variance = _variance([row.heldout_attribute for row in rows])
        return min(1.0, _variance(group_means) / max(total_variance, 1e-9))
    if operator == "temporal_state":
        early = [row for row in rows if row.time < median(item.time for item in rows)]
        late = [row for row in rows if row.time >= median(item.time for item in rows)]
        return min(1.0, abs(_correlation(early) - _correlation(late)))
    if operator == "observation_regime":
        correlations = [_correlation([row for row in rows if row.missing_pattern == pattern]) for pattern in (0, 1, 2)]
        return min(1.0, max(correlations) - min(correlations))
    correlations = [_correlation([row for row in rows if row.route_hint == route]) for route in (0, 1)]
    return min(1.0, abs(correlations[0] - correlations[1]))


def _context_gains(
    train: Sequence[ControlRow],
    validation: Sequence[ControlRow],
    operator: str,
    *,
    orthogonalize_temporal: bool,
) -> tuple[float, ...]:
    base = _fit_model(train, "base", orthogonalize_temporal=orthogonalize_temporal)
    informed = _fit_model(train, operator, orthogonalize_temporal=orthogonalize_temporal)
    ordered = sorted(validation, key=lambda row: row.time)
    blocks = [ordered[index::3] for index in range(3)]
    gains: list[float] = []
    for block in blocks:
        targets = [row.target for row in block]
        gains.append(_auc(targets, informed.predict(block)) - _auc(targets, base.predict(block)))
    return tuple(gains)


def _shuffle_context(rows: Sequence[ControlRow], operator: str, generator: random.Random) -> list[ControlRow]:
    values: list[int | float]
    if operator == "repeated_unit_history":
        values = [row.unit for row in rows]
    elif operator == "temporal_state":
        values = [row.time for row in rows]
    elif operator == "observation_regime":
        values = [row.missing_pattern for row in rows]
    else:
        values = [row.route_hint for row in rows]
    generator.shuffle(values)
    output: list[ControlRow] = []
    for row, value in zip(rows, values, strict=True):
        if operator == "repeated_unit_history":
            output.append(replace(row, unit=int(value)))
        elif operator == "temporal_state":
            output.append(replace(row, time=float(value)))
        elif operator == "observation_regime":
            pattern = int(value)
            measure_a = None if pattern in {1, 3} else (row.measure_a if row.measure_a is not None else 0.0)
            measure_b = None if pattern in {2, 3} else (row.measure_b if row.measure_b is not None else 0.0)
            output.append(replace(row, measure_a=measure_a, measure_b=measure_b))
        else:
            output.append(replace(row, route_hint=int(value)))
    return output


def _correlation(rows: Sequence[ControlRow]) -> float:
    if len(rows) < 3:
        return 0.0
    x_mean = fmean(row.signal for row in rows)
    y_mean = fmean(row.target for row in rows)
    numerator = sum((row.signal - x_mean) * (row.target - y_mean) for row in rows)
    x_scale = math.sqrt(sum((row.signal - x_mean) ** 2 for row in rows))
    y_scale = math.sqrt(sum((row.target - y_mean) ** 2 for row in rows))
    return numerator / (x_scale * y_scale) if x_scale and y_scale else 0.0


def _variance(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean = fmean(values)
    return fmean((value - mean) ** 2 for value in values)


def _auc(targets: Sequence[int], predictions: Sequence[float]) -> float:
    if len(targets) != len(predictions) or not targets:
        raise ValueError("AUC inputs must be aligned and non-empty")
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
        average_rank = (start + 1 + end) / 2
        rank_sum += average_rank * sum(target for _, target in ordered[start:end])
        start = end
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("quantile requires observations")
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(probability * len(ordered)) - 1))
    return ordered[index]


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1 + exponent)
