import json

import pytest

from epistemic_loop.domain.events import EventType
from epistemic_loop.storage.event_store import IntegrityError, JsonlEventStore
from epistemic_loop.storage.projections import SqliteProjection


def test_same_event_log_replays_to_same_projection(tmp_path) -> None:
    store = JsonlEventStore(tmp_path / "events.jsonl")
    store.append(
        "run-001",
        EventType.RUN_CREATED,
        {
            "id": "run-001",
            "competition_id": "synthetic",
            "mode": "epistemic",
            "phase": "discovery",
            "status": "created",
        },
    )
    store.append(
        "run-001",
        EventType.STATE_CHANGED,
        {"state": "observing", "run_status": "running"},
    )
    events = store.read_all()
    with SqliteProjection(tmp_path / "projection.db") as projection:
        projection.rebuild(events)
        first = projection.connection.execute("SELECT id, status, phase FROM runs").fetchall()
        projection.rebuild(events)
        second = projection.connection.execute("SELECT id, status, phase FROM runs").fetchall()
    assert [tuple(row) for row in first] == [tuple(row) for row in second]


def test_hash_chain_detects_tampering(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    store = JsonlEventStore(path)
    store.append("run-001", EventType.STATE_CHANGED, {"state": "observing"})
    record = json.loads(path.read_text(encoding="utf-8"))
    record["payload"]["state"] = "executing"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(IntegrityError, match="event hash"):
        store.read_all()
