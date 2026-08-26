from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from epistemic_loop.domain.models import QDCandidate

Genome = TypeVar("Genome")


@dataclass(frozen=True)
class Individual(Generic[Genome]):
    id: str
    genome: Genome
    quality: float


class EvolutionarySearch(Generic[Genome]):
    """Budget-neutral mutation/crossover engine used by System B and above.

    Competition-specific genomes remain outside the orchestrator. The engine
    owns only parent selection and the mutation/crossover schedule, making it
    reusable for model configs, feature sets, or representation programs.
    """

    def __init__(self, population: Sequence[Individual[Genome]], *, seed: int):
        if not population:
            raise ValueError("evolutionary search requires a non-empty population")
        self.population = tuple(population)
        self.random = random.Random(seed)

    def ask(
        self,
        count: int,
        *,
        mutate: Callable[[Genome, random.Random], Genome],
        crossover: Callable[[Genome, Genome, random.Random], Genome],
        crossover_probability: float = 0.35,
    ) -> list[Genome]:
        if count < 1:
            return []
        if not 0 <= crossover_probability <= 1:
            raise ValueError("crossover_probability must be between 0 and 1")
        weights = _rank_weights(self.population)
        children: list[Genome] = []
        for _ in range(count):
            left = self.random.choices(self.population, weights=weights, k=1)[0]
            genome = left.genome
            if len(self.population) > 1 and self.random.random() < crossover_probability:
                right = self.random.choices(self.population, weights=weights, k=1)[0]
                genome = crossover(genome, right.genome, self.random)
            children.append(mutate(genome, self.random))
        return children

    def parent_sets(self, count: int, *, crossover_probability: float = 0.35) -> list[tuple[str, ...]]:
        """Return reproducible parent lineages for an external genome mutator."""

        if count < 1:
            return []
        if not 0 <= crossover_probability <= 1:
            raise ValueError("crossover_probability must be between 0 and 1")
        weights = _rank_weights(self.population)
        result: list[tuple[str, ...]] = []
        for _ in range(count):
            left = self.random.choices(self.population, weights=weights, k=1)[0]
            if len(self.population) > 1 and self.random.random() < crossover_probability:
                alternatives = [item for item in self.population if item.id != left.id]
                alternative_weights = [weights[self.population.index(item)] for item in alternatives]
                right = self.random.choices(alternatives, weights=alternative_weights, k=1)[0]
                result.append((left.id, right.id))
            else:
                result.append((left.id,))
        return result


def _rank_weights(population: Sequence[Individual[Genome]]) -> list[int]:
    order = {item.id: rank for rank, item in enumerate(sorted(population, key=lambda item: item.quality))}
    return [order[item.id] + 1 for item in population]


def evolution_directives(
    candidates: Sequence[QDCandidate],
    *,
    count: int,
    seed: int,
    crossover_probability: float = 0.35,
) -> list[dict[str, object]]:
    """Select parents while leaving competition-specific mutation to the solver."""

    if not candidates or count < 1:
        return []
    population = [
        Individual(
            id=item.id,
            genome=item.id,
            quality=(
                item.expected_hidden_score
                + 0.15 * item.robustness
                + 0.15 * item.error_diversity
                - item.score_variance
                - 0.1 * item.normalized_cost
                - item.leakage_risk
            ),
        )
        for item in candidates
    ]
    parent_sets = EvolutionarySearch(population, seed=seed).parent_sets(
        count,
        crossover_probability=crossover_probability,
    )
    by_id = {item.id: item for item in candidates}
    return [
        {
            "variation_operator": "crossover" if len(parent_ids) == 2 else "mutation",
            "parent_candidate_ids": list(parent_ids),
            "parent_experiment_ids": [by_id[identifier].experiment_id for identifier in parent_ids],
        }
        for parent_ids in parent_sets
    ]
