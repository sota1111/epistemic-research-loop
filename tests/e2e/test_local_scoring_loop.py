from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from epistemic_loop.adapters.executor.local import LocalExecutor
from epistemic_loop.agents.auto import AutomaticProposer
from epistemic_loop.agents.proposal_bridge import (
    ExperimentBatch,
    FalsificationAssessment,
    HypothesisBatch,
    ProposalBridge,
)
from epistemic_loop.config import AppConfig, CompetitionConfig, ExecutorConfig, LoopConfig, RunConfig
from epistemic_loop.controller.autoloop import AutonomousLoop, LoopSettings
from epistemic_loop.controller.research_graph import ResearchController
from epistemic_loop.domain.enums import ExperimentType, HypothesisType, VerifierResult
from epistemic_loop.domain.models import CompetitionWorldModel, ExperimentProposal, Hypothesis
from epistemic_loop.storage.repositories import ResearchRepository

ROOT = Path(__file__).resolve().parents[2]
RUN = "local-scoring-001"
ROUNDS = 12

#: The worker scores locally and writes only local metrics; no Kaggle call is possible from here.
WORKER = """
import json, os, pathlib
out = pathlib.Path(os.environ["ERL_OUTPUT_DIR"])
out.mkdir(parents=True, exist_ok=True)
(out / "metrics.json").write_text(json.dumps({"auc_gap": 0.061}))
(out / "fold_metrics.json").write_text(json.dumps({"folds": [0.05, 0.06]}))
"""


class RoundRobinLlm:
    """Proposes one fresh experiment per round, as an unattended run's designer would."""

    def __init__(self, hypothesis: Hypothesis, template: ExperimentProposal, worker: Path):
        self.hypothesis = hypothesis
        self.template = template
        self.worker = worker
        self.round = 0

    def generate(self, prompt: str, schema: type[BaseModel], context: dict[str, Any]) -> Any:
        if schema is HypothesisBatch:
            return HypothesisBatch(hypotheses=[self.hypothesis])
        if schema is ExperimentBatch:
            self.round += 1
            return ExperimentBatch(
                experiments=[
                    self.template.model_copy(
                        update={
                            "id": f"EXP-{self.round:03d}",
                            # A fresh question each round; the duplicate gate refuses a repeat.
                            "protocol": f"round {self.round}: compare the split on a new feature block",
                            "implementation_request": {"command": f"python3 {self.worker}"},
                        }
                    )
                ]
            )
        if schema is FalsificationAssessment:
            return FalsificationAssessment(
                hypothesis_id=context["hypothesis"]["id"],
                supporting_predictions=["temporal CV score is lower than random CV"],
                contradicting_predictions=[],
                alternative_explanation="fold-size differences rather than temporal leakage",
                confounders_checked=["fold size", "seed"],
                alternative_claims=["the gap is driven by one entity cluster, not by time"],
                verifier_result=VerifierResult.PASS,
                evidence_summary="observed gap 0.061 exceeds the preregistered 0.02 threshold",
            )
        raise AssertionError(f"unexpected schema: {schema}")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "worker.py").write_text(WORKER, encoding="utf-8")
    return tmp_path


@pytest.fixture
def config(workspace: Path) -> AppConfig:
    return AppConfig(
        run=RunConfig(id=RUN),
        competition=CompetitionConfig(slug="example", metric_direction="maximize", primary_metric="auc"),
        loop=LoopConfig(max_rounds_without_information=ROUNDS + 1),
        executor=ExecutorConfig(
            adapter="local",
            result_root=str(workspace / "results"),
            workspace=str(workspace),
        ),
    )


def test_twelve_rounds_run_on_local_scoring_without_any_submission(
    workspace: Path,
    config: AppConfig,
    hypothesis: Hypothesis,
    proposal: ExperimentProposal,
) -> None:
    """Kaggle allows five submissions a day; local scoring must not be limited by that at all.

    Twelve rounds is deliberately more than any daily submission allowance: the research loop reads
    only `metrics.json` written by the worker, so its cadence is bounded by compute, not by Kaggle.
    """
    controller = ResearchController(ResearchRepository(workspace / ".runs", workspace / "projection.db"))
    controller.create_run(config, base_commit_sha="abc123", dataset_fingerprint="f" * 64, run_id=RUN)
    controller.start(RUN, CompetitionWorldModel(unresolved_questions=["which split?"]))

    template = proposal.model_copy(
        update={"run_id": RUN, "experiment_type": ExperimentType.DIAGNOSTIC, "id": "EXP-000"}
    )
    llm = RoundRobinLlm(
        hypothesis.model_copy(update={"run_id": RUN, "type": HypothesisType.VALIDATION}),
        template,
        workspace / "worker.py",
    )
    loop = AutonomousLoop(
        controller,
        AutomaticProposer(llm, ProposalBridge(workspace / ".proposals", ROOT / "prompts")),
        LocalExecutor(workspace, workspace / "results"),
        config=config,
        home=workspace,
        sleep=lambda _: None,
    )

    outcomes = loop.run(RUN, LoopSettings(rounds=ROUNDS, poll_seconds=0, timeout_seconds=5))

    assert len(outcomes) == ROUNDS, [outcome.stop_reasons or outcome.pending for outcome in outcomes]
    assert all(outcome.observations for outcome in outcomes), "every round must produce a local observation"
    assert not any(outcome.pending for outcome in outcomes)

    state = controller.state(RUN)
    assert len(state.observations) == ROUNDS
    assert state.usage.experiments == ROUNDS
    assert state.usage.final_submissions == 0, "the research loop never spends a Kaggle submission"

    metrics = {value for observation in state.observations.values() for value in observation.metrics}
    assert metrics == {"auc_gap"}, "scoring stayed local"
    assert not any(path.name == "submission.csv" for path in workspace.rglob("*")), "no submission artifact was made"


def test_the_falsifier_history_reaches_the_next_rounds_proposals(
    workspace: Path,
    config: AppConfig,
    hypothesis: Hypothesis,
    proposal: ExperimentProposal,
) -> None:
    """Refutations are only knowledge if the next round sees them."""
    controller = ResearchController(ResearchRepository(workspace / ".runs", workspace / "projection.db"))
    controller.create_run(config, base_commit_sha="abc123", dataset_fingerprint="f" * 64, run_id=RUN)
    controller.start(RUN, CompetitionWorldModel())

    template = proposal.model_copy(
        update={"run_id": RUN, "experiment_type": ExperimentType.DIAGNOSTIC, "id": "EXP-000"}
    )
    llm = RoundRobinLlm(
        hypothesis.model_copy(update={"run_id": RUN, "type": HypothesisType.VALIDATION}),
        template,
        workspace / "worker.py",
    )
    bridge = ProposalBridge(workspace / ".proposals", ROOT / "prompts")
    loop = AutonomousLoop(
        controller,
        AutomaticProposer(llm, bridge),
        LocalExecutor(workspace, workspace / "results"),
        config=config,
        home=workspace,
        sleep=lambda _: None,
    )
    loop.run(RUN, LoopSettings(rounds=2, poll_seconds=0, timeout_seconds=5))

    context = bridge.experiment_request(RUN, controller.state(RUN)).context
    history = context["falsification_history"]
    assert history, "the designer must see what the falsifier already concluded"
    assert history[0]["strongest_alternative_explanation"]
    assert history[0]["alternative_claims"] == ["the gap is driven by one entity cluster, not by time"]
    assert context["validation_reuse"] is not None
    assert json.dumps(context), "the context must stay JSON-serialisable for the prompt"
