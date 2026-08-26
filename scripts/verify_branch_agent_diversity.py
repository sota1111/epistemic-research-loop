from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GENERIC_BRANCH = re.compile(r"^agents/workstream-[0-9]+$")


@dataclass(frozen=True)
class AgentSpec:
    run_id: str
    branch: str


def _git(repo: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _signature(proposal: dict[str, Any]) -> str:
    semantic = {
        "experiment_type": proposal["experiment_type"],
        "descriptors": proposal.get("descriptors"),
        "split_strategy": proposal["split_strategy"],
        "command": proposal["implementation_request"].get("command"),
    }
    canonical = json.dumps(semantic, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def verify_agent(home: Path, repository: Path, initial_commit: str, agent: AgentSpec) -> dict[str, Any]:
    event_path = home / ".runs" / agent.run_id / "events.jsonl"
    events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
    proposals = {
        event["payload"]["id"]: event["payload"] for event in events if event["event_type"] == "ExperimentProposed"
    }
    selected_ids = [
        identifier
        for event in events
        if event["event_type"] == "ExperimentSelected"
        for identifier in event["payload"]["selected_experiment_ids"]
    ]
    terminal = {
        event["payload"]["experiment_id"]: event["payload"]["status"]
        for event in events
        if event["event_type"] in {"ExperimentCompleted", "ExperimentFailed"}
    }
    record = json.loads(_git(repository, "show", f"{agent.branch}:research/selected_experiment.json"))
    event_hash = hashlib.sha256(event_path.read_bytes()).hexdigest()
    signatures = [_signature(proposals[identifier]) for identifier in selected_ids]
    branch_head = _git(repository, "rev-parse", agent.branch)
    ancestor = (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", initial_commit, branch_head],
            cwd=repository,
            check=False,
        ).returncode
        == 0
    )
    record_matches = (
        record["run_id"] == agent.run_id
        and record["initial_state_commit"] == initial_commit
        and record["event_log_sha256"] == event_hash
        and record["experiment_id"] in selected_ids
        and record["descriptors"] == proposals[record["experiment_id"]].get("descriptors")
        and record["command"] == proposals[record["experiment_id"]]["implementation_request"].get("command")
    )
    return {
        "run_id": agent.run_id,
        "branch": agent.branch,
        "branch_head": branch_head,
        "generic_branch_name": GENERIC_BRANCH.fullmatch(agent.branch) is not None,
        "initial_commit_is_ancestor": ancestor,
        "event_count": len(events),
        "event_log_sha256": event_hash,
        "selected_experiment_ids": selected_ids,
        "selection_signatures": signatures,
        "selected_terminal_statuses": {identifier: terminal.get(identifier) for identifier in selected_ids},
        "branch_record_matches_event_log": record_matches,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify branch-isolated ERL agents selected different experiments")
    parser.add_argument("--home", type=Path, default=Path("."))
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--initial-commit", required=True)
    parser.add_argument(
        "--agent",
        action="append",
        required=True,
        metavar="RUN_ID=BRANCH",
        help="repeat for each branch-isolated agent",
    )
    arguments = parser.parse_args()
    specs = [AgentSpec(*value.split("=", 1)) for value in arguments.agent]
    agents = [
        verify_agent(arguments.home.resolve(), arguments.repository.resolve(), arguments.initial_commit, spec)
        for spec in specs
    ]
    signatures = [signature for agent in agents for signature in agent["selection_signatures"]]
    checks = {
        "at_least_two_agents": len(agents) >= 2,
        "all_branch_names_generic": all(agent["generic_branch_name"] for agent in agents),
        "all_descend_from_initial_commit": all(agent["initial_commit_is_ancestor"] for agent in agents),
        "all_selected_experiments_completed": all(
            statuses and all(status == "completed" for status in statuses.values())
            for statuses in (agent["selected_terminal_statuses"] for agent in agents)
        ),
        "all_branch_records_match_event_logs": all(agent["branch_record_matches_event_log"] for agent in agents),
        "all_selection_signatures_distinct": len(signatures) == len(set(signatures)),
    }
    result = {"passed": all(checks.values()), "checks": checks, "agents": agents}
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
