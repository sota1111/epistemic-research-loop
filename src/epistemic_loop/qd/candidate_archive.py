from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from epistemic_loop.controller.candidate_artifacts import CandidateArtifactValidator
from epistemic_loop.domain.models import CandidateArtifactRecord, GlobalEvidence


def candidate_cell(candidate: CandidateArtifactRecord) -> str:
    descriptor = candidate.descriptor
    return "|".join(
        (
            descriptor.epistemic_niche,
            descriptor.validation_world,
            descriptor.model_family,
            descriptor.representation,
            descriptor.routing,
            descriptor.post_processing,
            descriptor.error_profile,
        )
    )


class EpistemicArchive:
    def __init__(self) -> None:
        self._by_niche: dict[str, list[GlobalEvidence]] = defaultdict(list)

    def add(self, niche: str, evidence: GlobalEvidence) -> None:
        if any(item.evidence_id == evidence.evidence_id for item in self._by_niche[niche]):
            raise ValueError(f"duplicate epistemic evidence: {evidence.evidence_id}")
        self._by_niche[niche].append(evidence)

    def occupancy(self) -> dict[str, int]:
        return {niche: len(items) for niche, items in sorted(self._by_niche.items())}


class CandidateArchive:
    """Multi-candidate archive with score-redacted agent views."""

    def __init__(
        self,
        *,
        minimum_candidate_slots: int = 8,
        maximum_candidate_slots: int = 40,
        validator: CandidateArtifactValidator | None = None,
    ):
        if minimum_candidate_slots < 8:
            raise ValueError("candidate archive must reserve at least eight slots")
        if maximum_candidate_slots < minimum_candidate_slots:
            raise ValueError("maximum candidate slots must cover the minimum")
        self.minimum_candidate_slots = minimum_candidate_slots
        self.maximum_candidate_slots = maximum_candidate_slots
        self.validator = validator or CandidateArtifactValidator()
        self._candidates: dict[str, CandidateArtifactRecord] = {}

    @property
    def candidates(self) -> tuple[CandidateArtifactRecord, ...]:
        return tuple(self._candidates[key] for key in sorted(self._candidates))

    @property
    def occupancy(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for item in self._candidates.values():
            counts[candidate_cell(item)] += 1
        return dict(sorted(counts.items()))

    def promote(self, candidate: CandidateArtifactRecord) -> None:
        if candidate.candidate_id in self._candidates:
            raise ValueError(f"candidate already archived: {candidate.candidate_id}")
        validation = self.validator.validate(candidate.artifact_root)
        if not validation.valid:
            raise ValueError(
                f"candidate artifact contract failed ({validation.terminal_status.value}): "
                f"missing={validation.missing}, invalid={validation.invalid}"
            )
        if not candidate.leakage_check_passed or not candidate.reproducibility_passed:
            raise ValueError("candidate promotion requires leakage and reproducibility gates")
        if len(self._candidates) >= self.maximum_candidate_slots:
            raise OverflowError("candidate archive capacity reached")
        self._candidates[candidate.candidate_id] = candidate

    def agent_view(self, agent_id: str) -> dict[str, object]:
        own = []
        for item in self.candidates:
            if item.source_agent != agent_id:
                continue
            view: dict[str, object] = {
                "candidate_id": item.candidate_id,
                "cell": candidate_cell(item),
                "resource_cost": item.resource_cost,
            }
            if item.open_structure_validation_debt_ids:
                view["structure_validation_debt_ids"] = list(item.open_structure_validation_debt_ids)
            own.append(view)
        niches = {item.descriptor.epistemic_niche for item in self._candidates.values()}
        return {
            "occupied_cells": {key: True for key in self.occupancy},
            "occupied_niches": sorted(niches),
            "unoccupied_slot_count": self.maximum_candidate_slots - len(self._candidates),
            "own_candidates": own,
        }

    def artifact_root(self, candidate_id: str, *, controller: bool = False, requester: str | None = None) -> Path:
        candidate = self._candidates[candidate_id]
        if not controller and requester != candidate.source_agent:
            raise PermissionError("another agent's candidate code and artifacts are hidden during exploration")
        return Path(candidate.artifact_root)
