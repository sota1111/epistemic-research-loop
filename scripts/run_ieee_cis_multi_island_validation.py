#!/usr/bin/env python3
"""Run the branch-isolated IEEE-CIS C-lite v0.2 validation campaign.

The agents create code independently.  This controller reads their preregistered proposals only
after all branches are ready, admits them through the semantic/resource gates, and runs every heavy
candidate sequentially.  It deliberately does not expose another agent's score or candidate while
the campaign is running.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any

import yaml

from epistemic_loop.controller.candidate_artifacts import (
    CandidateArtifactValidator,
    candidate_required_outputs,
)
from epistemic_loop.controller.diversity_control import effective_count, semantic_similarity
from epistemic_loop.controller.multi_island_loop import MultiIslandResearchLoop
from epistemic_loop.controller.resource_scheduler import ResourceScheduler
from epistemic_loop.domain.enums import (
    Direction,
    EpistemicNiche,
    ExperimentKind,
    ExperimentType,
    TerminalStatus,
)
from epistemic_loop.domain.models import (
    AgentBeliefState,
    AgentNicheAssignment,
    CandidateArtifactRecord,
    CandidateDescriptors,
    CollapseMetrics,
    CostEstimate,
    DecisionBinding,
    EpistemicAssessment,
    ExperimentProposal,
    ExperimentResult,
    LocalHypothesisBelief,
    PredictedOutcome,
    RemainingBudget,
    ResourceEstimate,
    RobustnessAssessment,
    ScoreEstimate,
    SemanticExperimentSignature,
)

BASE_REF = "initial/ieee-cis-state"
BASE_SHA = "ac3b46975e5da64570fb79d6e1141bc5c7525d0f"
RUN_ID = "ieee-cis-v02-multi-island-20260826"
PYTHON = "/workspaces/kaggle-ieee-cis-fraud-detection/.venv/bin/python"


@dataclass(frozen=True)
class Island:
    agent_id: str
    branch: str
    worktree: Path
    proposal_path: Path
    primary_niche: EpistemicNiche
    secondary_niche: EpistemicNiche
    representation: str
    error_profile: str
    command_overrides: dict[str, str]


def islands(worktree_root: Path, sample: int, estimators: int) -> tuple[Island, ...]:
    return (
        Island(
            agent_id="agent-04",
            branch="agents/agent-04",
            worktree=worktree_root / "agent-04",
            proposal_path=Path("proposals/agent-04.yaml"),
            primary_niche=EpistemicNiche.TEMPORAL,
            secondary_niche=EpistemicNiche.VALIDATION,
            representation="causal_client_history",
            error_profile="temporal_generalization",
            command_overrides={
                "--sample": str(sample),
                "--n-estimators": str(estimators),
                "--max-v-features": "48",
                "--threads": "4",
            },
        ),
        Island(
            agent_id="agent-05",
            branch="agents/agent-05",
            worktree=worktree_root / "agent-05",
            proposal_path=Path("proposals/agent-05.yaml"),
            primary_niche=EpistemicNiche.ENTITY_CLIENT,
            secondary_niche=EpistemicNiche.FEATURE_REPRESENTATION,
            representation="multi_resolution_client_memory",
            error_profile="known_new_client",
            command_overrides={
                # Seven embargo days do not leave a valid warm-up window in the 40k tail sample.
                # Preserve the agent's preregistered 200k resource profile instead of weakening the gap.
                "--sample": str(max(sample, 200_000)),
                "--n-estimators": str(estimators),
                "--max-base-features": "64",
                "--n-jobs": "4",
            },
        ),
        Island(
            agent_id="agent-06",
            branch="agents/agent-06",
            worktree=worktree_root / "agent-06",
            proposal_path=Path("proposals/agent-06.yaml"),
            primary_niche=EpistemicNiche.MODEL_FAMILY,
            secondary_niche=EpistemicNiche.FALSIFICATION,
            representation="paired_family_gate",
            error_profile="new_client_model_family",
            command_overrides={
                "--sample": str(sample),
                "--n-estimators": str(max(40, estimators // 2)),
                "--max-features": "80",
                "--n-jobs": "1",
            },
        ),
    )


def mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return value


def terms(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError(f"semantic signature term must be a string or list of strings: {value!r}")


def signature(payload: dict[str, Any]) -> SemanticExperimentSignature:
    raw = payload.get("semantic_signature")
    if not isinstance(raw, dict):
        raise ValueError("proposal requires semantic_signature")
    return SemanticExperimentSignature(
        target_hypotheses=terms(raw.get("target_hypotheses")),
        data_slice=terms(raw.get("data_slice")),
        operation=terms(raw.get("operation")),
        observable=terms(raw.get("observable")),
        decision_affected=terms(raw.get("decision_affected")),
        candidate_producing=raw.get("candidate_producing") is True,
    )


def private_claim(payload: dict[str, Any]) -> str:
    raw = payload.get("private_hypothesis")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        for key in ("statement", "claim"):
            if isinstance(raw.get(key), str):
                return raw[key]
    raise ValueError("proposal requires a private hypothesis statement")


def numeric_max(value: object, fallback: float, *, upper_bound: float | None = None) -> float:
    numbers = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", str(value))]
    if upper_bound is not None:
        numbers = [item for item in numbers if item <= upper_bound]
    return max(numbers, default=fallback)


def resource_estimate(payload: dict[str, Any], island: Island) -> ResourceEstimate:
    raw = payload.get("resource_estimate")
    if not isinstance(raw, dict):
        raise ValueError("proposal requires resource_estimate")
    memory = numeric_max(raw.get("peak_ram_gb", raw.get("peak_ram", 6)), 6, upper_bound=256)
    cpu = int(
        numeric_max(
            raw.get("threads", raw.get("cpu_threads", raw.get("cpu", 1))),
            1,
            upper_bound=256,
        )
    )
    minutes = numeric_max(
        raw.get("wall_time_minutes", raw.get("wall_clock", 60)),
        60,
        upper_bound=600,
    )
    scan_columns = int(
        numeric_max(
            raw.get("raw_column_cap_approx", raw.get("raw_feature_limit", raw.get("parquet_scan_columns", 120))),
            120,
        )
    )
    if island.agent_id == "agent-04":
        cpu = 4
    return ResourceEstimate(
        cpu_cores=cpu,
        memory_gb=memory,
        expected_minutes=minutes,
        parquet_scan_columns=scan_columns,
        full_table_materialization=False,
        heavy=True,
    )


def command(payload: dict[str, Any], island: Island) -> tuple[list[str], Path]:
    raw = payload.get("command")
    if not isinstance(raw, list) or not raw or not all(isinstance(item, str) for item in raw):
        raise ValueError("proposal command must be a non-empty argv list")
    argv = list(raw)
    argv[0] = PYTHON
    for option, replacement in island.command_overrides.items():
        if option in argv:
            argv[argv.index(option) + 1] = replacement
    output_index = argv.index("--output") + 1
    output = Path(argv[output_index])
    if not output.is_absolute():
        output = island.worktree / output
    argv[output_index] = str(output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite an existing candidate: {output}")
    return argv, output


def build_proposal(
    island: Island,
    payload: dict[str, Any],
    argv: list[str],
    estimate: ResourceEstimate,
) -> ExperimentProposal:
    semantic = signature(payload)
    if not semantic.candidate_producing:
        raise ValueError(f"{island.agent_id} did not propose a candidate-producing experiment")
    predicted = PredictedOutcome(
        description="the preregistered forward and subgroup metrics determine candidate eligibility",
        metric_name="primary_score",
        expected_direction=Direction.PATTERN,
        condition="at least three forward fraud-label horizons with a non-zero time gap",
    )
    seed_index = argv.index("--seed") + 1
    return ExperimentProposal(
        id=str(payload.get("proposal_id", f"{island.agent_id}-candidate")),
        run_id=RUN_ID,
        proposer_agent=island.agent_id,
        experiment_type=ExperimentType.EPISTEMIC,
        experiment_kind=ExperimentKind.CANDIDATE_PRODUCING,
        candidate_producing=True,
        epistemic_niche=island.primary_niche,
        semantic_signature=semantic,
        resource_estimate=estimate,
        hypothesis_ids=[f"{island.agent_id}-H-001"],
        research_question=private_claim(payload),
        protocol="preregistered candidate pipeline with multi-horizon forward-gap fraud validation",
        controls=["no hidden score", "no test label", "fold-local learned transforms"],
        split_strategy="multi_horizon_forward_gap",
        seeds=[int(argv[seed_index])],
        metrics=["primary_score", "known_client_auc", "new_client_auc"],
        predicted_outcomes=[predicted],
        decision_rule=str(payload.get("decision_binding", "promote only when preregistered gates pass")),
        decision_binding=DecisionBinding(
            decision_id=f"DEC-{island.agent_id}",
            possible_actions=["promote", "reject"],
            result_to_action={"gate_passed": "promote", "gate_failed": "reject"},
        ),
        expected_score_gain=ScoreEstimate(mean_gain=0, uncertainty=1),
        epistemic_assessment=EpistemicAssessment(
            hypothesis_discrimination=3,
            uncertainty_reduction=3,
            decision_consequence=4,
            search_space_reduction=2,
            outcome_observability=4,
            rationale="candidate emits forward OOF and subgroup artifacts",
        ),
        robustness_assessment=RobustnessAssessment(
            seed_coverage=0.25,
            fold_coverage=1,
            subgroup_coverage=1,
            temporal_coverage=1,
            leakage_checks=1,
            rationale="one seed, at least three temporal folds, Known/New slices, explicit leakage checks",
        ),
        novelty_score=1,
        estimated_cost=CostEstimate(
            cpu_hours=estimate.cpu_cores * estimate.expected_minutes / 60,
            wall_hours=estimate.expected_minutes / 60,
        ),
        implementation_request={"command": subprocess.list2cmdline(argv), "network_policy": "disabled"},
        required_artifacts=candidate_required_outputs(),
        descriptors=CandidateDescriptors(
            validation_type="multi_horizon_forward_gap",
            model_family="agent_selected",
            representation=island.representation,
            shift_hypothesis=island.primary_niche.value,
            entity_hypothesis="agent_local",
            error_profile=island.error_profile,
            source_agent=island.agent_id,
            epistemic_niche=island.primary_niche.value,
            validation_world="forward_gap_known_new",
        ),
    )


def git(worktree: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(worktree), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def snapshot_hash(data_root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        (data_root / "train.parquet", data_root / "test.parquet", data_root / "manifest.json"),
        key=lambda item: item.name,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(path.stat().st_size).encode("ascii"))
        digest.update(b"\0")
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def verify_branch(island: Island) -> dict[str, str]:
    branch = git(island.worktree, "branch", "--show-current")
    head = git(island.worktree, "rev-parse", "HEAD")
    merge_base = git(island.worktree, "merge-base", "HEAD", BASE_REF)
    dirty = git(island.worktree, "status", "--porcelain")
    if branch != island.branch or merge_base != BASE_SHA or dirty:
        raise ValueError(
            f"invalid workspace for {island.agent_id}: branch={branch}, merge_base={merge_base}, dirty={bool(dirty)}"
        )
    return {"branch": branch, "head": head, "merge_base": merge_base}


def primary_metrics(path: Path) -> dict[str, float]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("metrics.json must contain an object")
    return {
        key: float(value)
        for key, value in raw.items()
        if isinstance(value, (int, float)) and math.isfinite(float(value))
    }


def candidate_record(island: Island, output: Path) -> CandidateArtifactRecord:
    candidate = mapping(output / "candidate.yaml")
    validation = candidate["validation"]
    if not isinstance(validation, dict):
        raise ValueError("candidate validation section must be an object")
    slices = candidate.get("slices")
    slices = slices if isinstance(slices, dict) else {}
    model_family = str(candidate.get("selected_family", candidate.get("model_family", "lightgbm")))
    return CandidateArtifactRecord(
        candidate_id=str(candidate["candidate_id"]),
        source_agent=island.agent_id,
        git_commit=str(candidate["git_commit"]),
        dataset_hash=str(candidate["dataset_hash"]),
        environment_hash=str(candidate["environment_hash"]),
        artifact_root=str(output),
        descriptor=CandidateDescriptors(
            validation_type="multi_horizon_forward_gap",
            model_family=model_family,
            representation=island.representation,
            data_scope="sampled_train_full_test",
            shift_hypothesis=island.primary_niche.value,
            entity_hypothesis="client_slice",
            error_profile=island.error_profile,
            source_agent=island.agent_id,
            epistemic_niche=island.primary_niche.value,
            validation_world="forward_gap_known_new",
        ),
        primary_score=float(validation["primary_score"]),
        score_std=float(validation["score_std"]),
        known_client_auc=_optional_float(slices.get("known_client_auc")),
        new_client_auc=_optional_float(slices.get("new_client_auc")),
        expected_forward_score=float(validation["primary_score"]),
        robustness=max(0.0, 1.0 - min(1.0, float(validation["score_std"]))),
        uncertainty=float(validation["score_std"]),
        leakage_risk=0,
        resource_cost=0,
        leakage_check_passed=bool(candidate["leakage_check"]["passed"]),
        reproducibility_passed=bool(candidate["reproducibility"]["passed"]),
    )


def _optional_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else None


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(args: argparse.Namespace) -> dict[str, Any]:
    run_root = args.run_root.resolve()
    if run_root.exists():
        raise FileExistsError(f"refusing to overwrite existing run root: {run_root}")
    campaign = islands(args.worktree_root.resolve(), args.sample, args.estimators)
    branch_state = {item.agent_id: verify_branch(item) for item in campaign}
    payloads = {item.agent_id: mapping(item.worktree / item.proposal_path) for item in campaign}
    commands: dict[str, list[str]] = {}
    outputs: dict[str, Path] = {}
    estimates: dict[str, ResourceEstimate] = {}
    proposals: list[ExperimentProposal] = []
    for island in campaign:
        argv, output = command(payloads[island.agent_id], island)
        estimate = resource_estimate(payloads[island.agent_id], island)
        commands[island.agent_id] = argv
        outputs[island.agent_id] = output
        estimates[island.agent_id] = estimate
        proposals.append(build_proposal(island, payloads[island.agent_id], argv, estimate))

    dataset_hash = snapshot_hash(args.data_root.resolve())
    scheduler = ResourceScheduler(
        total_memory_gb=args.total_memory_gb,
        total_cpu_cores=args.total_cpu_cores,
        max_concurrent_heavy_experiments=1,
        max_concurrent_light_experiments=3,
        memory_safety_margin=0.25,
        state_path=run_root / "scheduler.json",
    )
    loop = MultiIslandResearchLoop(
        run_root / "control",
        dataset_hash=dataset_hash,
        agents=[
            AgentNicheAssignment(
                agent_id=item.agent_id,
                primary_niche=item.primary_niche,
                secondary_niche=item.secondary_niche,
            )
            for item in campaign
        ],
        remaining_budget=RemainingBudget(cpu_minutes=600, wall_clock_minutes=180, llm_tokens=300_000),
        scheduler=scheduler,
    )
    for island in campaign:
        loop.create_belief_island(
            AgentBeliefState(
                agent_id=island.agent_id,
                epistemic_niche=island.primary_niche,
                hypotheses=[
                    LocalHypothesisBelief(
                        id=f"{island.agent_id}-H-001",
                        claim=private_claim(payloads[island.agent_id]),
                        prior_probability=0.5,
                        posterior_probability=0.5,
                    )
                ],
                validation_world_beliefs={"forward_gap": 0.75, "time_group": 0.25},
                private_working_notes=["No other agent result was supplied before proposal admission."],
            )
        )
    for proposal in proposals:
        loop.propose(proposal, requester=proposal.proposer_agent)

    report: dict[str, Any] = {
        "run_id": RUN_ID,
        "base_ref": BASE_REF,
        "base_sha": BASE_SHA,
        "dataset_hash": dataset_hash,
        "sample_rows": args.sample,
        "branches": branch_state,
        "execution_policy": "sequential_heavy",
        "experiments": {},
    }
    write_json(run_root / "report.json", report)
    validator = CandidateArtifactValidator()
    for index, (island, proposal) in enumerate(zip(campaign, proposals, strict=True)):
        started = time.monotonic()
        loop.start(proposal.id)
        next_estimate = estimates[campaign[index + 1].agent_id] if index + 1 < len(campaign) else None
        parallel_probe = scheduler.can_schedule(next_estimate) if next_estimate is not None else None
        log_root = run_root / "logs" / island.agent_id
        log_root.mkdir(parents=True, exist_ok=True)
        process = subprocess.run(
            commands[island.agent_id],
            cwd=island.worktree,
            capture_output=True,
            text=True,
            timeout=args.timeout_minutes * 60,
            check=False,
        )
        (log_root / "stdout.log").write_text(process.stdout, encoding="utf-8")
        (log_root / "stderr.log").write_text(process.stderr, encoding="utf-8")
        artifact_validation = validator.validate(outputs[island.agent_id])
        if process.returncode == 0 and artifact_validation.valid:
            terminal_status = TerminalStatus.COMPLETED
            transport_status = "completed"
            record = candidate_record(island, outputs[island.agent_id])
            hash_matches = record.dataset_hash == dataset_hash
            if not hash_matches:
                terminal_status = TerminalStatus.INVALID_ARTIFACT
                transport_status = "failed"
                record = None
        else:
            memory_failure = process.returncode in {137, -9} or "memoryerror" in process.stderr.lower()
            terminal_status = (
                TerminalStatus.FAILED_RESOURCE
                if memory_failure
                else artifact_validation.terminal_status
                if process.returncode == 0
                else TerminalStatus.FAILED_EXECUTION
            )
            transport_status = "failed"
            record = None
            hash_matches = False
        result = ExperimentResult(
            experiment_id=proposal.id,
            run_id=RUN_ID,
            attempt=1,
            status=transport_status,
            terminal_status=terminal_status,
            exit_code=process.returncode,
            commit_sha=branch_state[island.agent_id]["head"],
            environment_hash=(record.environment_hash if record is not None else "unavailable"),
            dataset_fingerprint=dataset_hash,
            metrics=(primary_metrics(outputs[island.agent_id] / "metrics.json") if process.returncode == 0 else {}),
            artifact_refs=(
                [str(outputs[island.agent_id] / item) for item in candidate_required_outputs()]
                if outputs[island.agent_id].exists()
                else []
            ),
            runtime={"wall_seconds": time.monotonic() - started},
            failure_excerpt=(process.stderr[-2000:] or None) if transport_status == "failed" else None,
        )
        loop.complete(result, candidate=record)
        report["experiments"][island.agent_id] = {
            "proposal_id": proposal.id,
            "terminal_status": terminal_status.value,
            "exit_code": process.returncode,
            "wall_seconds": result.runtime["wall_seconds"],
            "artifact_valid": artifact_validation.valid,
            "artifact_missing": artifact_validation.missing,
            "artifact_invalid": artifact_validation.invalid,
            "dataset_hash_matches": hash_matches,
            "output": str(outputs[island.agent_id]),
            "resource_estimate": estimates[island.agent_id].model_dump(mode="json"),
            "parallel_probe_for_next": (
                {
                    "accepted": parallel_probe.accepted,
                    "reason": parallel_probe.reason,
                    "heavy": parallel_probe.heavy,
                }
                if parallel_probe is not None
                else None
            ),
        }
        write_json(run_root / "report.json", report)

    similarities = {
        f"{left.proposer_agent}:{right.proposer_agent}": semantic_similarity(
            left.semantic_signature,
            right.semantic_signature,  # type: ignore[arg-type]
        )
        for index, left in enumerate(proposals)
        for right in proposals[index + 1 :]
    }
    clusters = loop.duplicates.clusters(proposals)
    mean_similarity = fmean(similarities.values())
    dominant_fraction = max((len(item) for item in clusters), default=0) / len(proposals)
    operations = [item.semantic_signature.operation[0] for item in proposals if item.semantic_signature]
    collapse = loop.assess_collapse(
        CollapseMetrics(
            dominant_cluster_fraction=dominant_fraction,
            experiment_family_effective_count=effective_count(operations),
            qd_niche_occupancy=len(loop.archive.occupancy),
            hypothesis_family_budget_fraction=1 / len(proposals),
            mean_agent_proposal_similarity=mean_similarity,
            cycle=1,
        )
    )
    agent_views = {item.agent_id: loop.archive.agent_view(item.agent_id) for item in campaign}
    routed_counts = {
        item.agent_id: len(loop.routed_evidence(recipient_agent=item.agent_id, current_cycle=1)) for item in campaign
    }
    report.update(
        {
            "semantic": {
                "pairwise_similarity": similarities,
                "clusters": clusters,
                "duplicate_rate": 1 - len(clusters) / len(proposals),
            },
            "collapse": {
                "collapsed": collapse.collapsed,
                "active_conditions": collapse.active_conditions,
                "actions": collapse.actions,
            },
            "archive": {
                "candidate_count": len(loop.archive.candidates),
                "occupancy": loop.archive.occupancy,
                "agent_views": agent_views,
            },
            "evidence": {
                "global_count": len(loop.evidence.all()),
                "cycle_1_routed_counts": routed_counts,
                "cross_agent_broadcast_count": 0,
            },
            "global_control": loop.control.load().model_dump(mode="json"),
        }
    )
    write_json(run_root / "report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--worktree-root",
        type=Path,
        default=Path(".state/worktrees/ieee-cis-v02"),
    )
    parser.add_argument("--data-root", type=Path, default=Path(".data/ieee-cis/parquet"))
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path(".runs/ieee-cis-v02-multi-island-20260826"),
    )
    parser.add_argument("--sample", type=int, default=40_000)
    parser.add_argument("--estimators", type=int, default=120)
    parser.add_argument("--timeout-minutes", type=int, default=60)
    parser.add_argument("--total-memory-gb", type=float, default=62)
    parser.add_argument("--total-cpu-cores", type=int, default=24)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2, sort_keys=True))
