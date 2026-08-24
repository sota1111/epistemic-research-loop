import json

import pytest
from pydantic import ValidationError

from epistemic_loop.adapters.executor.ai_dev_control_plane import CONTRACT_MARKER, AiDevControlPlaneAdapter
from epistemic_loop.domain.models import DatasetMount, ExperimentRequest, ResourceRequest


def test_linear_issue_contains_versioned_idempotent_contract() -> None:
    request = ExperimentRequest(
        request_id="req-1",
        experiment_id="exp-1",
        run_id="run-1",
        idempotency_key="run-1:exp-1:attempt-1",
        base_commit_sha="abc",
        implementation_mode="patch_existing_solver",
        objective="compare splits",
        command="python3 solver.py",
        container_image="solver:sha256-1",
        dataset_mounts=[DatasetMount(name="data")],
        resources=ResourceRequest(),
        seeds=[11, 23],
        required_outputs=["metrics.json"],
    )
    body = AiDevControlPlaneAdapter.issue_description(request)
    assert CONTRACT_MARKER in body
    assert "ERL-IDEMPOTENCY: run-1:exp-1:attempt-1" in body
    contract = body.split("```json\n", 1)[1].split("\n```", 1)[0]
    assert json.loads(contract)["network_policy"] == "disabled"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"idempotency_key": "another-run:exp-1:attempt-1"}, "scoped"),
        ({"idempotency_key": "run-1:exp-1:attempt-0"}, "attempt-N"),
        ({"seeds": [11, 11]}, "unique"),
        ({"required_outputs": ["../private-score.json"]}, "safe relative paths"),
        ({"dataset_mounts": [{"name": "data", "read_only": False}]}, "Input should be True"),
    ],
)
def test_invalid_execution_contract_is_rejected_at_source(changes, message) -> None:
    payload = {
        "request_id": "req-1",
        "experiment_id": "exp-1",
        "run_id": "run-1",
        "idempotency_key": "run-1:exp-1:attempt-1",
        "base_commit_sha": "abc",
        "implementation_mode": "patch_existing_solver",
        "objective": "compare splits",
        "command": "python3 solver.py",
        "container_image": "solver:sha256-1",
        "dataset_mounts": [{"name": "data", "read_only": True}],
        "resources": {},
        "seeds": [11, 23],
        "required_outputs": ["metrics.json"],
    }
    payload.update(changes)

    with pytest.raises(ValidationError, match=message):
        ExperimentRequest.model_validate(payload)
