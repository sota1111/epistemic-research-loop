from __future__ import annotations

import pytest

from epistemic_loop.controller.execution_contract import build_experiment_request, idempotency_key
from epistemic_loop.domain.models import ExperimentProposal, ResearchRun


def _run() -> ResearchRun:
    return ResearchRun(
        id="run-001",
        competition_id="example",
        seed=7,
        base_commit_sha="abc123",
        dataset_fingerprint="f" * 64,
        config_hash="c" * 64,
    )


def test_idempotency_key_is_scoped_and_attempt_numbered() -> None:
    assert idempotency_key("run-001", "EXP-001", 2) == "run-001:EXP-001:attempt-2"
    with pytest.raises(ValueError, match="attempt must start at 1"):
        idempotency_key("run-001", "EXP-001", 0)


def test_contract_carries_seeds_outputs_and_defaults(proposal: ExperimentProposal) -> None:
    request = build_experiment_request(_run(), proposal, container_image="research:1")
    assert request.idempotency_key == "run-001:EXP-001:attempt-1"
    assert request.command == "python3 solver.py"
    assert request.container_image == "research:1"
    assert request.seeds == proposal.seeds
    assert request.required_outputs == proposal.required_artifacts
    assert request.objective == proposal.research_question
    assert request.network_policy == "disabled"
    assert request.dataset_mounts == []


def test_implementation_request_overrides_defaults(proposal: ExperimentProposal, clone_proposal) -> None:
    candidate = clone_proposal(
        proposal,
        implementation_request={
            "command": "uv run train.py",
            "objective": "explicit objective",
            "container_image": "override:2",
            "resources": {"cpu": 4, "memory_gb": 16, "timeout_seconds": 900},
            "dataset_mounts": ["train", "test"],
            "network_policy": "source_policy_proxy",
        },
    )
    request = build_experiment_request(_run(), candidate, container_image="research:1", dataset_mounts=["ignored"])
    assert request.objective == "explicit objective"
    assert request.container_image == "override:2"
    assert request.resources.cpu == 4
    assert request.resources.timeout_seconds == 900
    assert [mount.name for mount in request.dataset_mounts] == ["train", "test"]
    assert request.network_policy == "source_policy_proxy"


def test_missing_command_and_unknown_network_policy_are_rejected(proposal: ExperimentProposal, clone_proposal) -> None:
    without_command = clone_proposal(proposal, implementation_request={"objective": "x"})
    with pytest.raises(ValueError, match="implementation_request.command"):
        build_experiment_request(_run(), without_command, container_image="research:1")
    with pytest.raises(ValueError, match="unknown network policy"):
        build_experiment_request(_run(), proposal, container_image="research:1", network_policy="wide-open")


def test_configured_dataset_mounts_are_used_when_the_proposal_is_silent(
    proposal: ExperimentProposal,
) -> None:
    request = build_experiment_request(
        _run(), proposal, container_image="research:1", dataset_mounts=["competition-data"]
    )
    assert [mount.name for mount in request.dataset_mounts] == ["competition-data"]
    assert all(mount.read_only for mount in request.dataset_mounts)
