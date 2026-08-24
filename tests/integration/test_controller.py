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


def test_replan_returns_an_unproductive_round_to_planning(tmp_path, hypothesis, proposal, clone_proposal) -> None:
    """Selection may legitimately choose nothing; the run must be able to propose different work.

    Without this the loop sits in `selecting` with nothing to dispatch and no way to propose
    anything else, which is how an unattended run dies without saying so.
    """
    import pytest

    from epistemic_loop.config import AppConfig, CompetitionConfig, PhaseWeights, RunConfig
    from epistemic_loop.controller.research_graph import LoopStateError
    from epistemic_loop.domain.enums import LoopState
    from epistemic_loop.domain.models import CompetitionWorldModel, CostEstimate

    run_id = "replan-001"
    controller = ResearchController(ResearchRepository(tmp_path / ".runs", tmp_path / "projection.db"))
    config = AppConfig(
        run=RunConfig(id=run_id),
        competition=CompetitionConfig(slug="example", metric_direction="maximize"),
    )
    controller.create_run(config, base_commit_sha="abc123", dataset_fingerprint="f" * 64, run_id=run_id)
    controller.start(run_id, CompetitionWorldModel())
    controller.record_hypotheses(run_id, [hypothesis.model_copy(update={"run_id": run_id})])
    unaffordable = clone_proposal(
        proposal,
        run_id=run_id,
        estimated_cost=CostEstimate(cpu_hours=10_000).model_dump(),
    )
    controller.record_proposals(run_id, [unaffordable])

    weights = PhaseWeights(pragmatic=0.2, epistemic=0.45, robustness=0.2, diversity=0.15)
    decision = controller.select_experiments(run_id, weights=weights, size=1)
    assert decision.selected_experiment_ids == []
    assert "CPU budget exceeded" in decision.rejected_reasons["EXP-001"]

    controller.replan(run_id, "no candidate passed selection")
    assert controller.state(run_id).loop_state == LoopState.PLANNING

    with pytest.raises(LoopStateError, match="cannot replan"):
        controller.replan(run_id, "already replanned")


def test_a_refused_dispatch_does_not_mark_the_experiment_running(
    tmp_path, hypothesis, proposal, clone_proposal
) -> None:
    """A dispatch the state machine refuses must cost nothing.

    The attempt is recorded before the executor is called on purpose, so a hand-off that dies
    mid-flight leaves the experiment running and forces an explicit retry. But a call refused by the
    state machine never reached an executor at all: recording it would burn the attempt and force
    every later retry to invent a new attempt number for work that never started.
    """
    import pytest

    from epistemic_loop.adapters.executor.base import ExecutorAdapter
    from epistemic_loop.config import AppConfig, CompetitionConfig, PhaseWeights, RunConfig
    from epistemic_loop.controller.research_graph import LoopStateError
    from epistemic_loop.domain.enums import ExperimentStatus, LoopState
    from epistemic_loop.domain.models import CompetitionWorldModel

    class NeverCalled(ExecutorAdapter):
        def submit(self, request):  # pragma: no cover - the point is that it is not reached
            raise AssertionError("the executor must not be reached from a refused state")

        def result(self, request):
            return None

    run_id = "refused-001"
    controller = ResearchController(ResearchRepository(tmp_path / ".runs", tmp_path / "projection.db"))
    config = AppConfig(
        run=RunConfig(id=run_id), competition=CompetitionConfig(slug="example", metric_direction="maximize")
    )
    controller.create_run(config, base_commit_sha="abc123", dataset_fingerprint="f" * 64, run_id=run_id)
    controller.start(run_id, CompetitionWorldModel())
    controller.record_hypotheses(run_id, [hypothesis.model_copy(update={"run_id": run_id})])
    controller.record_proposals(run_id, [clone_proposal(proposal, run_id=run_id)])
    controller.select_experiments(
        run_id, weights=PhaseWeights(pragmatic=0.2, epistemic=0.45, robustness=0.2, diversity=0.15), size=1
    )
    controller.replan(run_id, "simulate a round that moved on without dispatching")

    with pytest.raises(LoopStateError, match="cannot move from planning to executing"):
        controller.dispatch(run_id, "EXP-001", NeverCalled(), container_image="python:3.11-slim")

    state = controller.state(run_id)
    assert state.experiment_statuses["EXP-001"] == ExperimentStatus.SELECTED, "the refused dispatch burnt the attempt"
    assert state.loop_state == LoopState.PLANNING
