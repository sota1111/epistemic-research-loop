from epistemic_loop.domain.events import EventType
from epistemic_loop.storage.projections import SqliteProjection
from epistemic_loop.storage.repositories import ResearchRepository


def test_append_updates_projection_and_replay_is_idempotent(tmp_path) -> None:
    repository = ResearchRepository(tmp_path / "runs", tmp_path / "projection.db")
    repository.append(
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
    repository.append(
        "run-001",
        EventType.STATE_CHANGED,
        {"state": "observing", "run_status": "running"},
    )
    with SqliteProjection(tmp_path / "projection.db") as projection:
        row = projection.connection.execute("SELECT status FROM runs WHERE id='run-001'").fetchone()
        assert row["status"] == "running"
    repository.replay("run-001")
    with SqliteProjection(tmp_path / "projection.db") as projection:
        count = projection.connection.execute("SELECT count(*) AS n FROM projected_events").fetchone()
        assert count["n"] == 2
