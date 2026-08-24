from __future__ import annotations

from dataclasses import dataclass

from epistemic_loop.domain.enums import HoldoutPolicyName
from epistemic_loop.holdout.query_ledger import HoldoutQuery, QueryLedger
from epistemic_loop.holdout.violations import HoldoutViolation, HoldoutViolationError


@dataclass(frozen=True)
class HoldoutResponse:
    passed: bool | None
    score: float | None
    response_kind: str


class HoldoutGate:
    def __init__(
        self,
        run_id: str,
        policy: HoldoutPolicyName,
        ledger: QueryLedger,
        *,
        max_queries: int = 0,
        production: bool = True,
    ):
        if production and policy == HoldoutPolicyName.OPEN_DEBUG:
            raise ValueError("open_debug holdout policy is forbidden in production")
        self.run_id = run_id
        self.policy = policy
        self.ledger = ledger
        self.max_queries = max_queries

    def evaluate(
        self,
        score: float,
        *,
        actor: str,
        threshold: float | None = None,
        reveal_score: bool = False,
    ) -> HoldoutResponse:
        prior_queries = self.ledger.list(self.run_id)
        if self.policy == HoldoutPolicyName.STRICT_BLIND:
            raise HoldoutViolationError(
                HoldoutViolation(
                    run_id=self.run_id,
                    code="STRICT_BLIND_QUERY",
                    description="holdout queries are forbidden before benchmark finalization",
                    actor=actor,
                )
            )
        if self.max_queries and len(prior_queries) >= self.max_queries:
            raise HoldoutViolationError(
                HoldoutViolation(
                    run_id=self.run_id,
                    code="QUERY_BUDGET_EXCEEDED",
                    description="holdout query budget exceeded",
                    actor=actor,
                )
            )
        if self.policy == HoldoutPolicyName.GATED_BINARY:
            if threshold is None:
                raise ValueError("gated_binary requires a preregistered threshold")
            if reveal_score:
                raise HoldoutViolationError(
                    HoldoutViolation(
                        run_id=self.run_id,
                        code="NUMERIC_SCORE_REQUEST",
                        description="gated_binary may return only a threshold result",
                        actor=actor,
                    )
                )
            response = HoldoutResponse(score >= threshold, None, "binary")
        else:
            response = HoldoutResponse(score >= threshold if threshold is not None else None, score, "numeric")
        self.ledger.append(
            HoldoutQuery(
                run_id=self.run_id,
                actor=actor,
                query_kind="threshold" if threshold is not None else "score",
                request={"threshold": threshold, "reveal_score": reveal_score},
                response_kind=response.response_kind,
            )
        )
        return response
