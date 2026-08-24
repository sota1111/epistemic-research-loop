from __future__ import annotations

from pathlib import Path
from typing import Any

from epistemic_loop.domain.events import EventEnvelope, EventType
from epistemic_loop.domain.models import DomainModel
from epistemic_loop.storage.event_store import JsonlEventStore
from epistemic_loop.storage.projections import SqliteProjection


class ResearchRepository:
    """Atomic façade: append to canonical log, then update the rebuildable projection."""

    def __init__(self, run_root: str | Path, projection_path: str | Path):
        self.run_root = Path(run_root)
        self.projection_path = Path(projection_path)

    def event_store(self, run_id: str) -> JsonlEventStore:
        return JsonlEventStore(self.run_root / run_id / "events.jsonl")

    def append(self, run_id: str, event_type: EventType, payload: DomainModel | dict[str, Any]) -> EventEnvelope:
        event = self.event_store(run_id).append(run_id, event_type, payload)
        with SqliteProjection(self.projection_path) as projection:
            projection.apply(event)
        return event

    def replay(self, run_id: str) -> list[EventEnvelope]:
        events = self.event_store(run_id).read_all()
        with SqliteProjection(self.projection_path) as projection:
            projection.rebuild(events)
        return events
