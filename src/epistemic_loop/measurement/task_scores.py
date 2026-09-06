"""Persist the per-task raw vector. The composite is a derived value, never a stored one.

`docs/v050_course_correction.md` §3 item 4. The scoring system always changes mid-campaign: a
weight moves, a gate threshold moves, a metric turns out to measure something else. When only the
composite was stored, every such change meant re-scoring every candidate -- ten minutes each, for
a change that touches no candidate's behaviour at all. With the per-task raw vector kept, the same
change is a recomputation (`docs/v050_lessons.md` §1.6).

The rule is enforced rather than documented: :class:`TaskScore` refuses metric names that are
composites, so a caller cannot quietly persist the derived number alongside the raw one and let
the two drift apart.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Names that mean "already combined". Storing one of these defeats the point of the store: the
#: recomputation would silently read a composite built under the previous weights.
DERIVED_METRIC_NAMES = frozenset({"composite", "combined", "combined_score", "score", "total", "weighted"})


class DerivedMetricError(ValueError):
    """Raised when a composite is offered to a store that only holds raw per-task measurements."""


@dataclass(frozen=True)
class TaskScore:
    """One candidate's raw measurements on one task."""

    candidate_id: str
    task_id: str
    metrics: Mapping[str, float]
    kind: str = "candidate"
    "Where the row came from: a real candidate, or a probe. Calibration must not mix the two"
    "(`docs/v050_lessons.md` §1.4)."

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.task_id:
            raise ValueError("candidate_id and task_id are required")
        if not self.metrics:
            raise ValueError("a task score with no metrics records nothing")
        for name, value in self.metrics.items():
            if name.casefold() in DERIVED_METRIC_NAMES:
                raise DerivedMetricError(
                    f"'{name}' is a composite; store the raw per-task metrics and derive it with "
                    f"composite_scores() so a change of weights does not need a re-score"
                )
            if not math.isfinite(value):
                raise ValueError(f"metric '{name}' is not finite")

    def to_json(self) -> str:
        return json.dumps(
            {
                "candidate_id": self.candidate_id,
                "task_id": self.task_id,
                "kind": self.kind,
                "metrics": dict(sorted(self.metrics.items())),
            },
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, line: str) -> TaskScore:
        payload = json.loads(line)
        return cls(
            candidate_id=payload["candidate_id"],
            task_id=payload["task_id"],
            metrics=dict(payload["metrics"]),
            kind=payload.get("kind", "candidate"),
        )


@dataclass
class TaskScoreStore:
    """Append-only JSONL of raw per-task vectors, keyed by (candidate, task).

    Append-only for the same reason the event log is: a re-score that overwrites its predecessor
    destroys the record of what the earlier decision was actually made on. The last row for a key
    wins on read, and the earlier rows stay on disk.
    """

    path: Path
    _cache: list[TaskScore] = field(default_factory=list, repr=False)

    def append(self, scores: Iterable[TaskScore]) -> int:
        rows = list(scores)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(row.to_json() + "\n")
        self._cache = []
        return len(rows)

    def load(self) -> tuple[TaskScore, ...]:
        if self._cache:
            return tuple(self._cache)
        if not self.path.exists():
            return ()
        rows = [
            TaskScore.from_json(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        self._cache = rows
        return tuple(rows)

    def latest(self, *, kind: str | None = "candidate") -> dict[tuple[str, str], TaskScore]:
        latest: dict[tuple[str, str], TaskScore] = {}
        for row in self.load():
            if kind is not None and row.kind != kind:
                continue
            latest[(row.candidate_id, row.task_id)] = row
        return latest

    def candidates(self, *, kind: str | None = "candidate") -> tuple[str, ...]:
        return tuple(sorted({candidate for candidate, _ in self.latest(kind=kind)}))

    def tasks(self, *, kind: str | None = "candidate") -> tuple[str, ...]:
        return tuple(sorted({task for _, task in self.latest(kind=kind)}))

    def metric_vectors(self, metric: str, *, kind: str | None = "candidate") -> dict[str, dict[str, float]]:
        """``{candidate: {task: value}}`` for one raw metric, ready for a paired comparison."""
        vectors: dict[str, dict[str, float]] = {}
        for (candidate, task), row in self.latest(kind=kind).items():
            if metric in row.metrics:
                vectors.setdefault(candidate, {})[task] = row.metrics[metric]
        return vectors


@dataclass(frozen=True)
class TaskGate:
    """A per-task threshold below which most of the score stops counting.

    Real scoring systems are rarely a plain weighted sum. The loading competition zeroes every
    component except fill once a task falls below a placed-item fraction, and a recomputation that
    ignores that reproduces neither the ranking nor the campaign's own numbers. Expressing it here
    keeps the gate in the derivation, where a change of threshold is a recomputation, rather than
    baked into whatever wrote the scores.
    """

    metric: str
    minimum: float
    kept_metrics: tuple[str, ...] = ()

    def passes(self, metrics: Mapping[str, float]) -> bool:
        if self.metric not in metrics:
            raise KeyError(f"gate metric '{self.metric}' is not in the stored vector")
        return metrics[self.metric] >= self.minimum


@dataclass(frozen=True)
class CompositeSpec:
    """How raw per-task metrics combine into the number a decision is made on."""

    weights: Mapping[str, float]
    gate: TaskGate | None = None

    def __post_init__(self) -> None:
        if not self.weights:
            raise ValueError("weights must not be empty")

    def required_metrics(self) -> tuple[str, ...]:
        names = set(self.weights)
        if self.gate is not None:
            names.add(self.gate.metric)
        return tuple(sorted(names))

    def score(self, metrics: Mapping[str, float]) -> float:
        counted = self.weights
        if self.gate is not None and not self.gate.passes(metrics):
            counted = {name: self.weights[name] for name in self.gate.kept_metrics if name in self.weights}
        return sum(weight * metrics[name] for name, weight in counted.items())

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> CompositeSpec:
        """Accept either a bare weight mapping or ``{"weights": ..., "gate": ...}``."""
        if "weights" not in payload:
            return cls(weights={name: float(value) for name, value in payload.items()})
        gate_payload = payload.get("gate")
        gate = (
            TaskGate(
                metric=str(gate_payload["metric"]),
                minimum=float(gate_payload["minimum"]),
                kept_metrics=tuple(str(name) for name in gate_payload.get("kept_metrics", ())),
            )
            if isinstance(gate_payload, Mapping)
            else None
        )
        weights: Mapping[str, Any] = payload["weights"]
        return cls(weights={name: float(value) for name, value in weights.items()}, gate=gate)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"weights": dict(self.weights)}
        if self.gate is not None:
            payload["gate"] = {
                "metric": self.gate.metric,
                "minimum": self.gate.minimum,
                "kept_metrics": list(self.gate.kept_metrics),
            }
        return payload


def per_task_composite(
    scores: Sequence[TaskScore],
    weights: Mapping[str, float] | CompositeSpec,
) -> dict[str, dict[str, float]]:
    """Derive ``{candidate: {task: composite}}`` under one scoring specification.

    Missing metrics are an error rather than a zero: a candidate scored before a metric existed is
    not a candidate that scored zero on it, and silently treating it as one is how a recomputation
    quietly changes a ranking.
    """
    spec = weights if isinstance(weights, CompositeSpec) else CompositeSpec.from_mapping(weights)
    required = spec.required_metrics()
    derived: dict[str, dict[str, float]] = {}
    for row in scores:
        missing = [name for name in required if name not in row.metrics]
        if missing:
            raise KeyError(f"{row.candidate_id}/{row.task_id} is missing metric(s): {', '.join(sorted(missing))}")
        derived.setdefault(row.candidate_id, {})[row.task_id] = spec.score(row.metrics)
    return derived


def composite_scores(
    scores: Sequence[TaskScore],
    weights: Mapping[str, float] | CompositeSpec,
    *,
    tasks: Sequence[str] | None = None,
) -> dict[str, float]:
    """One number per candidate, averaged over ``tasks`` (default: every task it was scored on).

    Pass ``tasks`` whenever candidates were scored on different task sets: an average over
    different tasks is not a comparison, and this is the point at which that goes unnoticed.
    """
    per_task = per_task_composite(scores, weights)
    totals: dict[str, float] = {}
    for candidate, values in per_task.items():
        selected = [values[task] for task in tasks if task in values] if tasks is not None else list(values.values())
        if not selected:
            continue
        totals[candidate] = sum(selected) / len(selected)
    return totals


def recompute(
    store: TaskScoreStore,
    weights: Mapping[str, float] | CompositeSpec,
    *,
    tasks: Sequence[str] | None = None,
) -> dict[str, float]:
    """Re-derive every candidate's composite under new weights, without re-scoring anything."""
    return composite_scores(tuple(store.latest().values()), weights, tasks=tasks)
