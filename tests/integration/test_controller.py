from pathlib import Path

from epistemic_loop.agents.observer import CompetitionObserver
from epistemic_loop.config import load_config
from epistemic_loop.controller.research_graph import ResearchController, fingerprint_path
from epistemic_loop.domain.events import EventType
from epistemic_loop.storage.repositories import ResearchRepository


def test_controller_creates_and_starts_a_replayable_run(tmp_path) -> None:
    config = load_config(Path(__file__).resolve().parents[2] / "configs" / "defaults.yaml")
    repository = ResearchRepository(tmp_path / "runs", tmp_path / "state.db")
    controller = ResearchController(repository)
    run = controller.create_run(
        config,
        base_commit_sha="abc",
        dataset_fingerprint=fingerprint_path(None),
        run_id="run-controller",
    )
    world = CompetitionObserver().observe(
        {
            "metric": {"name": "auc"},
            "target": "fraud",
            "columns": ["TransactionDT", "customer_id"],
            "compute_constraints": ["cpu only"],
        }
    )
    controller.start(run.id, world)
    events = repository.event_store(run.id).read_all()
    assert [event.event_type for event in events] == [
        EventType.RUN_CREATED,
        EventType.STATE_CHANGED,
        EventType.STATE_CHANGED,
        EventType.WORLD_MODEL_RECORDED,
        EventType.STATE_CHANGED,
    ]
    assert "TransactionDT" in world.temporal_structure[0]
    assert "customer_id" in world.entity_structure[0]


def test_path_fingerprint_is_stable_and_changes_with_content(tmp_path) -> None:
    missing = fingerprint_path(tmp_path / "missing")
    first = tmp_path / "data" / "a.txt"
    first.parent.mkdir()
    first.write_text("one", encoding="utf-8")
    before = fingerprint_path(first.parent)
    assert before == fingerprint_path(first.parent)
    first.write_text("two", encoding="utf-8")
    assert fingerprint_path(first.parent) != before
    assert missing != before
