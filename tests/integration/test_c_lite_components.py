from pathlib import Path

import pytest

from epistemic_loop.adapters.executor.base import ExecutorAdapter
from epistemic_loop.config import AppConfig, CompetitionConfig, PhaseWeights, RunConfig
from epistemic_loop.controller.research_graph import ResearchController, file_sha256
from epistemic_loop.controller.research_state import derive_research_state
from epistemic_loop.domain.enums import ExperimentType, HypothesisType, RunMode, ValidationSplitType
from epistemic_loop.domain.events import EventType
from epistemic_loop.domain.models import (
    CandidateDescriptors,
    CompetitionWorldModel,
    ExperimentManifest,
    ExperimentProposal,
    ExperimentResult,
    Hypothesis,
    HypothesisOutcomeForecast,
    OOFArtifact,
    OOFRecord,
    OutcomeLikelihood,
    ValidationOutcomeLikelihood,
    ValidationWorld,
    ValidationWorldForecast,
)
from epistemic_loop.oof.store import OOFStore
from epistemic_loop.storage.projections import SqliteProjection
from epistemic_loop.storage.repositories import ResearchRepository


class Completed(ExecutorAdapter):
    def __init__(self, artifacts: list[Path]):
        self.artifacts = artifacts

    def submit(self, request):
        manifest_path = next(item for item in self.artifacts if item.name == "erl_manifest.json")
        environment_lock = manifest_path.with_name("environment-lock.txt")
        environment_lock.write_text("locked\n", encoding="utf-8")
        self.artifacts.append(environment_lock)
        result = ExperimentResult(
            experiment_id=request.experiment_id,
            run_id=request.run_id,
            attempt=1,
            status="completed",
            commit_sha=request.base_commit_sha,
            environment_hash="e" * 64,
            environment_lock_hash="l" * 64,
            dataset_fingerprint="f" * 64,
            metrics={
                "auc": 0.81,
                "rank_stability": 0.7,
                "reproduction_passed": 1.0,
                "leakage_check_passed": 1.0,
            },
            observed_outcomes={"validation_world": "time_wins"},
            artifact_refs=[str(item) for item in self.artifacts],
            runtime={"cpu_hours": 0.2, "wall_hours": 0.1},
        )
        manifest_path.write_text(
            ExperimentManifest(
                experiment_id=request.experiment_id,
                run_id=request.run_id,
                system_mode=request.system_mode,
                request=request,
                result=result,
                environment_lock_hash=result.environment_lock_hash,
                environment_lock_ref=str(environment_lock),
                fold_assignment_refs=[str(item) for item in self.artifacts if "fold_assignment" in item.name],
                submission_procedure=request.command,
            ).model_dump_json(indent=2)
            + "\n",
            encoding="utf-8",
        )
        return result.model_copy(update={"manifest_ref": str(manifest_path)})

    def result(self, request):
        return None


def test_c_lite_state_is_event_sourced_end_to_end(
    tmp_path: Path,
    hypothesis: Hypothesis,
    proposal: ExperimentProposal,
) -> None:
    run_id = "c-lite-001"
    repository = ResearchRepository(tmp_path / ".runs", tmp_path / "projection.db")
    controller = ResearchController(repository)
    config = AppConfig(
        run=RunConfig(id=run_id, mode=RunMode.SYSTEM_C),
        competition=CompetitionConfig(slug="example", metric_direction="maximize", primary_metric="auc"),
    )
    controller.create_run(config, base_commit_sha="abc123", dataset_fingerprint="f" * 64, run_id=run_id)
    controller.start(run_id, CompetitionWorldModel())
    controller.record_validation_worlds(
        run_id,
        [
            ValidationWorld(
                id="W-random",
                run_id=run_id,
                split_type=ValidationSplitType.RANDOM,
                assumptions=["iid"],
                posterior_probability=0.5,
            ),
            ValidationWorld(
                id="W-time",
                run_id=run_id,
                split_type=ValidationSplitType.TIME,
                assumptions=["future"],
                posterior_probability=0.5,
            ),
        ],
    )
    target = hypothesis.model_copy(
        update={
            "run_id": run_id,
            "type": HypothesisType.VALIDATION,
            "alternative_hypothesis_ids": ["H-GROUP"],
            "created_by": "scientist",
        }
    )
    controller.record_hypotheses(run_id, [target])
    forecast = HypothesisOutcomeForecast(
        hypothesis_id=target.id,
        outcomes=[
            OutcomeLikelihood(label="time_wins", probability_if_true=0.8, probability_if_false=0.2),
            OutcomeLikelihood(label="random_wins", probability_if_true=0.2, probability_if_false=0.8),
        ],
        decisions_affected=["primary_validation"],
        measurement_notes="same model and seeds",
    )
    experiment = proposal.model_copy(
        update={
            "run_id": run_id,
            "outcome_forecasts": [forecast],
            "validation_world_forecast": ValidationWorldForecast(
                outcomes=[
                    ValidationOutcomeLikelihood(
                        label="time_wins",
                        probability_by_world={"W-random": 0.2, "W-time": 0.8},
                    ),
                    ValidationOutcomeLikelihood(
                        label="random_wins",
                        probability_by_world={"W-random": 0.8, "W-time": 0.2},
                    ),
                ],
                metric_name="rank_stability",
                decisions_affected=["primary_validation"],
                measurement_notes="same models and seeds",
            ),
            "descriptors": CandidateDescriptors(
                validation_type="time",
                model_family="gbdt",
                representation="aggregate",
                shift_hypothesis="temporal",
            ),
        }
    )
    controller.record_proposals(run_id, [experiment])
    controller.register_final_selection_rule(
        run_id,
        description="highest deterministic final-candidate utility after required verification",
    )
    decision = controller.select_experiments(
        run_id,
        weights=PhaseWeights(pragmatic=0.2, epistemic=0.45, robustness=0.2, diversity=0.15),
    )
    assert decision.selected_experiment_ids == [experiment.id]

    oof_path = OOFStore().write(
        tmp_path / "oof.jsonl",
        [
            OOFRecord(
                row_id=str(index),
                fold_id=str(index % 2),
                target=target_value,
                oof_prediction=prediction,
                validation_world="W-time",
                candidate_id=f"QD-{experiment.id}",
            )
            for index, (target_value, prediction) in enumerate([(0, 0.1), (1, 0.8), (0, 0.2), (1, 0.9)])
        ],
    )
    submission = tmp_path / "submission.csv"
    submission.write_text("id,target\n1,0.5\n", encoding="utf-8")
    fold_assignment = tmp_path / "fold_assignment.json"
    fold_assignment.write_text('{"0": ["0", "2"], "1": ["1", "3"]}\n', encoding="utf-8")
    manifest = tmp_path / "erl_manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    _, result = controller.dispatch(
        run_id,
        experiment.id,
        Completed([oof_path, submission, fold_assignment, manifest]),
        container_image="test",
    )
    observation = controller.import_result(run_id, result)
    assert observation is not None
    assert f"QD-{experiment.id}" in controller.state(run_id).qd_candidates
    assert controller.state(run_id).validation_worlds["W-time"].posterior_probability == 0.8

    oof_artifact = OOFArtifact(
        id="OOF-001",
        run_id=run_id,
        candidate_id=f"QD-{experiment.id}",
        validation_world="W-time",
        uri=str(oof_path),
        sha256=file_sha256(oof_path),
        row_count=4,
        format="jsonl",
    )
    controller.record_oof_artifact(run_id, oof_artifact)
    assert controller.propose_falsification(run_id, available_data=["train", "time"]).target_hypothesis == target.id

    controller.replan(run_id, "run the required independent replication")
    with pytest.raises(ValueError, match="independent replication"):
        controller.finalize(run_id, artifacts=[str(submission)], note="replication has not run yet")
    replication_root = tmp_path / "replication"
    replication_root.mkdir()
    replication_output = replication_root / "replication.txt"
    replication_output.write_text("passed\n", encoding="utf-8")
    replication_fold = replication_root / "fold_assignment.json"
    replication_fold.write_text(fold_assignment.read_text(encoding="utf-8"), encoding="utf-8")
    replication_manifest = replication_root / "erl_manifest.json"
    replication_manifest.write_text("{}\n", encoding="utf-8")
    replication = experiment.model_copy(
        update={
            "id": "EXP-REPLICATION-001",
            "experiment_type": ExperimentType.REPLICATION,
            "protocol": "independently rerun the locked candidate under its preregistered tolerance",
            "descriptors": None,
            "is_replication_of": experiment.id,
            "required_artifacts": ["replication.txt", "fold_assignment.json"],
        }
    )
    controller.record_proposals(run_id, [replication])
    replication_decision = controller.select_experiments(
        run_id,
        weights=PhaseWeights(pragmatic=0.2, epistemic=0.45, robustness=0.2, diversity=0.15),
    )
    assert replication_decision.selected_experiment_ids == [replication.id]
    _, replication_result = controller.dispatch(
        run_id,
        replication.id,
        Completed([replication_output, replication_fold, replication_manifest]),
        container_image="test",
    )
    assert controller.import_result(run_id, replication_result) is not None

    controller.replan(run_id, "component integration verified")
    submission.write_text("id,target\n1,0.6\n", encoding="utf-8")
    with pytest.raises(ValueError, match="content changed"):
        controller.finalize(run_id, artifacts=[str(submission)], note="reject a post-observation mutation")
    submission.write_text("id,target\n1,0.5\n", encoding="utf-8")
    locked = controller.finalize(run_id, artifacts=[str(submission)], note="lock the only verified candidate")
    assert locked["selection_rule_locked"] is True
    assert locked["artifacts"][0]["locked"] is True

    replayed = controller.state(run_id)
    assert replayed.validation_worlds["W-time"].posterior_probability > 0.8
    assert replayed.oof_artifacts["OOF-001"].row_count == 4
    assert replayed.qd_candidates[f"QD-{experiment.id}"].descriptors.model_family == "gbdt"
    research_state = derive_research_state(replayed)
    assert research_state.validation_uncertainty < 1.0
    assert research_state.active_hypotheses == 1
    assert research_state.qd_occupancy == 0.01
    assert research_state.expected_hidden_score == 0.81
    assert research_state.evidence_ids
    assert any(
        event.event_type == EventType.FALSIFICATION_PROPOSED for event in repository.event_store(run_id).read_all()
    )
    with SqliteProjection(repository.projection_path) as projection:
        projected = projection.one("validation_worlds", "W-time")
    assert projected is not None and projected["posterior_probability"] > 0.8
    with pytest.raises(ValueError, match="immutable"):
        repository.append(run_id, EventType.STATE_CHANGED, {"state": "planning"})
