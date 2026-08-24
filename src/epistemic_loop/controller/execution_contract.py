from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, cast

from epistemic_loop.domain.models import (
    DatasetMount,
    ExperimentProposal,
    ExperimentRequest,
    ResearchRun,
    ResourceRequest,
)

NETWORK_POLICIES = ("disabled", "source_policy_proxy", "enabled")


def idempotency_key(run_id: str, experiment_id: str, attempt: int) -> str:
    if attempt < 1:
        raise ValueError("attempt must start at 1")
    return f"{run_id}:{experiment_id}:attempt-{attempt}"


def build_experiment_request(
    run: ResearchRun,
    proposal: ExperimentProposal,
    *,
    attempt: int = 1,
    container_image: str,
    dataset_mounts: Sequence[str] = (),
    network_policy: str = "disabled",
) -> ExperimentRequest:
    """Translate a preregistered proposal into the versioned worker contract.

    The prediction and decision rule stay in the research log; the worker receives only what it
    needs to reproduce the run, so it cannot silently redefine what the experiment tests.
    """
    request: dict[str, Any] = proposal.implementation_request
    command = str(request.get("command", "")).strip()
    if not command:
        raise ValueError(f"experiment {proposal.id} has no implementation_request.command")
    if network_policy not in NETWORK_POLICIES:
        raise ValueError(f"unknown network policy: {network_policy}")

    resources = request.get("resources")
    resource_request = ResourceRequest.model_validate(resources) if isinstance(resources, dict) else ResourceRequest()
    mounts = request.get("dataset_mounts")
    mount_names = [str(item) for item in mounts] if isinstance(mounts, list) else list(dataset_mounts)

    return ExperimentRequest(
        request_id=f"REQ-{uuid.uuid4().hex[:12]}",
        experiment_id=proposal.id,
        run_id=run.id,
        idempotency_key=idempotency_key(run.id, proposal.id, attempt),
        base_commit_sha=run.base_commit_sha,
        implementation_mode=str(request.get("implementation_mode", "preregistered_experiment")),
        objective=str(request.get("objective") or proposal.research_question),
        command=command,
        container_image=str(request.get("container_image") or container_image),
        dataset_mounts=[DatasetMount(name=name) for name in mount_names],
        resources=resource_request,
        seeds=list(proposal.seeds),
        required_outputs=list(proposal.required_artifacts),
        network_policy=cast(Any, str(request.get("network_policy") or network_policy)),
    )
