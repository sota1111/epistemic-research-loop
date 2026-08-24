import pytest

from epistemic_loop.domain.enums import HoldoutPolicyName
from epistemic_loop.holdout.gate import HoldoutGate
from epistemic_loop.holdout.query_ledger import QueryLedger
from epistemic_loop.holdout.sealed_store import SealedScoreStore
from epistemic_loop.holdout.violations import HoldoutViolationError


def test_open_debug_is_forbidden_in_production_and_numeric_in_development(tmp_path) -> None:
    ledger = QueryLedger(tmp_path / "ledger.jsonl")
    with pytest.raises(ValueError, match="production"):
        HoldoutGate("run", HoldoutPolicyName.OPEN_DEBUG, ledger)
    gate = HoldoutGate("run", HoldoutPolicyName.OPEN_DEBUG, ledger, production=False)
    response = gate.evaluate(0.7, actor="test")
    assert response.score == 0.7 and response.response_kind == "numeric"


def test_binary_gate_requires_threshold_and_rejects_score_reveal(tmp_path) -> None:
    gate = HoldoutGate(
        "run",
        HoldoutPolicyName.GATED_BINARY,
        QueryLedger(tmp_path / "ledger.jsonl"),
        max_queries=2,
    )
    with pytest.raises(ValueError, match="threshold"):
        gate.evaluate(0.7, actor="test")
    with pytest.raises(HoldoutViolationError, match="threshold result"):
        gate.evaluate(0.7, actor="test", threshold=0.5, reveal_score=True)


def test_sealed_store_refuses_short_token_and_duplicate(tmp_path) -> None:
    store = SealedScoreStore(tmp_path)
    with pytest.raises(ValueError, match="16"):
        store.seal("score", {"score": 1}, "short")
    store.seal("score", {"score": 1}, "long-enough-secret-token")
    assert store.status("score")["sealed"] is True
    assert store.status("missing")["sealed"] is False
    with pytest.raises(FileExistsError):
        store.seal("score", {"score": 2}, "long-enough-secret-token")
