from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from epistemic_loop.adapters.executor.base import ExecutorAdapter
from epistemic_loop.domain.models import ExperimentRequest, ExperimentResult

CONTRACT_MARKER = "<!-- epistemic-research-loop:experiment-request:v1 -->"


class AiDevControlPlaneAdapter(ExecutorAdapter):
    """Creates a Linear execution ticket; ai-dev-control-plane consumes its webhook.

    The idempotency key is embedded as a searchable marker. Results are imported from the
    configured artifact/result root, keeping Linear scores out of the research event stream.
    """

    def __init__(
        self,
        *,
        team_id: str,
        project_id: str,
        result_root: str | Path,
        api_key_env: str = "LINEAR_API_KEY",
        api_url: str = "https://api.linear.app/graphql",
    ):
        self.team_id = team_id
        self.project_id = project_id
        self.result_root = Path(result_root)
        self.api_key_env = api_key_env
        self.api_url = api_url

    def _query(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"{self.api_key_env} is not set")
        request = urllib.request.Request(
            self.api_url,
            data=json.dumps({"query": query, "variables": variables}).encode(),
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = json.load(response)
        except urllib.error.URLError as error:
            raise RuntimeError(f"Linear request failed: {error.reason}") from error
        if body.get("errors"):
            raise RuntimeError(f"Linear GraphQL error: {body['errors'][0]['message']}")
        data = body["data"]
        if not isinstance(data, dict):
            raise RuntimeError("Linear GraphQL data must be an object")
        return data

    def _existing(self, idempotency_key: str) -> dict[str, Any] | None:
        marker = f"ERL-IDEMPOTENCY: {idempotency_key}"
        data = self._query(
            """query($query: String!) {
              issueSearch(query: $query, first: 10) {
                nodes { id identifier url description }
              }
            }""",
            {"query": marker},
        )
        return next(
            (
                item
                for item in data.get("issueSearch", {}).get("nodes", [])
                if marker in (item.get("description") or "")
            ),
            None,
        )

    @staticmethod
    def issue_description(request: ExperimentRequest) -> str:
        contract = request.model_dump_json(indent=2)
        return (
            f"{CONTRACT_MARKER}\n"
            f"ERL-IDEMPOTENCY: {request.idempotency_key}\n\n"
            "Execute this preregistered experiment exactly as declared. Do not change its prediction "
            "or decision rule. Write the required outputs and ExperimentResult to the configured artifact store.\n\n"
            f"```json\n{contract}\n```\n"
        )

    def submit(self, request: ExperimentRequest) -> ExperimentResult:
        existing = self._existing(request.idempotency_key)
        if existing is None:
            data = self._query(
                """mutation($input: IssueCreateInput!) {
                  issueCreate(input: $input) { success issue { id identifier url } }
                }""",
                {
                    "input": {
                        "teamId": self.team_id,
                        "projectId": self.project_id,
                        "title": f"[ERL {request.run_id}] {request.objective}",
                        "description": self.issue_description(request),
                    }
                },
            )
            created = data.get("issueCreate", {})
            if not created.get("success") or not created.get("issue"):
                raise RuntimeError("Linear issueCreate did not return an issue")
            existing = created["issue"]
        return ExperimentResult(
            experiment_id=request.experiment_id,
            run_id=request.run_id,
            attempt=1,
            status="queued",
            commit_sha=request.base_commit_sha,
            environment_hash="pending",
            dataset_fingerprint="pending",
            external_ref=existing.get("identifier") or existing.get("id"),
        )

    def result(self, request: ExperimentRequest) -> ExperimentResult | None:
        path = self.result_root / request.run_id / request.experiment_id / "result.json"
        return ExperimentResult.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None
