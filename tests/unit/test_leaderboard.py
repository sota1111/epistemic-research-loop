from __future__ import annotations

import pytest

from epistemic_loop.domain.enums import LeaderboardFeedbackMode
from epistemic_loop.holdout.leaderboard import LeaderboardGate, redact_private
from epistemic_loop.holdout.query_ledger import QueryLedger
from epistemic_loop.holdout.violations import HoldoutViolationError

SEALED = {"public_score": 0.812, "private_score": 0.798}


def _gate(tmp_path, mode: LeaderboardFeedbackMode, max_queries: int = 2) -> LeaderboardGate:
    return LeaderboardGate(
        "run-001",
        mode,
        QueryLedger(tmp_path / "leaderboard.jsonl"),
        max_queries=max_queries,
    )


def test_private_score_is_never_exposed() -> None:
    assert redact_private(SEALED) == {"public_score": 0.812}
    assert redact_private({"privateScore": 1.0, "publicScore": 0.5}) == {"publicScore": 0.5}


def test_forbidden_mode_blocks_every_read(tmp_path) -> None:
    with pytest.raises(HoldoutViolationError) as error:
        _gate(tmp_path, LeaderboardFeedbackMode.FORBIDDEN).evaluate(SEALED, actor="agent")
    assert error.value.violation.code == "LEADERBOARD_FEEDBACK_FORBIDDEN"


def test_gated_binary_returns_only_a_threshold_verdict(tmp_path) -> None:
    gate = _gate(tmp_path, LeaderboardFeedbackMode.GATED_BINARY)
    feedback = gate.evaluate(SEALED, actor="evaluator", threshold=0.80)
    assert feedback.passed is True
    assert feedback.public_score is None
    assert feedback.response_kind == "binary"
    assert (feedback.queries_used, feedback.queries_remaining) == (1, 1)


def test_gated_binary_requires_a_preregistered_threshold(tmp_path) -> None:
    gate = _gate(tmp_path, LeaderboardFeedbackMode.GATED_BINARY)
    with pytest.raises(ValueError, match="requires a preregistered threshold"):
        gate.evaluate(SEALED, actor="evaluator")
    assert gate.used() == 0


def test_numeric_mode_reveals_the_public_score_only(tmp_path) -> None:
    feedback = _gate(tmp_path, LeaderboardFeedbackMode.NUMERIC).evaluate(SEALED, actor="evaluator", threshold=0.90)
    assert feedback.public_score == pytest.approx(0.812)
    assert feedback.passed is False
    assert feedback.response_kind == "numeric"


def test_budget_is_enforced_and_ledgered(tmp_path) -> None:
    gate = _gate(tmp_path, LeaderboardFeedbackMode.NUMERIC, max_queries=2)
    gate.evaluate(SEALED, actor="evaluator")
    gate.evaluate(SEALED, actor="evaluator")
    assert gate.used() == 2
    with pytest.raises(HoldoutViolationError) as error:
        gate.evaluate(SEALED, actor="evaluator")
    assert error.value.violation.code == "LEADERBOARD_BUDGET_EXCEEDED"
    assert gate.used() == 2


def test_zero_budget_refuses_the_first_read(tmp_path) -> None:
    with pytest.raises(HoldoutViolationError):
        _gate(tmp_path, LeaderboardFeedbackMode.NUMERIC, max_queries=0).evaluate(SEALED, actor="agent")


def test_missing_public_score_is_a_payload_error(tmp_path) -> None:
    gate = _gate(tmp_path, LeaderboardFeedbackMode.NUMERIC)
    with pytest.raises(ValueError, match="does not contain a public_score"):
        gate.evaluate({"private_score": 0.7}, actor="evaluator")
