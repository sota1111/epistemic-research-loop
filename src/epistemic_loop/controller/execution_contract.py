from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, cast

from epistemic_loop.adapters.executor.base import SHELL_CONTRACT, ExecutionContract
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
    contract: ExecutionContract = SHELL_CONTRACT,
) -> ExperimentRequest:
    """Translate a preregistered proposal into the versioned worker contract.

    The prediction and decision rule stay in the research log; the worker receives only what it
    needs to reproduce the run, so it cannot silently redefine what the experiment tests.
    """
    request: dict[str, Any] = proposal.implementation_request
    command = str(request.get("command", "")).strip()
    # Whether a command is required is the executor's contract, not a property of every request.
    # Demanding one unconditionally rejected a perfectly good brief-shaped proposal at the last
    # step before dispatch -- after the gate had already accepted it against the right contract.
    missing = [name for name in contract.required_fields if not request.get(name)]
    if missing:
        raise ValueError(
            f"experiment {proposal.id} is missing implementation_request{missing}, which the "
            f"configured executor requires. {contract.note}"
        )
    brief_value = request.get("brief")
    if contract.required_brief_fields:
        if not isinstance(brief_value, dict):
            raise ValueError(f"experiment {proposal.id} has an implementation_request.brief that is not an object")
        absent = [name for name in contract.required_brief_fields if not str(brief_value.get(name) or "").strip()]
        if absent:
            raise ValueError(f"experiment {proposal.id} has a brief missing {absent}")
    if network_policy not in NETWORK_POLICIES:
        raise ValueError(f"unknown network policy: {network_policy}")

    resources = dict(request.get("resources") or {}) if isinstance(request.get("resources"), dict) else {}
    if proposal.resource_estimate is not None:
        estimate = proposal.resource_estimate
        resources.setdefault("cpu", estimate.cpu_cores)
        resources.setdefault("memory_gb", estimate.memory_gb)
        resources.setdefault("gpu_memory_gb", estimate.gpu_memory_gb)
        resources.setdefault("expected_minutes", estimate.expected_minutes)
        resources.setdefault("parquet_scan_columns", estimate.parquet_scan_columns)
        resources.setdefault("full_table_materialization", estimate.full_table_materialization)
        resources.setdefault("timeout_seconds", max(1, int(estimate.expected_minutes * 60 * 2)))
    resource_request = ResourceRequest.model_validate(resources) if resources else ResourceRequest()
    mounts = request.get("dataset_mounts")
    mount_names = [str(item) for item in mounts] if isinstance(mounts, list) else list(dataset_mounts)

    return ExperimentRequest(
        request_id=f"REQ-{uuid.uuid4().hex[:12]}",
        experiment_id=proposal.id,
        run_id=run.id,
        idempotency_key=idempotency_key(run.id, proposal.id, attempt),
        base_commit_sha=run.base_commit_sha,
        config_hash=run.config_hash,
        dataset_fingerprint=run.dataset_fingerprint,
        system_mode=run.mode,
        implementation_mode=str(request.get("implementation_mode", "preregistered_experiment")),
        objective=str(request.get("objective") or proposal.research_question),
        command=command,
        container_image=str(request.get("container_image") or container_image),
        dataset_mounts=[DatasetMount(name=name) for name in mount_names],
        resources=resource_request,
        seeds=list(proposal.seeds),
        required_outputs=list(proposal.required_artifacts),
        network_policy=cast(Any, str(request.get("network_policy") or network_policy)),
        brief=cast("dict[str, Any]", brief) if isinstance(brief := request.get("brief"), dict) else {},
        candidate_producing=proposal.candidate_producing,
        semantic_signature=proposal.semantic_signature,
        epistemic_niche=proposal.epistemic_niche,
    )
