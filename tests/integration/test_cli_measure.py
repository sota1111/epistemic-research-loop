"""`erlctl measure` is the comparator that belongs in front of a selection step.

`docs/v050_course_correction.md` §3 items 2-4. The gate is only worth having if it is reachable
from where selection actually happens, so the same refusal is asserted here through the CLI.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

from typer.testing import CliRunner

from epistemic_loop.cli import app
from epistemic_loop.measurement.task_scores import TaskScore, TaskScoreStore

CAMPAIGN_SPREAD = 16.33


def _write_scores(path: Path, offsets: dict[str, float], *, tasks: int, spread: float) -> None:
    normal = statistics.NormalDist()
    pattern = [normal.inv_cdf((index + 0.5) / tasks) for index in range(tasks)]
    scale = statistics.pstdev(pattern)
    pattern = [value / scale for value in pattern]
    rows = []
    for rotation, (candidate, offset) in enumerate(offsets.items()):
        rotated = pattern[rotation * 3 :] + pattern[: rotation * 3]
        for index in range(tasks):
            rows.append(
                TaskScore(
                    candidate,
                    f"t{index:04d}",
                    {"fill_rate": 40.0 + offset + spread * rotated[index], "stability": 10.0 - offset},
                )
            )
    TaskScoreStore(path).append(rows)


def test_rank_returns_tiers_and_refuses_a_total_order_inside_the_noise(tmp_path: Path) -> None:
    scores = tmp_path / "scores.jsonl"
    _write_scores(scores, {"a": 2.0, "b": 0.0}, tasks=12, spread=CAMPAIGN_SPREAD / math.sqrt(2))

    result = CliRunner().invoke(app, ["measure", "rank", "--scores", str(scores), "--metric", "fill_rate"])
    payload = json.loads(result.output)

    assert result.exit_code == 0, result.output
    assert payload["resolved"] is False
    assert payload["tiers"] == [["a", "b"]]
    assert payload["undecided_pairs"] == [["a", "b"]]

    strict = CliRunner().invoke(app, ["measure", "rank", "--scores", str(scores), "--metric", "fill_rate", "--strict"])
    assert strict.exit_code == 2
    assert json.loads(strict.output)["total_order"] is None


def test_rank_orders_a_difference_the_task_count_can_see(tmp_path: Path) -> None:
    scores = tmp_path / "scores.jsonl"
    _write_scores(scores, {"a": 12.0, "b": 0.0}, tasks=64, spread=CAMPAIGN_SPREAD / math.sqrt(2))

    result = CliRunner().invoke(app, ["measure", "rank", "--scores", str(scores), "--metric", "fill_rate", "--strict"])
    payload = json.loads(result.output)

    assert result.exit_code == 0, result.output
    assert payload["total_order"] == ["a", "b"]


def test_compare_reports_no_winner_when_the_interval_spans_zero(tmp_path: Path) -> None:
    scores = tmp_path / "scores.jsonl"
    _write_scores(scores, {"a": 2.0, "b": 0.0}, tasks=12, spread=CAMPAIGN_SPREAD / math.sqrt(2))

    result = CliRunner().invoke(
        app,
        ["measure", "compare", "--scores", str(scores), "--left", "a", "--right", "b", "--metric", "fill_rate"],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 0, result.output
    assert payload["better"] is None
    assert payload["interval"][0] <= 0 <= payload["interval"][1]


def test_plan_states_the_task_count_a_difference_needs() -> None:
    result = CliRunner().invoke(app, ["measure", "plan", "--difference", "5"])
    payload = json.loads(result.output)

    assert payload["required_tasks"] == 41
    assert payload["affordable"]["iteration"]["ok"] is False
    assert payload["affordable"]["selection"]["ok"] is True
    assert payload["throughput_ratio"] == 4.0


def test_recompute_derives_new_composites_without_rescoring(tmp_path: Path) -> None:
    scores = tmp_path / "scores.jsonl"
    _write_scores(scores, {"a": 6.0, "b": 0.0}, tasks=8, spread=1.0)

    with_stability = CliRunner().invoke(
        app,
        [
            "measure",
            "recompute",
            "--scores",
            str(scores),
            "--weights",
            json.dumps({"fill_rate": 1.0, "stability": 4.0}),
        ],
    )
    without = CliRunner().invoke(
        app,
        [
            "measure",
            "recompute",
            "--scores",
            str(scores),
            "--weights",
            json.dumps({"fill_rate": 1.0, "stability": 0.0}),
        ],
    )

    assert with_stability.exit_code == 0, with_stability.output
    first = json.loads(with_stability.output)["composites"]
    second = json.loads(without.output)["composites"]
    assert first["b"] > first["a"]  # stability weighted heavily reverses the order
    assert second["a"] > second["b"]


def test_a_composite_ranking_goes_through_the_same_gate(tmp_path: Path) -> None:
    scores = tmp_path / "scores.jsonl"
    _write_scores(scores, {"a": 2.0, "b": 0.0}, tasks=12, spread=CAMPAIGN_SPREAD / math.sqrt(2))

    result = CliRunner().invoke(
        app,
        [
            "measure",
            "rank",
            "--scores",
            str(scores),
            "--weights",
            json.dumps({"fill_rate": 1.0, "stability": 0.0}),
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["resolved"] is False


def test_unknown_candidates_and_metrics_are_rejected(tmp_path: Path) -> None:
    scores = tmp_path / "scores.jsonl"
    _write_scores(scores, {"a": 1.0, "b": 0.0}, tasks=4, spread=1.0)

    unknown_metric = CliRunner().invoke(app, ["measure", "rank", "--scores", str(scores), "--metric", "nope"])
    unknown_candidate = CliRunner().invoke(
        app,
        ["measure", "compare", "--scores", str(scores), "--left", "a", "--right", "z", "--metric", "fill_rate"],
    )

    assert unknown_metric.exit_code != 0
    assert unknown_candidate.exit_code != 0
