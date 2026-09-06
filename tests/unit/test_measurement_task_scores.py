"""The per-task raw vector is what is stored; the composite is derived (§3 item 4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from epistemic_loop.measurement.task_scores import (
    CompositeSpec,
    DerivedMetricError,
    TaskGate,
    TaskScore,
    TaskScoreStore,
    composite_scores,
    per_task_composite,
    recompute,
)


def _rows() -> list[TaskScore]:
    return [
        TaskScore("cand-a", "t01", {"fill_rate": 0.62, "stability": 0.80}),
        TaskScore("cand-a", "t02", {"fill_rate": 0.58, "stability": 0.40}),
        TaskScore("cand-b", "t01", {"fill_rate": 0.60, "stability": 0.90}),
        TaskScore("cand-b", "t02", {"fill_rate": 0.61, "stability": 0.10}),
    ]


def test_a_change_of_weights_needs_no_rescore(tmp_path: Path) -> None:
    """The whole point (`docs/v050_lessons.md` §1.6): the scoring system changed mid-campaign and
    50 individuals did not have to be re-scored, because the raw vectors were still there."""
    store = TaskScoreStore(tmp_path / "scores.jsonl")
    store.append(_rows())

    before = recompute(store, {"fill_rate": 1.0, "stability": 0.5})
    after = recompute(store, {"fill_rate": 1.0, "stability": 0.0})

    assert before["cand-a"] > before["cand-b"]
    assert after["cand-b"] > after["cand-a"]  # dropping the stability weight reverses the order


def test_storing_a_composite_is_refused() -> None:
    """The rule is enforced, not documented: a stored composite goes stale the moment the weights
    move, and nothing downstream can tell that it has."""
    with pytest.raises(DerivedMetricError, match="composite"):
        TaskScore("cand-a", "t01", {"composite": 58.2})
    with pytest.raises(DerivedMetricError):
        TaskScore("cand-a", "t01", {"Score": 58.2})


def test_the_store_is_append_only_and_the_last_row_for_a_key_wins(tmp_path: Path) -> None:
    store = TaskScoreStore(tmp_path / "scores.jsonl")
    store.append([TaskScore("cand-a", "t01", {"fill_rate": 0.50})])
    store.append([TaskScore("cand-a", "t01", {"fill_rate": 0.62})])

    assert len(store.load()) == 2  # the earlier decision's evidence is still on disk
    assert store.latest()[("cand-a", "t01")].metrics["fill_rate"] == 0.62


def test_metric_vectors_feed_a_paired_comparison(tmp_path: Path) -> None:
    store = TaskScoreStore(tmp_path / "scores.jsonl")
    store.append(_rows())

    vectors = store.metric_vectors("fill_rate")

    assert vectors == {"cand-a": {"t01": 0.62, "t02": 0.58}, "cand-b": {"t01": 0.60, "t02": 0.61}}
    assert store.candidates() == ("cand-a", "cand-b")
    assert store.tasks() == ("t01", "t02")


def test_probe_rows_are_kept_but_never_mixed_into_candidate_fits(tmp_path: Path) -> None:
    """`docs/v050_lessons.md` §1.4: a calibration fitted on truncation probes did not extrapolate
    to the band the real candidates were in. The rows are kept, and separated by kind."""
    store = TaskScoreStore(tmp_path / "scores.jsonl")
    store.append([*_rows(), TaskScore("probe-1", "t01", {"fill_rate": 0.44}, kind="probe")])

    assert store.candidates() == ("cand-a", "cand-b")
    assert store.candidates(kind="probe") == ("probe-1",)
    assert len(store.load()) == 5


def test_a_missing_metric_is_an_error_rather_than_a_zero() -> None:
    rows = [*_rows(), TaskScore("cand-c", "t01", {"fill_rate": 0.99})]

    with pytest.raises(KeyError, match="stability"):
        per_task_composite(rows, {"fill_rate": 1.0, "stability": 0.5})


def test_candidates_are_averaged_over_the_task_set_they_are_compared_on() -> None:
    rows = [*_rows(), TaskScore("cand-a", "t99", {"fill_rate": 1.0, "stability": 1.0})]

    unrestricted = composite_scores(rows, {"fill_rate": 1.0, "stability": 0.0})
    restricted = composite_scores(rows, {"fill_rate": 1.0, "stability": 0.0}, tasks=["t01", "t02"])

    assert unrestricted["cand-a"] == pytest.approx((0.62 + 0.58 + 1.0) / 3)
    assert restricted["cand-a"] == pytest.approx(0.60)


def test_empty_and_malformed_rows_are_refused() -> None:
    with pytest.raises(ValueError):
        TaskScore("", "t01", {"fill_rate": 0.5})
    with pytest.raises(ValueError, match="records nothing"):
        TaskScore("cand-a", "t01", {})
    with pytest.raises(ValueError, match="finite"):
        TaskScore("cand-a", "t01", {"fill_rate": float("nan")})
    with pytest.raises(ValueError):
        per_task_composite(_rows(), {})


def test_round_trips_through_disk(tmp_path: Path) -> None:
    store = TaskScoreStore(tmp_path / "scores.jsonl")
    store.append(_rows())

    reread = TaskScoreStore(tmp_path / "scores.jsonl").load()

    assert reread == tuple(_rows())


def test_a_task_gate_drops_the_components_it_gates_and_keeps_the_rest() -> None:
    """The loading competition zeroes every component except fill below a placed-item fraction.
    A plain weighted sum reproduces neither its ranking nor its own published composite."""
    spec = CompositeSpec(
        weights={"fill_score": 0.6, "cog_score": 0.2, "stability_score": 0.2},
        gate=TaskGate(metric="placed_fraction", minimum=0.48, kept_metrics=("fill_score",)),
    )
    passed = {"fill_score": 50.0, "cog_score": 60.0, "stability_score": 80.0, "placed_fraction": 0.80}
    failed = {**passed, "placed_fraction": 0.30}

    assert spec.score(passed) == pytest.approx(0.6 * 50 + 0.2 * 60 + 0.2 * 80)
    assert spec.score(failed) == pytest.approx(0.6 * 50)


def test_the_gate_metric_is_required_even_though_it_carries_no_weight() -> None:
    spec = CompositeSpec(
        weights={"fill_score": 1.0},
        gate=TaskGate(metric="placed_fraction", minimum=0.48, kept_metrics=("fill_score",)),
    )
    rows = [TaskScore("cand-a", "t01", {"fill_score": 50.0})]

    assert spec.required_metrics() == ("fill_score", "placed_fraction")
    with pytest.raises(KeyError, match="placed_fraction"):
        per_task_composite(rows, spec)


def test_a_specification_round_trips_through_json() -> None:
    spec = CompositeSpec(
        weights={"fill_score": 0.55, "cog_score": 0.15},
        gate=TaskGate(metric="placed_fraction", minimum=0.48, kept_metrics=("fill_score",)),
    )

    restored = CompositeSpec.from_mapping(json.loads(json.dumps(spec.to_dict())))

    assert restored == spec
    # A bare weight mapping is still accepted, so the simple case needs no wrapper.
    assert CompositeSpec.from_mapping({"fill_score": 1.0}).gate is None


def test_lowering_the_gate_threshold_is_a_recomputation_not_a_rescore(tmp_path: Path) -> None:
    store = TaskScoreStore(tmp_path / "scores.jsonl")
    store.append(
        [
            TaskScore("cand-a", "t01", {"fill_score": 40.0, "cog_score": 90.0, "placed_fraction": 0.40}),
            TaskScore("cand-b", "t01", {"fill_score": 45.0, "cog_score": 10.0, "placed_fraction": 0.60}),
        ]
    )
    weights = {"fill_score": 0.6, "cog_score": 0.4}

    strict = recompute(store, CompositeSpec(weights, TaskGate("placed_fraction", 0.48, ("fill_score",))))
    relaxed = recompute(store, CompositeSpec(weights, TaskGate("placed_fraction", 0.30, ("fill_score",))))

    assert strict["cand-b"] > strict["cand-a"]  # cand-a is gated down to fill alone
    assert relaxed["cand-a"] > relaxed["cand-b"]  # with the gate lowered its cog score counts
