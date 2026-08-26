from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from epistemic_loop.domain.models import CollapseMetrics, ExperimentProposal, SemanticExperimentSignature


def semantic_similarity(left: SemanticExperimentSignature, right: SemanticExperimentSignature) -> float:
    fields = ("target_hypotheses", "data_slice", "operation", "observable", "decision_affected")
    scores = []
    for field in fields:
        first = set(getattr(left, field))
        second = set(getattr(right, field))
        scores.append(len(first & second) / len(first | second))
    scores.append(float(left.candidate_producing == right.candidate_producing))
    return sum(scores) / len(scores)


def is_semantic_duplicate(left: ExperimentProposal, right: ExperimentProposal) -> bool:
    if left.semantic_signature is None or right.semantic_signature is None:
        return False
    same = semantic_similarity(left.semantic_signature, right.semantic_signature) == 1.0
    if not same:
        return False
    replication = left.replication or right.replication
    return replication is None


class SemanticDuplicateDetector:
    def __init__(self, *, similarity_threshold: float = 0.85):
        if not 0 <= similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between zero and one")
        self.similarity_threshold = similarity_threshold

    def duplicates(
        self,
        proposal: ExperimentProposal,
        previous: Sequence[ExperimentProposal],
    ) -> tuple[ExperimentProposal, ...]:
        if proposal.semantic_signature is None or proposal.replication is not None:
            return ()
        return tuple(
            item
            for item in previous
            if item.semantic_signature is not None
            and semantic_similarity(proposal.semantic_signature, item.semantic_signature) >= self.similarity_threshold
        )

    def clusters(self, proposals: Sequence[ExperimentProposal]) -> tuple[tuple[str, ...], ...]:
        remaining = {item.id: item for item in proposals if item.semantic_signature is not None}
        clusters: list[tuple[str, ...]] = []
        while remaining:
            seed_id = min(remaining)
            members = {seed_id}
            frontier = [remaining.pop(seed_id)]
            while frontier:
                seed = frontier.pop()
                attached = [
                    identifier
                    for identifier, item in remaining.items()
                    if semantic_similarity(seed.semantic_signature, item.semantic_signature)  # type: ignore[arg-type]
                    >= self.similarity_threshold
                ]
                for identifier in attached:
                    members.add(identifier)
                    frontier.append(remaining.pop(identifier))
            clusters.append(tuple(sorted(members)))
        return tuple(sorted(clusters))


def effective_count(labels: Sequence[str]) -> float:
    if not labels:
        return 0.0
    counts = Counter(labels)
    probabilities = [count / len(labels) for count in counts.values()]
    return math.exp(-sum(value * math.log(value) for value in probabilities))


@dataclass(frozen=True)
class CollapseDecision:
    collapsed: bool
    active_conditions: tuple[str, ...]
    actions: tuple[str, ...]


class CollectiveCollapseDetector:
    """Requires two shared collapse symptoms in two consecutive cycles."""

    ACTIONS = (
        "pause_dominant_semantic_cluster",
        "reallocate_to_unexplored_niches",
        "reinitialize_agent_prompt_and_prior",
        "add_agent_with_different_operators",
        "send_leading_hypothesis_to_falsifier",
        "keep_global_best_hidden",
        "inspect_action_space",
        "generate_missing_tool_or_script",
    )

    def __init__(self) -> None:
        self._history: list[tuple[CollapseMetrics, frozenset[str]]] = []

    def assess(self, metrics: CollapseMetrics) -> CollapseDecision:
        previous = self._history[-1][0] if self._history else None
        conditions = self._conditions(metrics, previous)
        collapsed = False
        if self._history:
            prior_conditions = self._history[-1][1]
            collapsed = len(conditions & prior_conditions) >= 2
        self._history.append((metrics, frozenset(conditions)))
        return CollapseDecision(
            collapsed=collapsed,
            active_conditions=tuple(sorted(conditions)),
            actions=self.ACTIONS if collapsed else (),
        )

    @staticmethod
    def _conditions(metrics: CollapseMetrics, previous: CollapseMetrics | None) -> set[str]:
        conditions = set()
        if metrics.dominant_cluster_fraction >= 0.70:
            conditions.add("dominant_cluster_fraction")
        if metrics.experiment_family_effective_count < 2.0:
            conditions.add("effective_family_count")
        if previous is not None and metrics.qd_niche_occupancy <= previous.qd_niche_occupancy:
            conditions.add("qd_occupancy_stalled")
        if metrics.hypothesis_family_budget_fraction >= 0.50:
            conditions.add("hypothesis_budget_concentration")
        if metrics.mean_agent_proposal_similarity > 0.80:
            conditions.add("mean_agent_similarity")
        return conditions


class MinimumNicheBudget:
    """Protect initial niche allocations from short-term score pruning."""

    def __init__(self, fractions: Mapping[str, float], total_budget: float):
        if total_budget < 0 or abs(sum(fractions.values()) - 1.0) > 1e-6:
            raise ValueError("niche fractions must sum to one and total budget must be non-negative")
        self.minimum = {name: total_budget * fraction for name, fraction in fractions.items()}
        self.spent = dict.fromkeys(fractions, 0.0)

    def charge(self, niche: str, amount: float) -> None:
        if niche not in self.spent or amount < 0:
            raise ValueError("unknown niche or negative charge")
        self.spent[niche] += amount

    def protected(self, niche: str) -> bool:
        if niche not in self.spent:
            raise KeyError(niche)
        return self.spent[niche] < self.minimum[niche]
