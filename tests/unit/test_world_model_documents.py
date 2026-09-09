"""The world-model documents quote the fitted artifacts, and the quotes still hold.

`docs/world_model/README.md` is the front door and states the numbers a reader will act on. The
fits are re-runnable (`scripts/fit_world_model.py`, `scripts/fit_world_model_counterexample.py`),
so the failure this guards against is a document that keeps quoting a fit that no longer exists --
which is worse than no document, because it reads exactly like a current one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORLD_MODEL = ROOT / "docs" / "world_model"
README = (WORLD_MODEL / "README.md").read_text(encoding="utf-8")


def _artifact(name: str) -> dict:
    return json.loads((WORLD_MODEL / name).read_text(encoding="utf-8"))


def test_the_primary_verdict_is_quoted_as_fitted() -> None:
    validation = _artifact("world_model.json")["validation"]

    assert validation["separable"] is True
    for value in ("0.8462", "0.8745", "+0.0283", "[+0.0121, +0.0466]"):
        assert value in README, value
    assert f"{validation['checklist_accuracy']:.4f}" in README
    assert f"{validation['context_accuracy']:.4f}" in README


def test_the_counterexample_model_is_quoted_as_rejected() -> None:
    validation = _artifact("world_model_counterexample.json")["validation"]

    assert validation["adopted_as_point_predictor"] is False
    assert validation["counterexample_recall"] == [0, 6]
    assert validation["decisive_recall"] == [24, 78]
    assert validation["primary_decisive_recall"] == [31, 78]
    for value in ("0.8664", "−0.0081", "[−0.0223, +0.0061]", "+0.0103", "[+0.0027, +0.0174]"):
        assert value in README, value
    assert "0/6" in README and "24/78" in README and "31/78" in README


def test_the_states_the_corpus_never_observed_are_named() -> None:
    artifact = _artifact("world_model_counterexample.json")

    assert artifact["unobserved_states"] == ["HCAL", "FC"]
    for state in ("Hypothesis Calibration", "Falsification Coverage"):
        assert state in README
    assert artifact["states"]["HCAL"]["observed"]["decisive"] == 0
    assert artifact["states"]["FC"]["observed"]["decisive"] == 0


def test_the_direction_figures_that_carry_the_counterexample_are_quoted() -> None:
    """`p_minus` is what stops the model being a checklist; the front door quotes three of them."""
    states = _artifact("world_model_counterexample.json")["states"]

    assert states["PB"]["global"]["p_minus"] == pytest.approx(0.75)
    assert states["SED"]["global"]["p_minus"] == pytest.approx(0.3333, abs=1e-4)
    assert states["RMC"]["global"]["p_minus"] == pytest.approx(0.1154, abs=1e-4)
    for value in ("0.75", "0.33", "0.12"):
        assert value in README, value


def test_the_nedo_prediction_and_its_empty_cell_are_quoted() -> None:
    prediction = _artifact("prediction_nedo.json")
    decisive = [row for row in prediction["states"] if row["context_prediction"] == "1"]

    assert prediction["cell"] == "0,1,1"
    assert prediction["cell_observed_in_corpus"] is False
    assert [row["state"] for row in decisive] == ["RMC"]
    assert decisive[0]["p_decisive"] == pytest.approx(0.561, abs=1e-3)
    assert "(0,1,1)" in README
    assert "0.561" in README


def test_the_corpus_covers_six_of_the_eight_context_cells() -> None:
    corpus = json.loads((WORLD_MODEL / "corpus_coding.json").read_text(encoding="utf-8"))

    cells = {
        (item["ctx"]["temporal"], item["ctx"]["entity"], item["ctx"]["decomposable"]) for item in corpus["competitions"]
    }

    assert len(corpus["competitions"]) == 38
    assert len(cells) == 6
    assert (0, 1, 1) not in cells  # NEDO's cell
    assert (1, 0, 1) not in cells
    assert "8 セル中 6 セル" in README


def test_the_front_door_keeps_the_rules_that_govern_use() -> None:
    """Three constraints a reader must not miss: read it as a distribution, never show it to an
    agent, and do not promote a single-coder fit into a default."""
    assert "Controller 専有" in README
    assert "分布として読む" in README
    assert "Preferred State の既定値にしない" in README
