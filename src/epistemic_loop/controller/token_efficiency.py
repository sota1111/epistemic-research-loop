from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from epistemic_loop.domain.models import SemanticExperimentSignature


@dataclass(frozen=True)
class TokenEfficiencyMetrics:
    tokens_per_completed_experiment: float | None
    tokens_per_valid_candidate: float | None
    tokens_per_new_semantic_family: float | None
    tokens_per_private_score_improvement: float | None


class TokenBudgetLedger:
    """Bound proposal/cluster spend and reserve tokens for candidate production."""

    def __init__(
        self,
        *,
        total_tokens: int,
        proposal_token_limit: int,
        semantic_cluster_token_limit: int,
        candidate_reserve_fraction: float = 0.35,
    ):
        if min(total_tokens, proposal_token_limit, semantic_cluster_token_limit) <= 0:
            raise ValueError("token budgets must be positive")
        if not 0 <= candidate_reserve_fraction <= 1:
            raise ValueError("candidate reserve fraction must be between zero and one")
        self.total_tokens = total_tokens
        self.proposal_limit = proposal_token_limit
        self.cluster_limit = semantic_cluster_token_limit
        self.candidate_reserve = int(total_tokens * candidate_reserve_fraction)
        self.spent = 0
        self.candidate_spent = 0
        self.by_cluster: dict[str, int] = {}
        self.completed = 0
        self.valid_candidates = 0
        self.semantic_families: set[str] = set()
        self.private_score_improvement = 0.0

    def authorize(
        self,
        signature: SemanticExperimentSignature,
        *,
        requested_tokens: int,
        candidate_producing: bool,
    ) -> str:
        if requested_tokens <= 0 or requested_tokens > self.proposal_limit:
            raise ValueError("proposal token limit exceeded")
        key = self.cluster_key(signature)
        if self.by_cluster.get(key, 0) + requested_tokens > self.cluster_limit:
            raise ValueError("semantic cluster token limit exceeded")
        if self.spent + requested_tokens > self.total_tokens:
            raise ValueError("total token budget exceeded")
        unspent_candidate_reserve = max(0, self.candidate_reserve - self.candidate_spent)
        if not candidate_producing and self.total_tokens - (self.spent + requested_tokens) < unspent_candidate_reserve:
            raise ValueError("candidate-producing token reserve would be consumed")
        return key

    def charge(
        self,
        signature: SemanticExperimentSignature,
        *,
        tokens: int,
        candidate_producing: bool,
        completed: bool,
        valid_candidate: bool = False,
        private_score_improvement: float = 0.0,
    ) -> None:
        key = self.authorize(signature, requested_tokens=tokens, candidate_producing=candidate_producing)
        self.spent += tokens
        self.by_cluster[key] = self.by_cluster.get(key, 0) + tokens
        self.semantic_families.add(key)
        if candidate_producing:
            self.candidate_spent += tokens
        self.completed += int(completed)
        self.valid_candidates += int(valid_candidate)
        self.private_score_improvement += max(0.0, private_score_improvement)

    def metrics(self) -> TokenEfficiencyMetrics:
        return TokenEfficiencyMetrics(
            tokens_per_completed_experiment=_ratio(self.spent, self.completed),
            tokens_per_valid_candidate=_ratio(self.spent, self.valid_candidates),
            tokens_per_new_semantic_family=_ratio(self.spent, len(self.semantic_families)),
            tokens_per_private_score_improvement=(
                self.spent / self.private_score_improvement if self.private_score_improvement > 0 else None
            ),
        )

    @staticmethod
    def cluster_key(signature: SemanticExperimentSignature) -> str:
        canonical = json.dumps(signature.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


def _ratio(tokens: int, count: int) -> float | None:
    return tokens / count if count else None
