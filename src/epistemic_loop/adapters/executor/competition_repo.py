from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from epistemic_loop.adapters.executor.base import ExecutorAdapter
from epistemic_loop.domain.models import ExperimentRequest, ExperimentResult

#: Ordinary-looking tracking id. It is how a retry finds the ticket it already filed, and it reads
#: as project bookkeeping rather than as a foreign system's contract.
TASK_MARKER = "Task-ID"


class CompetitionRepoAdapter(ExecutorAdapter):
    """Files an ordinary development ticket against a competition repository.

    The worker fleet on the other side is developing that repository under instruction. It has no
    reason to know which system wrote the instruction, and telling it would be a leak in both
    directions: the ticket would carry a foreign schema the repository does not use, and the
    research loop's identifiers would end up in a codebase that has nothing to do with it.

    So the ticket says what to build and where to leave the numbers, in the competition
    repository's own terms. No embedded execution contract, no orchestrator identifiers, no command
    to run verbatim -- the worker is a developer, not a shell.

    Results come back through the repository itself: `results/<experiment>/metrics.json`, which is
    that repository's own documented convention. This adapter reads it and reports the outcome; it
    does not ask the worker to fill in a schema it would otherwise never see.
    """

    def __init__(
        self,
        *,
        team_id: str,
        project_id: str,
        repo_path: str | Path,
        results_subdir: str = "results",
        worker: str = "claude:opus",
        handoff: bool = False,
        state_id: str | None = None,
        api_key_env: str = "LINEAR_API_KEY",
        api_url: str = "https://api.linear.app/graphql",
    ):
        self.team_id = team_id
        self.project_id = project_id
        self.repo_path = Path(repo_path)
        self.results_subdir = results_subdir
        self.worker = worker
        self.handoff = handoff
        self.state_id = state_id
        self.api_key_env = api_key_env
        self.api_url = api_url

    # ------------------------------------------------------------------ linear

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
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.load(response)
        except urllib.error.URLError as error:
            raise RuntimeError(f"Linear request failed: {error.reason}") from error
        if body.get("errors"):
            raise RuntimeError(f"Linear GraphQL error: {body['errors'][0]['message']}")
        data = body["data"]
        if not isinstance(data, dict):
            raise RuntimeError("Linear GraphQL data must be an object")
        return data

    def _existing(self, task_id: str) -> dict[str, Any] | None:
        marker = f"{TASK_MARKER}: {task_id}"
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

    # ------------------------------------------------------------------ ticket

    @staticmethod
    def _task_id(request: ExperimentRequest) -> str:
        """A tracking id that carries no orchestrator vocabulary."""
        return re.sub(r"[^A-Za-z0-9]+", "-", request.idempotency_key).strip("-").lower()

    def experiment_name(self, request: ExperimentRequest) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "-", request.experiment_id).strip("-").lower()

    def issue_description(self, request: ExperimentRequest, brief: dict[str, Any]) -> str:
        """Render the task the way the competition repository's own tracker would.

        `brief` carries the human-readable content: what to measure, how, and what counts as done.
        Nothing in the body names the system that produced it.
        """
        name = self.experiment_name(request)
        results = f"{self.results_subdir}/{name}"
        metrics = brief.get("metrics") or []
        checklist = "\n".join(f"- [ ] `{results}/metrics.json` に `{metric}` を出力する" for metric in metrics)
        artifacts = "\n".join(f"* `{results}/{item}`" for item in brief.get("artifacts", ["metrics.json"]))
        seeds = ", ".join(str(seed) for seed in request.seeds)
        notes = "\n".join(f"* {line}" for line in brief.get("notes", []))
        return (
            f"workers: solo={self.worker}, handoff={'on' if self.handoff else 'off'}\n\n"
            f"TARGET_REPO={self.repo_path}\n\n"
            "## 目的\n\n"
            f"{brief['objective']}\n\n"
            "## 変更範囲\n\n"
            f"{artifacts}\n\n"
            "## 実装内容\n\n"
            f"{brief['approach']}\n\n"
            f"* 乱数シード: {seeds}\n"
            f"* 出力ディレクトリ: `{results}`（無ければ作成する）\n"
            f"{notes}\n\n"
            "## 検証内容\n\n"
            f"{brief['verification']}\n\n"
            "`results/<name>/metrics.json` は指標名から数値へのフラットな JSON。"
            "リポジトリの README に定義された唯一の下流インターフェースなので、"
            "実行できてもこれが無い場合は未完了として扱う。\n\n"
            "## 受け入れ条件\n\n"
            f"{checklist}\n"
            "- [ ] 上記以外の指標や内訳も同じディレクトリに併置する\n"
            "- [ ] 指定された split・シード・特徴方針を変更しない\n\n"
            f"{TASK_MARKER}: {self._task_id(request)}\n"
        )

    def issue_input(self, request: ExperimentRequest, brief: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "teamId": self.team_id,
            "projectId": self.project_id,
            "title": brief["title"],
            "description": self.issue_description(request, brief),
        }
        if self.state_id:
            payload["stateId"] = self.state_id
        return payload

    # ----------------------------------------------------------------- execute

    def submit(self, request: ExperimentRequest) -> ExperimentResult:
        brief = request.brief
        if not {"title", "objective", "approach", "verification"} <= set(brief):
            raise ValueError(
                "competition_repo executor needs implementation_request.brief with "
                "title, objective, approach and verification"
            )
        existing = self._existing(self._task_id(request))
        if existing is None:
            data = self._query(
                """mutation($input: IssueCreateInput!) {
                  issueCreate(input: $input) { success issue { id identifier url } }
                }""",
                {"input": self.issue_input(request, brief)},
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

    def metrics_path(self, request: ExperimentRequest) -> Path:
        return self.repo_path / self.results_subdir / self.experiment_name(request) / "metrics.json"

    def result(self, request: ExperimentRequest) -> ExperimentResult | None:
        """Build the result from what the repository produced, not from a schema the worker filled.

        The competition repository's contract is `metrics.json`. Asking a developer to also write an
        orchestrator's result envelope would put this system's vocabulary into their codebase, so
        the envelope is assembled here instead.
        """
        path = self.metrics_path(request)
        if not path.is_file():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"{path} must contain a flat object of metric name to number")
        metrics = {str(key): float(value) for key, value in raw.items() if isinstance(value, (int, float))}
        directory = path.parent
        return ExperimentResult(
            experiment_id=request.experiment_id,
            run_id=request.run_id,
            attempt=1,
            status="completed" if metrics else "failed",
            exit_code=0 if metrics else 1,
            commit_sha=_head_commit(self.repo_path) or request.base_commit_sha,
            environment_hash="competition-repo",
            dataset_fingerprint="competition-repo",
            metrics=metrics,
            artifact_refs=sorted(str(item) for item in directory.iterdir() if item.is_file()),
            runtime={},
        )


def _head_commit(repo: Path) -> str | None:
    """The competition repository's own HEAD, so a result is attributable to the code that made it."""
    import subprocess

    try:
        return subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
