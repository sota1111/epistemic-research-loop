from __future__ import annotations

from epistemic_loop.domain.models import ExperimentProposal


def experiment_similarity(left: ExperimentProposal, right: ExperimentProposal) -> float:
    components: list[float] = []
    components.append(1.0 if left.lineage == right.lineage else 0.0)
    components.append(1.0 if left.experiment_type == right.experiment_type else 0.0)
    left_h = set(left.hypothesis_ids)
    right_h = set(right.hypothesis_ids)
    union = left_h | right_h
    components.append(len(left_h & right_h) / len(union) if union else 0.0)
    left_m = set(left.metrics)
    right_m = set(right.metrics)
    metric_union = left_m | right_m
    components.append(len(left_m & right_m) / len(metric_union) if metric_union else 0.0)
    return sum(components) / len(components)


def diversity_value(proposal: ExperimentProposal) -> float:
    return proposal.novelty_score
