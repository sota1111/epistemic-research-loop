from __future__ import annotations

from collections import defaultdict, deque

from pydantic import Field, model_validator

from epistemic_loop.domain.enums import EdgeType, HypothesisStatus
from epistemic_loop.domain.models import DomainModel, Hypothesis


class HypothesisEdge(DomainModel):
    source_id: str
    target_id: str
    edge_type: EdgeType
    rationale: str

    @model_validator(mode="after")
    def no_self_edge(self) -> HypothesisEdge:
        if self.source_id == self.target_id:
            raise ValueError("a hypothesis cannot have an edge to itself")
        return self


class HypothesisGraph(DomainModel):
    hypotheses: dict[str, Hypothesis] = Field(default_factory=dict)
    edges: list[HypothesisEdge] = Field(default_factory=list)
    max_active: int = Field(default=30, ge=1)

    def add_hypothesis(self, hypothesis: Hypothesis) -> None:
        if hypothesis.id in self.hypotheses:
            raise ValueError(f"hypothesis already exists: {hypothesis.id}")
        active = sum(
            item.status not in {HypothesisStatus.RETIRED, HypothesisStatus.FALSIFIED}
            for item in self.hypotheses.values()
        )
        if active >= self.max_active:
            raise ValueError(f"active hypothesis limit reached: {self.max_active}")
        self.hypotheses[hypothesis.id] = hypothesis

    def add_edge(self, edge: HypothesisEdge) -> None:
        if edge.source_id not in self.hypotheses or edge.target_id not in self.hypotheses:
            raise ValueError("both edge endpoints must exist")
        if edge in self.edges:
            raise ValueError("duplicate hypothesis edge")
        self.edges.append(edge)

    def related(self, hypothesis_id: str, edge_type: EdgeType | None = None) -> list[str]:
        return [
            edge.target_id
            for edge in self.edges
            if edge.source_id == hypothesis_id and (edge_type is None or edge.edge_type == edge_type)
        ]

    def dependency_order(self) -> list[str]:
        """Return a stable topological order for depends_on edges; reject dependency cycles."""
        incoming: dict[str, int] = {key: 0 for key in self.hypotheses}
        outgoing: dict[str, list[str]] = defaultdict(list)
        for edge in self.edges:
            if edge.edge_type != EdgeType.DEPENDS_ON:
                continue
            # source depends on target, therefore target must precede source.
            outgoing[edge.target_id].append(edge.source_id)
            incoming[edge.source_id] += 1
        ready = deque(sorted(key for key, count in incoming.items() if count == 0))
        result: list[str] = []
        while ready:
            node = ready.popleft()
            result.append(node)
            for child in sorted(outgoing[node]):
                incoming[child] -= 1
                if incoming[child] == 0:
                    ready.append(child)
        if len(result) != len(self.hypotheses):
            raise ValueError("depends_on edges contain a cycle")
        return result
