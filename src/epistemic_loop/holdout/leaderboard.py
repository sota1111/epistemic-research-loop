from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from epistemic_loop.domain.enums import LeaderboardFeedbackMode
from epistemic_loop.holdout.query_ledger import HoldoutQuery, QueryLedger
from epistemic_loop.holdout.violations import HoldoutViolation, HoldoutViolationError

QUERY_KIND = "leaderboard_public"
PRIVATE_FIELDS = ("private_score", "privateScore")


@dataclass(frozen=True)
class LeaderboardFeedback:
    passed: bool | None
    public_score: float | None
    response_kind: str
    queries_used: int
    queries_remaining: int


def redact_private(payload: dict[str, Any]) -> dict[str, Any]:
    """The private score is the objective, never an input; it must not leave the sealed store."""
    return {key: value for key, value in payload.items() if key not in PRIVATE_FIELDS}


class LeaderboardGate:
    """Budgeted access to the public leaderboard.

    The public score is a finite-sample proxy for the private score. Reading it without a budget
    turns the leaderboard into a training signal, which is exactly what costs private-score rank,
    so every read is ledgered and the default mode returns only a preregistered threshold verdict.
    """

    def __init__(
        self,
        run_id: str,
        mode: LeaderboardFeedbackMode,
        ledger: QueryLedger,
        *,
        max_queries: int = 0,
    ):
        self.run_id = run_id
        self.mode = mode
        self.ledger = ledger
        self.max_queries = max_queries

    def used(self) -> int:
        return sum(item.query_kind == QUERY_KIND for item in self.ledger.list(self.run_id))

    def _violation(self, code: str, description: str, actor: str) -> HoldoutViolationError:
        return HoldoutViolationError(
            HoldoutViolation(run_id=self.run_id, code=code, description=description, actor=actor)
        )

    def evaluate(
        self,
        sealed_payload: dict[str, Any],
        *,
        actor: str,
        threshold: float | None = None,
    ) -> LeaderboardFeedback:
        if self.mode == LeaderboardFeedbackMode.FORBIDDEN:
            raise self._violation(
                "LEADERBOARD_FEEDBACK_FORBIDDEN",
                "public leaderboard feedback is disabled for this run",
                actor,
            )
        used = self.used()
        if used >= self.max_queries:
            raise self._violation(
                "LEADERBOARD_BUDGET_EXCEEDED",
                f"public leaderboard feedback budget of {self.max_queries} is exhausted",
                actor,
            )

        public = redact_private(sealed_payload).get("public_score")
        if public is None:
            raise ValueError("sealed payload does not contain a public_score")
        score = float(public)

        if self.mode == LeaderboardFeedbackMode.GATED_BINARY:
            if threshold is None:
                raise ValueError("gated_binary leaderboard feedback requires a preregistered threshold")
            feedback = LeaderboardFeedback(score >= threshold, None, "binary", used + 1, self.max_queries - used - 1)
        else:
            passed = score >= threshold if threshold is not None else None
            feedback = LeaderboardFeedback(passed, score, "numeric", used + 1, self.max_queries - used - 1)

        self.ledger.append(
            HoldoutQuery(
                run_id=self.run_id,
                actor=actor,
                query_kind=QUERY_KIND,
                request={"threshold": threshold, "mode": self.mode.value},
                response_kind=feedback.response_kind,
            )
        )
        return feedback
