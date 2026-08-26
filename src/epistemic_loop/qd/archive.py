from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from epistemic_loop.domain.models import QDArchiveEntry, QDCandidate
from epistemic_loop.qd.descriptors import ALL_DESCRIPTORS, cell_key


def candidate_quality(
    candidate: QDCandidate,
    *,
    variance_lambda: float = 1.0,
    cost_lambda: float = 0.1,
    leakage_lambda: float = 1.0,
) -> float:
    """Quality is always expressed on a higher-is-better normalized score."""

    return (
        candidate.expected_hidden_score
        - variance_lambda * candidate.score_variance
        - cost_lambda * candidate.normalized_cost
        - leakage_lambda * candidate.leakage_risk
    )


@dataclass(frozen=True)
class ArchiveUpdate:
    candidate_id: str
    cell_key: str
    retained: bool
    replaced_slots: tuple[str, ...]
    reason: str


class QDArchive:
    """MAP-Elites-style archive with four useful elites per descriptor cell.

    The object is a deterministic projection: callers persist candidates as
    events and can rebuild this archive from them in any process.
    """

    def __init__(
        self,
        descriptor_names: Sequence[str] = ALL_DESCRIPTORS,
        *,
        maximum_size: int = 100,
        quality_floor_relative_to_best: float = 0.97,
        variance_lambda: float = 1.0,
        cost_lambda: float = 0.1,
        leakage_lambda: float = 1.0,
    ):
        unknown = set(descriptor_names) - set(ALL_DESCRIPTORS)
        if unknown or not descriptor_names:
            raise ValueError(f"invalid QD descriptors: {sorted(unknown)}")
        if maximum_size < 1:
            raise ValueError("maximum_size must be positive")
        if not 0 <= quality_floor_relative_to_best <= 1:
            raise ValueError("quality_floor_relative_to_best must be between 0 and 1")
        self.descriptor_names = tuple(descriptor_names)
        self.maximum_size = maximum_size
        self.quality_floor_relative_to_best = quality_floor_relative_to_best
        self.variance_lambda = variance_lambda
        self.cost_lambda = cost_lambda
        self.leakage_lambda = leakage_lambda
        self._candidates: dict[str, QDCandidate] = {}
        self._cells: dict[str, QDArchiveEntry] = {}

    @classmethod
    def rebuild(cls, candidates: Iterable[QDCandidate], **kwargs: object) -> QDArchive:
        archive = cls(**kwargs)  # type: ignore[arg-type]
        for candidate in sorted(candidates, key=lambda item: (item.created_at, item.id)):
            archive.add(candidate)
        return archive

    def quality(self, candidate: QDCandidate) -> float:
        return candidate_quality(
            candidate,
            variance_lambda=self.variance_lambda,
            cost_lambda=self.cost_lambda,
            leakage_lambda=self.leakage_lambda,
        )

    @property
    def entries(self) -> tuple[QDArchiveEntry, ...]:
        return tuple(self._cells[key] for key in sorted(self._cells))

    @property
    def candidates(self) -> tuple[QDCandidate, ...]:
        retained = {identifier for cell in self._cells.values() for identifier in _entry_ids(cell)}
        return tuple(self._candidates[identifier] for identifier in sorted(retained))

    @property
    def occupancy(self) -> int:
        return len(self._cells)

    def add(self, candidate: QDCandidate) -> ArchiveUpdate:
        key = cell_key(candidate.descriptors, self.descriptor_names)
        existing = self._cells.get(key)
        if existing is None and len(self._cells) >= self.maximum_size:
            return ArchiveUpdate(candidate.id, key, False, (), "archive cell capacity reached")
        if candidate.id in self._candidates:
            raise ValueError(f"candidate {candidate.id} already exists in the archive")

        self._candidates[candidate.id] = candidate
        if existing is None:
            self._cells[key] = QDArchiveEntry(
                cell_key=key,
                best_quality=candidate.id,
                lowest_cost=candidate.id,
                highest_robustness=candidate.id,
                highest_error_diversity=candidate.id,
            )
            return ArchiveUpdate(
                candidate.id,
                key,
                True,
                ("best_quality", "lowest_cost", "highest_robustness", "highest_error_diversity"),
                "new cell",
            )

        incumbent = self._candidates[existing.best_quality]
        candidate_score = self.quality(candidate)
        best_score = self.quality(incumbent)
        tolerance = abs(best_score) * (1 - self.quality_floor_relative_to_best)
        competitive = candidate_score >= best_score - tolerance
        replacements: list[str] = []
        values = existing.model_dump()
        if candidate_score > best_score:
            values["best_quality"] = candidate.id
            replacements.append("best_quality")
            competitive = True
        if competitive:
            slot_rules: dict[str, Callable[[QDCandidate], tuple[float, float]]] = {
                "lowest_cost": lambda item: (-item.normalized_cost, self.quality(item)),
                "highest_robustness": lambda item: (item.robustness, self.quality(item)),
                "highest_error_diversity": lambda item: (item.error_diversity, self.quality(item)),
            }
            for slot, rank in slot_rules.items():
                current = self._candidates[str(values[slot])]
                if rank(candidate) > rank(current):
                    values[slot] = candidate.id
                    replacements.append(slot)
        self._cells[key] = QDArchiveEntry.model_validate(values)
        retained = candidate.id in _entry_ids(self._cells[key])
        if not retained:
            self._candidates.pop(candidate.id)
        return ArchiveUpdate(
            candidate.id,
            key,
            retained,
            tuple(replacements),
            "retained as cell elite" if retained else "below the cell quality/diversity frontier",
        )


def _entry_ids(entry: QDArchiveEntry) -> tuple[str, ...]:
    return (
        entry.best_quality,
        entry.lowest_cost,
        entry.highest_robustness,
        entry.highest_error_diversity,
    )
