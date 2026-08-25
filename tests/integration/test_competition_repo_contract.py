from __future__ import annotations

import json
from pathlib import Path

import pytest

from epistemic_loop.adapters.executor.competition_repo import CompetitionRepoAdapter
from epistemic_loop.domain.models import DatasetMount, ExperimentRequest, ResourceRequest

#: Words that would tell the receiving repository which system wrote its ticket.
ORCHESTRATOR_VOCABULARY = (
    "epistemic",
    "erl-",
    "erl ",
    "experiment-request",
    "experimentrequest",
    "experimentresult",
    "research_loop",
    "hypothesis",
    "falsif",
    "preregister",
    "belief",
)

BRIEF = {
    "title": "時系列 holdout でのベースラインを測る",
    "objective": "直近の取引を評価に回したときのベースライン性能を出す",
    "approach": "src/solver/experiment.py の train モードを使い、時系列 holdout で学習・評価する",
    "verification": "2 つのシードで再実行し、差が 0.01 未満であることを確認する",
    "metrics": ["roc_auc", "roc_auc_seed_std"],
    "artifacts": ["metrics.json", "seed_metrics.json"],
    "notes": ["直近 200000 行に絞ってよい"],
}


def _request(**changes: object) -> ExperimentRequest:
    payload: dict[str, object] = {
        "request_id": "req-1",
        "experiment_id": "EXP-baseline-timesplit",
        "run_id": "ieee-cis-2026-08",
        "idempotency_key": "ieee-cis-2026-08:EXP-baseline-timesplit:attempt-1",
        "base_commit_sha": "abc123",
        "implementation_mode": "preregistered_experiment",
        "objective": "baseline under a time-ordered split",
        "command": "unused by this executor",
        "container_image": "python:3.11-slim",
        "dataset_mounts": [DatasetMount(name="ieee-cis")],
        "resources": ResourceRequest(),
        "seeds": [11, 23],
        "required_outputs": ["metrics.json"],
        "brief": BRIEF,
    }
    payload.update(changes)
    return ExperimentRequest.model_validate(payload)


def _adapter(repo: Path) -> CompetitionRepoAdapter:
    return CompetitionRepoAdapter(team_id="team-1", project_id="project-1", repo_path=repo)


def test_the_ticket_never_names_the_system_that_wrote_it(tmp_path: Path) -> None:
    """The receiving repository is being developed under instruction, not driven by this loop.

    A ticket that carried this system's schema, identifiers or vocabulary would put a foreign
    contract into a codebase that has no use for it, and would tell the worker it is executing an
    experiment rather than building software. Both are leaks, and this is the assertion that keeps
    the boundary honest as the ticket text evolves.
    """
    body = _adapter(tmp_path).issue_description(_request(), BRIEF)
    lowered = body.lower()
    leaks = [word for word in ORCHESTRATOR_VOCABULARY if word in lowered]
    assert not leaks, f"the ticket leaks orchestrator vocabulary: {leaks}"

    # What it must carry is the control plane's routing convention and the repository's own terms.
    assert body.startswith("workers: solo=claude:opus, handoff=off\n")
    assert f"TARGET_REPO={tmp_path}" in body
    assert "results/exp-baseline-timesplit/metrics.json" in body
    assert BRIEF["objective"] in body and BRIEF["approach"] in body and BRIEF["verification"] in body
    assert "直近 200000 行に絞ってよい" in body
    for metric in BRIEF["metrics"]:
        assert f"`{metric}` を出力する" in body


def test_a_brief_missing_its_required_parts_is_refused(tmp_path: Path) -> None:
    """An underspecified ticket wastes a worker run, so it is refused before it is filed."""
    adapter = _adapter(tmp_path)
    with pytest.raises(ValueError, match="title, objective, approach and verification"):
        adapter.submit(_request(brief={"title": "only a title"}))


def test_the_result_is_assembled_from_the_repository_s_own_convention(tmp_path: Path) -> None:
    """The worker writes `metrics.json`; the envelope is built here.

    Asking a developer to also fill in this system's result schema would push its vocabulary into
    their repository, which is the thing this executor exists to avoid.
    """
    adapter = _adapter(tmp_path)
    request = _request()
    assert adapter.result(request) is None, "no metrics yet means no result, not an empty one"

    destination = adapter.metrics_path(request)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({"roc_auc": 0.913, "roc_auc_seed_std": 0.004, "note": "ignored"}), "utf-8")
    (destination.parent / "seed_metrics.json").write_text("{}", encoding="utf-8")

    result = adapter.result(request)

    assert result is not None
    assert result.status == "completed" and result.exit_code == 0
    assert result.metrics == {"roc_auc": 0.913, "roc_auc_seed_std": 0.004}, "non-numeric entries are dropped"
    assert any(item.endswith("seed_metrics.json") for item in result.artifact_refs)
    assert result.experiment_id == request.experiment_id and result.run_id == request.run_id
    # Ticket recovery needs the Linear API, which the test does not have; it must degrade to None
    # rather than failing the import, but the field has to exist so traceability is possible at all.
    assert "external_ref" in result.model_dump()


def test_an_empty_metrics_file_is_a_failure_not_a_success(tmp_path: Path) -> None:
    """A run that produced no numbers did not answer the question it was filed to answer."""
    adapter = _adapter(tmp_path)
    request = _request()
    destination = adapter.metrics_path(request)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({"note": "could not fit the model"}), encoding="utf-8")

    result = adapter.result(request)

    assert result is not None and result.status == "failed" and result.exit_code == 1


def test_the_tracking_id_is_stable_and_survives_the_round_trip(tmp_path: Path) -> None:
    """A retry must find the ticket it already filed rather than opening a second one."""
    adapter = _adapter(tmp_path)
    first = adapter.issue_description(_request(), BRIEF)
    again = adapter.issue_description(_request(), BRIEF)
    assert first == again

    line = next(item for item in first.splitlines() if item.startswith("Task-ID:"))
    assert line == "Task-ID: ieee-cis-2026-08-exp-baseline-timesplit-attempt-1"

    second_attempt = _request(idempotency_key="ieee-cis-2026-08:EXP-baseline-timesplit:attempt-2")
    assert "attempt-2" in adapter.issue_description(second_attempt, BRIEF)
