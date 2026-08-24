import json

import pytest
from pydantic import ValidationError

from epistemic_loop.adapters.executor.ai_dev_control_plane import CONTRACT_MARKER, AiDevControlPlaneAdapter
from epistemic_loop.domain.models import DatasetMount, ExperimentRequest, ResourceRequest


def _request() -> ExperimentRequest:
    return ExperimentRequest(
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


def test_linear_issue_contains_versioned_idempotent_contract() -> None:
    request = _request()
    body = AiDevControlPlaneAdapter.issue_description(
        request, worker="claude:opus", handoff=False, target_repo="/workspaces/solver"
    )
    # The control plane parses the first line to pick a worker and TARGET_REPO to pick a checkout.
    assert body.startswith("workers: solo=claude:opus, handoff=off\n")
    assert "TARGET_REPO=/workspaces/solver" in body
    assert CONTRACT_MARKER in body
    assert "ERL-IDEMPOTENCY: run-1:exp-1:attempt-1" in body
    for heading in ("## 目的", "## 変更範囲", "## 実装内容", "## 検証内容", "## 受け入れ条件"):
        assert heading in body, f"the worker's ticket must keep the {heading} section"
    assert "compare splits" in body
    assert "`python3 solver.py`" in body
    contract = body.split("```json\n", 1)[1].split("\n```", 1)[0]
    assert json.loads(contract)["network_policy"] == "disabled"


def test_handoff_and_repo_are_omitted_when_not_configured() -> None:
    request = _request()
    body = AiDevControlPlaneAdapter.issue_description(request, worker="codex:gpt-5.6-sol", handoff=True)
    assert body.startswith("workers: solo=codex:gpt-5.6-sol, handoff=on\n")
    assert "TARGET_REPO" not in body


def test_issue_input_carries_the_configured_state() -> None:
    adapter = AiDevControlPlaneAdapter(
        team_id="team-1",
        project_id="project-1",
        result_root="/tmp/results",
        worker="claude:fable",
        target_repo="/workspaces/solver",
        state_id="state-todo",
    )
    payload = adapter.issue_input(_request())
    assert payload["teamId"] == "team-1"
    assert payload["projectId"] == "project-1"
    assert payload["stateId"] == "state-todo"
    assert payload["title"] == "[ERL run-1] compare splits"
    assert payload["description"].startswith("workers: solo=claude:fable, handoff=off")

    without_state = AiDevControlPlaneAdapter(
        team_id="team-1", project_id="project-1", result_root="/tmp/results"
    ).issue_input(_request())
    assert "stateId" not in without_state


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


def test_existing_lookup_avoids_the_deprecated_search_and_matches_the_marker() -> None:
    # Linear answers `deprecated` to issueSearch, which aborted every dispatch; the lookup must use
    # an exact description filter and still confirm the marker on the node it returns.
    adapter = AiDevControlPlaneAdapter(team_id="team-1", project_id="project-1", result_root="/tmp/results")
    seen: list[tuple[str, dict]] = []

    def fake_query(query: str, variables: dict) -> dict:
        seen.append((query, variables))
        return {
            "issues": {
                "nodes": [
                    {"id": "other", "identifier": "SOT-1", "url": "u1", "description": "unrelated ticket"},
                    {
                        "id": "match",
                        "identifier": "SOT-2",
                        "url": "u2",
                        "description": "ERL-IDEMPOTENCY: run-1:exp-1:attempt-1\nbody",
                    },
                ]
            }
        }

    adapter._query = fake_query  # type: ignore[method-assign]
    found = adapter._existing("run-1:exp-1:attempt-1")

    assert found is not None and found["identifier"] == "SOT-2"
    query, variables = seen[0]
    assert "issueSearch" not in query
    assert "description: { contains: $marker }" in query
    assert variables == {"marker": "ERL-IDEMPOTENCY: run-1:exp-1:attempt-1"}


def test_submit_reuses_the_ticket_already_filed_for_the_same_attempt() -> None:
    adapter = AiDevControlPlaneAdapter(team_id="team-1", project_id="project-1", result_root="/tmp/results")
    request = _request()
    calls: list[str] = []

    def fake_query(query: str, variables: dict) -> dict:
        calls.append(query)
        assert "issueCreate" not in query, "a second ticket must never be created for the same attempt"
        return {
            "issues": {
                "nodes": [
                    {
                        "id": "match",
                        "identifier": "SOT-2",
                        "url": "u2",
                        "description": f"ERL-IDEMPOTENCY: {request.idempotency_key}",
                    }
                ]
            }
        }

    adapter._query = fake_query  # type: ignore[method-assign]
    result = adapter.submit(request)

    assert result.external_ref == "SOT-2"
    assert result.status == "queued"
    assert len(calls) == 1
