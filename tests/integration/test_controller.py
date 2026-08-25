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


def test_a_run_can_be_finalized_from_planning(tmp_path, hypothesis, proposal, clone_proposal) -> None:
    """A final submission is not an experiment and must not have to pass as one.

    It buys no information and is the most expensive fit a run makes, so a pragmatic selector scores
    it negative and refuses it -- which happened to the exploiter arm's own final submission during
    the IEEE-CIS verification. `FINALIZING` existed in the state machine for this and nothing ever
    entered it, so the final artifact had to be produced outside the loop's accounting.
    """
    import pytest

    from epistemic_loop.config import AppConfig, CompetitionConfig, RunConfig
    from epistemic_loop.controller.research_graph import LoopStateError
    from epistemic_loop.domain.enums import LoopState, RunStatus
    from epistemic_loop.domain.events import EventType
    from epistemic_loop.domain.models import CompetitionWorldModel

    run_id = "final-001"
    controller = ResearchController(ResearchRepository(tmp_path / ".runs", tmp_path / "projection.db"))
    config = AppConfig(
        run=RunConfig(id=run_id), competition=CompetitionConfig(slug="example", metric_direction="maximize")
    )
    controller.create_run(config, base_commit_sha="abc123", dataset_fingerprint="f" * 64, run_id=run_id)
    controller.start(run_id, CompetitionWorldModel())
    controller.record_hypotheses(run_id, [hypothesis.model_copy(update={"run_id": run_id})])

    payload = controller.finalize(run_id, artifacts=["submission.csv"], note="shipping the tuned configuration")

    assert payload["artifacts"] == ["submission.csv"]
    assert payload["experiments_completed"] == 0
    state = controller.state(run_id)
    assert state.loop_state == LoopState.COMPLETED
    assert state.run.status == RunStatus.COMPLETED
    recorded = [event.event_type for event in controller.repository.event_store(run_id).read_all()]
    assert EventType.RUN_FINALIZED in recorded

    with pytest.raises(LoopStateError, match="cannot finalize from completed"):
        controller.finalize(run_id, artifacts=[], note="twice")


def test_a_late_result_is_recorded_instead_of_discarded(tmp_path, hypothesis, proposal, clone_proposal) -> None:
    """A worker slower than the caller's timeout must not cost the run its evidence.

    `import_result` used to require the loop to still be in `executing`, so once a round timed out
    and replanned, a result that arrived afterwards could never be imported: the experiment stayed
    `running` forever and the compute that produced it was thrown away. With an asynchronous worker
    fleet that is ordinary rather than exceptional, so the observation is now recorded without
    dragging the loop back into `parsing`, and the next round's falsification step picks it up.
    """
    import pytest

    from epistemic_loop.config import AppConfig, CompetitionConfig, PhaseWeights, RunConfig
    from epistemic_loop.controller.research_graph import LoopStateError
    from epistemic_loop.domain.enums import ExperimentStatus, LoopState
    from epistemic_loop.domain.models import CompetitionWorldModel, ExperimentResult

    run_id = "late-001"
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

    class Queued:
        def submit(self, request):
            return ExperimentResult(
                experiment_id=request.experiment_id,
                run_id=request.run_id,
                attempt=1,
                status="queued",
                commit_sha=request.base_commit_sha,
                environment_hash="pending",
                dataset_fingerprint="pending",
            )

        def result(self, request):
            return None

    controller.dispatch(run_id, "EXP-001", Queued(), container_image="python:3.11-slim")  # type: ignore[arg-type]
    controller.replan(run_id, "the worker did not report within the timeout")
    assert controller.state(run_id).loop_state == LoopState.PLANNING

    late = ExperimentResult(
        experiment_id="EXP-001",
        run_id=run_id,
        attempt=1,
        status="completed",
        commit_sha="abc123",
        environment_hash="e" * 64,
        dataset_fingerprint="f" * 64,
        metrics={"roc_auc": 0.91},
    )
    observation = controller.import_result(run_id, late)

    assert observation is not None and observation.metrics == {"roc_auc": 0.91}
    state = controller.state(run_id)
    assert state.experiment_statuses["EXP-001"] == ExperimentStatus.COMPLETED
    assert state.loop_state == LoopState.PLANNING, "a late result must not drag the loop back a stage"
    assert [item.id for item in state.unjudged_observations()] == [observation.id]

    with pytest.raises(LoopStateError, match="never dispatched"):
        controller.import_result(run_id, late.model_copy(update={"experiment_id": "EXP-001"}))


def test_a_standing_candidate_pool_can_be_rescored_without_new_proposals(
    tmp_path, hypothesis, proposal, clone_proposal
) -> None:
    """A round with nothing new to propose must still be able to select.

    A preregistered candidate set is meant to be worked through one experiment at a time. Requiring
    a fresh proposal to reach `scoring` would make the run invent work it does not want just to get
    at work it already committed to.
    """
    import pytest

    from epistemic_loop.config import AppConfig, CompetitionConfig, PhaseWeights, RunConfig
    from epistemic_loop.domain.enums import LoopState
    from epistemic_loop.domain.models import CompetitionWorldModel

    run_id = "rescore-001"
    weights = PhaseWeights(pragmatic=0.2, epistemic=0.45, robustness=0.2, diversity=0.15)
    controller = ResearchController(ResearchRepository(tmp_path / ".runs", tmp_path / "projection.db"))
    config = AppConfig(
        run=RunConfig(id=run_id), competition=CompetitionConfig(slug="example", metric_direction="maximize")
    )
    controller.create_run(config, base_commit_sha="abc123", dataset_fingerprint="f" * 64, run_id=run_id)
    controller.start(run_id, CompetitionWorldModel())
    controller.record_hypotheses(run_id, [hypothesis.model_copy(update={"run_id": run_id})])
    controller.record_proposals(
        run_id,
        [
            clone_proposal(proposal, run_id=run_id, id="EXP-001"),
            clone_proposal(proposal, run_id=run_id, id="EXP-002", protocol="a second, different protocol"),
        ],
    )
    first = controller.select_experiments(run_id, weights=weights, size=1)
    assert len(first.selected_experiment_ids) == 1
    controller.replan(run_id, "round finished without dispatching")
    assert controller.state(run_id).loop_state == LoopState.PLANNING

    second = controller.select_experiments(run_id, weights=weights, size=1)

    assert second.selected_experiment_ids and second.selected_experiment_ids != first.selected_experiment_ids
    assert controller.state(run_id).loop_state == LoopState.SELECTING

    controller.replan(run_id, "and again")
    with pytest.raises(ValueError, match="no proposed experiments"):
        controller.select_experiments(run_id, weights=weights, size=1)
