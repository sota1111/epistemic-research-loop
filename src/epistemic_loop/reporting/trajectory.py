from __future__ import annotations

from epistemic_loop.domain.events import EventEnvelope


def trajectory(events: list[EventEnvelope]) -> list[dict[str, object]]:
    return [
        {
            "sequence": event.sequence,
            "time": event.occurred_at.isoformat(),
            "type": event.event_type.value,
            "summary": event.payload.get("id") or event.payload.get("state") or event.payload.get("phase"),
        }
        for event in events
    ]
