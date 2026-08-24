import pytest
from cryptography.exceptions import InvalidTag

from epistemic_loop.domain.enums import HoldoutPolicyName
from epistemic_loop.holdout.gate import HoldoutGate
from epistemic_loop.holdout.query_ledger import QueryLedger
from epistemic_loop.holdout.sealed_store import SealedScoreStore
from epistemic_loop.holdout.violations import HoldoutViolationError


def test_unseal_requires_correct_evaluator_token(tmp_path) -> None:
    store = SealedScoreStore(tmp_path)
    store.seal("score-1", {"private": 0.8}, "correct-secret-token")
    assert b"0.8" not in (tmp_path / "score-1.sealed").read_bytes()
    with pytest.raises(InvalidTag):
        store.unseal("score-1", "incorrect-secret-token")
    assert store.unseal("score-1", "correct-secret-token") == {"private": 0.8}


def test_strict_blind_never_returns_score(tmp_path) -> None:
    gate = HoldoutGate(
        "run-001",
        HoldoutPolicyName.STRICT_BLIND,
        QueryLedger(tmp_path / "queries.jsonl"),
    )
    with pytest.raises(HoldoutViolationError):
        gate.evaluate(0.8, actor="researcher")


def test_gated_binary_returns_only_threshold_result(tmp_path) -> None:
    gate = HoldoutGate(
        "run-001",
        HoldoutPolicyName.GATED_BINARY,
        QueryLedger(tmp_path / "queries.jsonl"),
        max_queries=1,
    )
    response = gate.evaluate(0.8, actor="evaluator", threshold=0.75)
    assert response.passed is True
    assert response.score is None
    with pytest.raises(HoldoutViolationError):
        gate.evaluate(0.9, actor="evaluator", threshold=0.75)
