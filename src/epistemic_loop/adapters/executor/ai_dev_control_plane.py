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
        worker: str = "claude:opus",
        handoff: bool = False,
        target_repo: str | None = None,
        state_id: str | None = None,
        api_key_env: str = "LINEAR_API_KEY",
        api_url: str = "https://api.linear.app/graphql",
    ):
        self.team_id = team_id
        self.project_id = project_id
        self.result_root = Path(result_root)
        self.worker = worker
        self.handoff = handoff
        self.target_repo = target_repo
        self.state_id = state_id
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
        """Find the ticket already filed for this attempt, so a retry never files a second one.

        The lookup is an exact substring filter rather than full-text search: `issueSearch` is
        deprecated in Linear's API (it answers `deprecated` and the dispatch aborts), and its
        ranked, fuzzy matching could push the one issue that matters out of the page. The
        description check is kept so a filter that ever loosens cannot resurrect a wrong ticket.
        """
        marker = f"ERL-IDEMPOTENCY: {idempotency_key}"
        data = self._query(
            """query($marker: String!) {
              issues(filter: { description: { contains: $marker } }, first: 10) {
                nodes { id identifier url description }
              }
            }""",
            {"marker": marker},
        )
        return next(
            (item for item in data.get("issues", {}).get("nodes", []) if marker in (item.get("description") or "")),
            None,
        )

    @staticmethod
    def issue_description(
        request: ExperimentRequest,
        *,
        worker: str = "claude:opus",
        handoff: bool = False,
        target_repo: str | None = None,
    ) -> str:
        """Render the control plane's native ticket, with the contract embedded verbatim.

        The `workers:` header and `TARGET_REPO=` line are what ai-dev-control-plane parses to pick
        a worker and a checkout; the Markdown sections are what that worker reads. The execution
        contract stays in the body as machine-readable JSON so the research loop and the worker
        agree on exactly one description of the experiment.
        """
        mounts = ", ".join(mount.name for mount in request.dataset_mounts) or "なし"
        seeds = ", ".join(str(seed) for seed in request.seeds)
        outputs = "\n".join(f"* `{name}`" for name in request.required_outputs)
        checklist = "\n".join(f"- [ ] `{name}` を出力する" for name in request.required_outputs)
        repo_line = f"TARGET_REPO={target_repo}\n\n" if target_repo else ""
        return (
            f"workers: solo={worker}, handoff={'on' if handoff else 'off'}\n\n"
            f"{repo_line}"
            f"{CONTRACT_MARKER}\n"
            f"ERL-IDEMPOTENCY: {request.idempotency_key}\n\n"
            "## 目的\n\n"
            f"{request.objective}\n\n"
            "## 変更範囲\n\n"
            f"{outputs}\n\n"
            "## 実装内容\n\n"
            f"* コマンド: `{request.command}`\n"
            f"* コンテナ: `{request.container_image}`\n"
            f"* シード: {seeds}\n"
            f"* データマウント（読み取り専用）: {mounts}\n"
            f"* ネットワーク: {request.network_policy}\n\n"
            "## 検証内容\n\n"
            "* 事前登録された予測と判定規則は**変更しない**。実験は宣言どおりに実行する。\n"
            "* 必須成果物を `ERL_OUTPUT_DIR` に書き出す。\n"
            "* `ExperimentResult` を result store に書く。研究ループがそこから結果を取り込む。\n\n"
            "## 受け入れ条件\n\n"
            f"{checklist}\n"
            "- [ ] `result.json` に `ExperimentResult` を書く\n"
            "- [ ] 予測・判定規則・シード・split を変更していない\n\n"
            "## 実行契約（機械可読・変更禁止）\n\n"
            f"```json\n{request.model_dump_json(indent=2)}\n```\n"
        )

    def issue_input(self, request: ExperimentRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "teamId": self.team_id,
            "projectId": self.project_id,
            "title": f"[ERL {request.run_id}] {request.objective}",
            "description": self.issue_description(
                request,
                worker=self.worker,
                handoff=self.handoff,
                target_repo=self.target_repo,
            ),
        }
        if self.state_id:
            payload["stateId"] = self.state_id
        return payload

    def submit(self, request: ExperimentRequest) -> ExperimentResult:
        existing = self._existing(request.idempotency_key)
        if existing is None:
            data = self._query(
                """mutation($input: IssueCreateInput!) {
                  issueCreate(input: $input) { success issue { id identifier url } }
                }""",
                {"input": self.issue_input(request)},
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
