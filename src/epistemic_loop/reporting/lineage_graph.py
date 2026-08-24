from __future__ import annotations

from epistemic_loop.domain.models import ExperimentProposal


def mermaid_lineage(experiments: list[ExperimentProposal]) -> str:
    lines = ["flowchart TD"]
    by_lineage: dict[str, list[ExperimentProposal]] = {}
    for experiment in experiments:
        by_lineage.setdefault(experiment.lineage, []).append(experiment)
    for lineage, items in sorted(by_lineage.items()):
        safe = "".join(character if character.isalnum() else "_" for character in lineage)
        lines.append(f"  subgraph {safe}[{lineage}]")
        for previous, current in zip(items, items[1:], strict=False):
            lines.append(f"    {previous.id} --> {current.id}")
        if len(items) == 1:
            lines.append(f"    {items[0].id}")
        lines.append("  end")
    return "\n".join(lines) + "\n"
