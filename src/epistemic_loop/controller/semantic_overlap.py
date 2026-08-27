"""Classify semantic overlap as useful replication or redundant duplication."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class SemanticOverlapClass(StrEnum):
    UNIQUE = "unique"
    INDEPENDENT_REPLICATION = "independent_replication"
    REDUNDANT_DUPLICATION = "redundant_duplication"


@dataclass(frozen=True)
class SemanticExperimentRecord:
    experiment_id: str
    agent_id: str
    cluster_id: str
    claim: str
    operation: str
    observable: str
    downstream_decision: str
    model: str
    data_slice: str
    falsification_path: str
    proposal_preregistered: bool
    source_evidence_seen: bool = False


@dataclass(frozen=True)
class SemanticOverlapAssessment:
    cluster_id: str
    classification: SemanticOverlapClass
    experiment_ids: tuple[str, ...]
    independent_agents: tuple[str, ...]
    new_evidence_dimensions: tuple[str, ...]
    qd_contribution: bool


class SemanticOverlapClassifier:
    _DIMENSIONS = ("model", "observable", "data_slice", "falsification_path")

    def classify(self, records: Sequence[SemanticExperimentRecord]) -> tuple[SemanticOverlapAssessment, ...]:
        clusters: dict[str, list[SemanticExperimentRecord]] = {}
        for record in records:
            clusters.setdefault(record.cluster_id, []).append(record)
        return tuple(self._classify_cluster(cluster_id, clusters[cluster_id]) for cluster_id in sorted(clusters))

    def _classify_cluster(
        self,
        cluster_id: str,
        records: Sequence[SemanticExperimentRecord],
    ) -> SemanticOverlapAssessment:
        identifiers = tuple(sorted(item.experiment_id for item in records))
        agents = tuple(sorted({item.agent_id for item in records}))
        if len(records) == 1:
            return SemanticOverlapAssessment(
                cluster_id,
                SemanticOverlapClass.UNIQUE,
                identifiers,
                agents,
                (),
                True,
            )
        same_core = len({(item.claim, item.operation, item.downstream_decision) for item in records}) == 1
        varying = tuple(
            dimension for dimension in self._DIMENSIONS if len({getattr(item, dimension) for item in records}) > 1
        )
        independent = (
            same_core
            and len(agents) >= 2
            and all(item.proposal_preregistered and not item.source_evidence_seen for item in records)
            and bool(varying)
        )
        classification = (
            SemanticOverlapClass.INDEPENDENT_REPLICATION
            if independent
            else SemanticOverlapClass.REDUNDANT_DUPLICATION
        )
        return SemanticOverlapAssessment(
            cluster_id,
            classification,
            identifiers,
            agents,
            varying,
            classification is not SemanticOverlapClass.REDUNDANT_DUPLICATION,
        )
