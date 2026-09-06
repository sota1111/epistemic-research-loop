"""The layer-2 promotion bar, and what raising it costs (§3 items 9 and 10).

The registry in `docs/controller_reference/layer2_registry.json` is checked here rather than
described in prose, because the failure it guards against is precisely a class being called
problem-independent in a document while its evidence sits inside one problem class.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from epistemic_loop.taxonomy.layer2 import (
    Observation,
    PromotionRule,
    TechniqueClass,
    load_registry,
    summarize,
)

REGISTRY = Path(__file__).resolve().parents[2] / "docs" / "controller_reference" / "layer2_registry.json"


def _observation(**overrides: object) -> Observation:
    payload: dict[str, object] = {
        "competition": "IEEE-CIS",
        "problem_class": "tabular_prediction",
        "source": "docs/verification/example.md",
        "strength": "direct",
    }
    payload.update(overrides)
    return Observation(**payload)  # type: ignore[arg-type]


def test_two_competitions_in_one_problem_class_no_longer_promote() -> None:
    """The old bar. Two tabular competitions were called evidence of format independence."""
    item = TechniqueClass(
        id="context_pooling",
        title="context pooling",
        layer="solution",
        observations=(
            _observation(competition="IEEE-CIS", agent_model="opus"),
            _observation(competition="Santander", agent_model="opus"),
        ),
    )

    assessment = item.assess(PromotionRule())

    assert assessment.status == "candidate"
    assert any("problem class" in reason for reason in assessment.reasons)


def test_two_problem_classes_promote() -> None:
    item = TechniqueClass(
        id="slope",
        title="local differences are exaggerated",
        layer="apparatus",
        observations=(
            _observation(competition="IEEE-CIS", problem_class="tabular_prediction"),
            _observation(competition="NEDO", problem_class="algorithm_submission"),
        ),
    )

    assert item.assess(PromotionRule()).promoted is True


def test_a_pattern_seen_under_one_model_only_stays_a_candidate() -> None:
    """A property of one model until something else reproduces it -- why `beyond additive
    marginals` was never promoted despite spanning two competitions."""
    item = TechniqueClass(
        id="beyond_additive",
        title="limits of additivity",
        layer="solution",
        observations=(
            _observation(competition="IEEE-CIS", problem_class="tabular_prediction", agent_model="sol"),
            _observation(competition="NEDO", problem_class="algorithm_submission", agent_model="sol"),
        ),
    )

    assessment = item.assess(PromotionRule())

    assert assessment.status == "candidate"
    assert any("agent model" in reason for reason in assessment.reasons)


def test_the_model_rule_does_not_bind_observations_with_no_agent_behind_them() -> None:
    """A defect in the scoring apparatus has no model to vary; requiring two would be nonsense."""
    item = TechniqueClass(
        id="apparatus",
        title="local metric measures something else",
        layer="apparatus",
        observations=(
            _observation(competition="IEEE-CIS", problem_class="tabular_prediction"),
            _observation(competition="NEDO", problem_class="algorithm_submission"),
        ),
    )

    assert item.assess(PromotionRule()).promoted is True


def test_arguable_observations_are_kept_but_cannot_promote() -> None:
    item = TechniqueClass(
        id="blind_spot",
        title="unspanned axis",
        layer="apparatus",
        observations=(
            _observation(competition="NEDO", problem_class="algorithm_submission"),
            _observation(competition="IEEE-CIS", problem_class="tabular_prediction", strength="arguable"),
        ),
    )

    assessment = item.assess(PromotionRule())

    assert assessment.status == "candidate"
    assert assessment.direct_observations == 1
    assert assessment.arguable_observations == 1  # kept in the record, not counted toward the bar


def test_the_committed_registry_demotes_the_two_classes_the_old_bar_promoted() -> None:
    registry = load_registry(REGISTRY)

    assert {item.id for item in registry.demoted()} == {"context_pooling", "occurrence_sparsity_profile"}


def test_the_committed_registry_promotes_two_apparatus_classes_and_no_solution_class() -> None:
    registry = load_registry(REGISTRY)

    promoted = {item.id for item in registry.promoted()}

    assert promoted == {"local_metric_measures_something_else", "local_differences_are_exaggerated"}
    assert registry.promoted(layer="solution") == ()
    # Section 3 item 10 claimed three apparatus classes were observed in two problem classes.
    # Applied mechanically, the third is not: its direct evidence is all from one problem class.
    rows = {row["id"]: row for row in summarize(registry)}
    assert rows["unspanned_axis_is_an_apparatus_blind_spot"]["status"] == "candidate"
    assert rows["unspanned_axis_is_an_apparatus_blind_spot"]["arguable_observations"] == 1


def test_every_registry_observation_cites_a_source_that_exists() -> None:
    """A taxonomy whose citations do not resolve is a taxonomy nobody can check."""
    root = REGISTRY.resolve().parents[2]
    registry = load_registry(REGISTRY)

    for item in registry.classes:
        for observation in item.observations:
            path = observation.source.split(" ")[0]
            assert (root / path).exists(), f"{item.id}: {path} does not exist"


def test_malformed_observations_are_refused() -> None:
    with pytest.raises(ValueError, match="needs a competition"):
        Observation(competition="", problem_class="tabular_prediction", source="x")
    with pytest.raises(ValueError, match="unknown strength"):
        _observation(strength="probably")
