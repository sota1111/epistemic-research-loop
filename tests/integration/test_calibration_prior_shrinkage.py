from epistemic_loop.config import AppConfig, CompetitionConfig, RunConfig
from epistemic_loop.controller.research_graph import ResearchController
from epistemic_loop.domain.enums import RunMode
from epistemic_loop.domain.events import EventType
from epistemic_loop.domain.models import CompetitionWorldModel, ForecastCalibrationRecord, Hypothesis
from epistemic_loop.storage.repositories import ResearchRepository


def test_poorly_calibrated_agent_prior_is_shrunk_toward_half(tmp_path, hypothesis: Hypothesis) -> None:
    run_id = "calibration-run"
    repository = ResearchRepository(tmp_path / "runs", tmp_path / "state.db")
    controller = ResearchController(repository)
    config = AppConfig(
        run=RunConfig(id=run_id, mode=RunMode.SYSTEM_C),
        competition=CompetitionConfig(slug="anonymous", metric_direction="maximize"),
    )
    controller.create_run(config, base_commit_sha="abc", dataset_fingerprint="f" * 64, run_id=run_id)
    controller.start(run_id, CompetitionWorldModel())
    for index in range(3):
        repository.append(
            run_id,
            EventType.FORECAST_CALIBRATION_RECORDED,
            ForecastCalibrationRecord(
                id=f"FCR-{index}",
                run_id=run_id,
                experiment_id=f"E-{index}",
                proposer_agent="test",
                category=hypothesis.type.value,
                probabilities={"yes": 0.99, "no": 0.01},
                observed_label="no",
            ),
        )
    proposed = hypothesis.model_copy(update={"run_id": run_id, "prior_confidence": 0.9, "current_confidence": 0.9})

    controller.record_hypotheses(
        run_id,
        [proposed],
        calibration_minimum_records=3,
        poor_brier_threshold=0.25,
        prior_shrinkage=0.25,
    )

    recorded = controller.state(run_id).hypotheses[hypothesis.id]
    assert recorded.uncalibrated_prior_confidence == 0.9
    assert recorded.prior_confidence == 0.8
    assert recorded.current_confidence == 0.8
