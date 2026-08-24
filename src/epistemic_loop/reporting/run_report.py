from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from epistemic_loop.domain.events import EventEnvelope, EventType


def build_run_report(run_id: str, events: list[EventEnvelope]) -> str:
    counts = Counter(event.event_type.value for event in events)
    run = next((event.payload for event in events if event.event_type == EventType.RUN_CREATED), {})
    latest_phase = next(
        (event.payload.get("phase") for event in reversed(events) if event.event_type == EventType.PHASE_CHANGED),
        run.get("phase", "unknown"),
    )
    hypotheses = [event.payload for event in events if event.event_type == EventType.HYPOTHESIS_PROPOSED]
    experiments = [event.payload for event in events if event.event_type == EventType.EXPERIMENT_PROPOSED]
    violations = [event.payload for event in events if event.event_type == EventType.VIOLATION_DETECTED]
    return (
        "\n".join(
            [
                f"# Research Run {run_id}",
                "",
                "## Run conditions",
                "",
                f"- Competition: {run.get('competition_id', 'unknown')}",
                f"- Mode: {run.get('mode', 'unknown')}",
                f"- Phase: {latest_phase}",
                f"- Base commit: {run.get('base_commit_sha', 'unknown')}",
                f"- Dataset fingerprint: {run.get('dataset_fingerprint', 'unknown')}",
                "",
                "## Audit summary",
                "",
                f"- Events: {len(events)}",
                f"- Hypotheses proposed: {len(hypotheses)}",
                f"- Experiments proposed: {len(experiments)}",
                f"- Holdout/rule violations: {len(violations)}",
                "",
                "## Event counts",
                "",
                "```json",
                json.dumps(dict(sorted(counts.items())), indent=2),
                "```",
            ]
        )
        + "\n"
    )


def write_run_report(run_id: str, events: list[EventEnvelope], destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_run_report(run_id, events), encoding="utf-8")
    return path
