import pytest

from epistemic_loop.domain.enums import EdgeType
from epistemic_loop.domain.hypothesis_graph import HypothesisEdge, HypothesisGraph
from epistemic_loop.domain.models import Hypothesis


def test_dependency_order(hypothesis: Hypothesis) -> None:
    dependent = hypothesis.model_copy(update={"id": "H-002", "version": 2})
    graph = HypothesisGraph()
    graph.add_hypothesis(hypothesis)
    graph.add_hypothesis(dependent)
    graph.add_edge(
        HypothesisEdge(source_id="H-002", target_id="H-001", edge_type=EdgeType.DEPENDS_ON, rationale="split first")
    )
    assert graph.dependency_order() == ["H-001", "H-002"]


def test_dependency_cycle_is_rejected(hypothesis: Hypothesis) -> None:
    other = hypothesis.model_copy(update={"id": "H-002", "version": 2})
    graph = HypothesisGraph(hypotheses={"H-001": hypothesis, "H-002": other})
    graph.add_edge(HypothesisEdge(source_id="H-001", target_id="H-002", edge_type=EdgeType.DEPENDS_ON, rationale="a"))
    graph.add_edge(HypothesisEdge(source_id="H-002", target_id="H-001", edge_type=EdgeType.DEPENDS_ON, rationale="b"))
    with pytest.raises(ValueError, match="cycle"):
        graph.dependency_order()
