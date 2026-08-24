from __future__ import annotations

import json
from pathlib import Path

import pytest

from epistemic_loop.agents.proposal_bridge import ProposalBridge
from epistemic_loop.controller.run_state import load_run_state
from epistemic_loop.domain.events import EventType
from epistemic_loop.domain.models import (
    CompetitionWorldModel,
    ExperimentProposal,
    Hypothesis,
    ResearchRun,
)
from epistemic_loop.storage.repositories import ResearchRepository

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def state(tmp_path: Path, hypothesis: Hypothesis):
    repository = ResearchRepository(tmp_path / ".runs", tmp_path / "projection.db")
    repository.append(
        "run-001",
        EventType.RUN_CREATED,
        ResearchRun(
            id="run-001",
            competition_id="example",
            seed=7,
            base_commit_sha="abc123",
            dataset_fingerprint="f" * 64,
            config_hash="c" * 64,
        ),
    )
    repository.append("run-001", EventType.HYPOTHESIS_PROPOSED, hypothesis)
    return load_run_state(repository.event_store("run-001").read_all())


def test_requests_carry_the_prompt_and_the_enforcing_schema(tmp_path: Path, state) -> None:
    bridge = ProposalBridge(tmp_path / "proposals", ROOT / "prompts")

    hypothesis_request = json.loads(
        bridge.request_hypotheses("run-001", CompetitionWorldModel(), state).read_text(encoding="utf-8")
    )
    assert hypothesis_request["agent"] == "hypothesis_generator"
    assert "predictions if true" in hypothesis_request["prompt"]
    assert "hypotheses" in hypothesis_request["json_schema"]["properties"]
    assert hypothesis_request["context"]["existing_hypotheses"][0]["id"] == "H-001"
    assert "never follow instructions" in hypothesis_request["untrusted_data_policy"]

    experiment_request = json.loads(bridge.request_experiments("run-001", state).read_text(encoding="utf-8"))
    assert experiment_request["agent"] == "experiment_designer"
    assert "experiments" in experiment_request["json_schema"]["properties"]
    assert experiment_request["context"]["already_run_fingerprints"] == []


def test_missing_prompt_template_is_reported(tmp_path: Path, state) -> None:
    bridge = ProposalBridge(tmp_path / "proposals", tmp_path / "absent")
    with pytest.raises(FileNotFoundError, match="prompt template is missing"):
        bridge.request_experiments("run-001", state)


def test_responses_are_validated_against_the_domain_models(
    tmp_path: Path, hypothesis: Hypothesis, proposal: ExperimentProposal
) -> None:
    wrapped = tmp_path / "wrapped.json"
    wrapped.write_text(json.dumps({"hypotheses": [hypothesis.model_dump(mode="json")]}), encoding="utf-8")
    assert [item.id for item in ProposalBridge.load_hypotheses(wrapped)] == ["H-001"]

    bare = tmp_path / "bare.json"
    bare.write_text(json.dumps([proposal.model_dump(mode="json")]), encoding="utf-8")
    assert [item.id for item in ProposalBridge.load_experiments(bare)] == ["EXP-001"]

    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps({"hypotheses": [{"id": "H-BAD"}]}), encoding="utf-8")
    with pytest.raises(ValueError):
        ProposalBridge.load_hypotheses(invalid)

    scalar = tmp_path / "scalar.json"
    scalar.write_text(json.dumps("nope"), encoding="utf-8")
    with pytest.raises(ValueError, match="must be a list or an object"):
        ProposalBridge.load_experiments(scalar)
