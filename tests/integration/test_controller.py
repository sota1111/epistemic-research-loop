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

    The scenario is the real one: a two-experiment portfolio where the first result is imported
    before the second is dispatched. Importing moves the loop to `parsing`, and the second
    experiment -- still selected, never started -- must come out of it untouched.
    """
    import pytest

    from epistemic_loop.adapters.executor.base import ExecutorAdapter
    from epistemic_loop.config import AppConfig, CompetitionConfig, PhaseWeights, RunConfig
    from epistemic_loop.controller.research_graph import LoopStateError
    from epistemic_loop.domain.enums import ExperimentStatus, LoopState
    from epistemic_loop.domain.models import CompetitionWorldModel, ExperimentResult

    class Echo(ExecutorAdapter):
        def __init__(self) -> None:
            self.calls: list[str] = []

        def submit(self, request):
            self.calls.append(request.experiment_id)
            return ExperimentResult(
                experiment_id=request.experiment_id,
                run_id=request.run_id,
                attempt=1,
                status="completed",
                commit_sha=request.base_commit_sha,
                environment_hash="e" * 64,
                dataset_fingerprint="f" * 64,
                metrics={"roc_auc": 0.9},
            )

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
    controller.record_proposals(
        run_id,
        [
            clone_proposal(proposal, run_id=run_id, id="EXP-001"),
            clone_proposal(proposal, run_id=run_id, id="EXP-002", protocol="a second, different protocol"),
        ],
    )
    controller.select_experiments(
        run_id, weights=PhaseWeights(pragmatic=0.2, epistemic=0.45, robustness=0.2, diversity=0.15), size=2
    )
    executor = Echo()
    _, first = controller.dispatch(run_id, "EXP-001", executor, container_image="python:3.11-slim")
    controller.import_result(run_id, first)
    assert controller.state(run_id).loop_state == LoopState.PARSING

    with pytest.raises(LoopStateError, match="cannot move from parsing to executing"):
        controller.dispatch(run_id, "EXP-002", executor, container_image="python:3.11-slim")

    state = controller.state(run_id)
    assert state.experiment_statuses["EXP-002"] == ExperimentStatus.SELECTED, "the refused dispatch burnt the attempt"
    assert executor.calls == ["EXP-001"], "the executor must not be reached from a refused state"


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


def test_a_stranded_selection_can_still_be_dispatched(tmp_path, hypothesis, proposal, clone_proposal) -> None:
    """A selection the run already committed to must not be lost because the round moved on.

    Selecting an experiment records its preregistration in the log. If the round then advances
    without dispatching it, the experiment is stranded: it is `selected`, so a fresh selection will
    not pick it up again, and the loop is no longer in `selecting`, so it cannot be dispatched.
    Refusing to honour it discards a decision rather than protecting one.
    """
    from epistemic_loop.config import AppConfig, CompetitionConfig, PhaseWeights, RunConfig
    from epistemic_loop.domain.enums import ExperimentStatus, LoopState
    from epistemic_loop.domain.models import CompetitionWorldModel, ExperimentResult

    run_id = "stranded-001"
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
    controller.replan(run_id, "the round advanced without dispatching")
    assert controller.state(run_id).loop_state == LoopState.PLANNING
    assert controller.state(run_id).experiment_statuses["EXP-001"] == ExperimentStatus.SELECTED

    class Echo:
        def submit(self, request):
            return ExperimentResult(
                experiment_id=request.experiment_id,
                run_id=request.run_id,
                attempt=1,
                status="completed",
                commit_sha=request.base_commit_sha,
                environment_hash="e" * 64,
                dataset_fingerprint="f" * 64,
                metrics={"roc_auc": 0.9},
            )

        def result(self, request):
            return None

    _, result = controller.dispatch(run_id, "EXP-001", Echo(), container_image="python:3.11-slim")  # type: ignore[arg-type]

    assert result.status == "completed"
    assert controller.state(run_id).loop_state == LoopState.EXECUTING
    assert controller.import_result(run_id, result) is not None
