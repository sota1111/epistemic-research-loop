"""Layer-2 taxonomy: what has been seen often enough, and widely enough, to be a class.

`docs/v050_course_correction.md` §3 items 9 and 10.

The layer-2 taxonomy was named "data-format independent" and promoted classes on two
competitions. Both competitions were tabular. A class observed twice inside one problem class is
evidence about that problem class, and calling it format-independent is a claim the evidence does
not carry -- the same mistake, one level up, as reading a ranking off twelve tasks.

So the bar moved and it is checked here rather than asserted in prose:

* **two distinct problem classes**, not two competitions. This is the whole change. Tabular
  prediction and algorithm submission are different problem classes; IEEE-CIS and Santander are
  not.
* **two distinct competitions**, retained from the old rule.
* **two distinct agent models**, when every observation came from an agent. A pattern seen only
  under one model is a property of that model until something else reproduces it -- the reason the
  "beyond additive marginals" candidate was never promoted.
* only **direct** observations count. An observation recorded as `arguable` is kept, because
  hiding it would lose the record, but it cannot promote anything on its own.

Applying this rule demotes classes that were already promoted. That is the point of raising a bar,
and the demotions are the finding, not a failure of the registry.

**Controller-owned.** Nothing here may be copied into a prompt, a contract, or any agent-visible
file: a taxonomy handed to the agents being measured stops measuring them.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Strength = Literal["direct", "arguable"]
Layer = Literal["solution", "apparatus"]
Status = Literal["promoted", "candidate"]


@dataclass(frozen=True)
class Observation:
    """One recorded sighting of a class, with everything the promotion rule needs to weigh it."""

    competition: str
    problem_class: str
    source: str
    strength: Strength = "direct"
    agent_model: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.competition or not self.problem_class or not self.source:
            raise ValueError("an observation needs a competition, a problem class and a source")
        if self.strength not in ("direct", "arguable"):
            raise ValueError(f"unknown strength: {self.strength}")


@dataclass(frozen=True)
class PromotionRule:
    """The bar, as data. Raising it means changing these numbers and re-running the assessment."""

    minimum_problem_classes: int = 2
    minimum_competitions: int = 2
    minimum_agent_models: int = 2

    def assess(self, observations: Sequence[Observation]) -> Assessment:
        direct = [item for item in observations if item.strength == "direct"]
        problem_classes = sorted({item.problem_class for item in direct})
        competitions = sorted({item.competition for item in direct})
        models = sorted({item.agent_model for item in direct if item.agent_model})
        reasons: list[str] = []
        if len(problem_classes) < self.minimum_problem_classes:
            reasons.append(
                f"direct observations span {len(problem_classes)} problem class(es) "
                f"({', '.join(problem_classes) or 'none'}); {self.minimum_problem_classes} required"
            )
        if len(competitions) < self.minimum_competitions:
            reasons.append(
                f"direct observations span {len(competitions)} competition(s); {self.minimum_competitions} required"
            )
        # Only binding when every direct observation names a model: a class seen in the scoring
        # apparatus rather than in an agent's output has no model to vary.
        if direct and all(item.agent_model for item in direct) and len(models) < self.minimum_agent_models:
            reasons.append(
                f"every direct observation came from {len(models)} agent model(s) ({', '.join(models)}); "
                f"{self.minimum_agent_models} required before this is a property of the problem rather "
                f"than of the model"
            )
        return Assessment(
            status="candidate" if reasons else "promoted",
            problem_classes=tuple(problem_classes),
            competitions=tuple(competitions),
            agent_models=tuple(models),
            direct_observations=len(direct),
            arguable_observations=len(observations) - len(direct),
            reasons=tuple(reasons),
        )


@dataclass(frozen=True)
class Assessment:
    status: Status
    problem_classes: tuple[str, ...]
    competitions: tuple[str, ...]
    agent_models: tuple[str, ...]
    direct_observations: int
    arguable_observations: int
    reasons: tuple[str, ...]

    @property
    def promoted(self) -> bool:
        return self.status == "promoted"


@dataclass(frozen=True)
class TechniqueClass:
    id: str
    title: str
    layer: Layer
    observations: tuple[Observation, ...] = ()
    #: What this class was before the rule changed, so a demotion stays visible in the record.
    previous_status: Status | None = None

    def assess(self, rule: PromotionRule) -> Assessment:
        return rule.assess(self.observations)


@dataclass(frozen=True)
class Registry:
    rule: PromotionRule
    classes: tuple[TechniqueClass, ...] = ()
    source: Path | None = field(default=None, compare=False)

    def assessments(self) -> dict[str, Assessment]:
        return {item.id: item.assess(self.rule) for item in self.classes}

    def promoted(self, layer: Layer | None = None) -> tuple[TechniqueClass, ...]:
        assessments = self.assessments()
        return tuple(
            item for item in self.classes if assessments[item.id].promoted and (layer is None or item.layer == layer)
        )

    def demoted(self) -> tuple[TechniqueClass, ...]:
        """Classes the old bar promoted and this one does not. The cost of raising the bar."""
        assessments = self.assessments()
        return tuple(
            item for item in self.classes if item.previous_status == "promoted" and not assessments[item.id].promoted
        )


def load_registry(path: Path) -> Registry:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rule = PromotionRule(**payload.get("promotion_rule", {}))
    classes = tuple(
        TechniqueClass(
            id=entry["id"],
            title=entry["title"],
            layer=entry["layer"],
            observations=tuple(Observation(**observation) for observation in entry.get("observations", [])),
            previous_status=entry.get("previous_status"),
        )
        for entry in payload.get("classes", [])
    )
    identifiers = [item.id for item in classes]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate class ids in the registry")
    return Registry(rule=rule, classes=classes, source=Path(path))


def summarize(registry: Registry) -> list[dict[str, object]]:
    """One row per class, ready to print or serialise. Reasons are kept for candidates."""
    assessments = registry.assessments()
    rows: list[dict[str, object]] = []
    for item in registry.classes:
        assessment = assessments[item.id]
        rows.append(
            {
                "id": item.id,
                "title": item.title,
                "layer": item.layer,
                "status": assessment.status,
                "previous_status": item.previous_status,
                "demoted": item.previous_status == "promoted" and not assessment.promoted,
                "problem_classes": list(assessment.problem_classes),
                "competitions": list(assessment.competitions),
                "agent_models": list(assessment.agent_models),
                "direct_observations": assessment.direct_observations,
                "arguable_observations": assessment.arguable_observations,
                "reasons": list(assessment.reasons),
            }
        )
    return rows


def problem_classes(observations: Iterable[Observation]) -> tuple[str, ...]:
    return tuple(sorted({item.problem_class for item in observations}))
