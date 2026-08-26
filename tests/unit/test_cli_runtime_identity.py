from __future__ import annotations

import subprocess
from pathlib import Path

from epistemic_loop.adapters.llm.cli import CliStructuredLlm
from epistemic_loop.cli import _git_sha, _llm
from epistemic_loop.config import AppConfig, CompetitionConfig, LlmConfig, RunConfig


def test_git_identity_comes_from_the_executor_workspace(tmp_path: Path) -> None:
    repository = tmp_path / "competition"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repository, check=True)
    (repository / "README.md").write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=repository, check=True)

    expected = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert _git_sha(repository) == expected


def test_cli_transcripts_are_namespaced_by_run(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ERL_HOME", str(tmp_path))
    config = AppConfig(
        run=RunConfig(id="branch-agent-02"),
        competition=CompetitionConfig(slug="example", metric_direction="maximize"),
        llm=LlmConfig(adapter="cli", cli_preset="claude", store_raw_response=True),
    )

    adapter = _llm(config, run_id="branch-agent-02")

    assert isinstance(adapter, CliStructuredLlm)
    assert adapter.transcript_dir == str(tmp_path / ".proposals" / "transcripts" / "branch-agent-02")
