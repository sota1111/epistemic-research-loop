#!/usr/bin/env python3
"""Run the branch-isolated IEEE-CIS C-lite v0.3 verification campaign.

All agents start generic. Their proposals are admitted only after every branch is
finished, and every candidate is executed under the one-heavy-job scheduler.
Structural hypotheses are registered only when an agent proposed one itself.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any, cast

import yaml

from epistemic_loop.controller.candidate_artifacts import (
    candidate_required_outputs,
)
from epistemic_loop.controller.diversity_control import effective_count, semantic_similarity
from epistemic_loop.controller.multi_island_loop import MultiIslandResearchLoop
from epistemic_loop.controller.resource_scheduler import ResourceScheduler
from epistemic_loop.domain.enums import (
    Direction,
    ExperimentKind,
    ExperimentType,
    StructuralDimension,
    StructureLifecycleState,
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
    StructuralAlternative,
    StructuralHypothesis,
)
from epistemic_loop.plugins.ieee_cis_artifacts import (
    IEEEArtifactPreflight,
    canonical_ieee_cis_dataset_hash,
)

BASE_REF = "initial/ieee-cis-state"
BASE_SHA = "ac3b46975e5da64570fb79d6e1141bc5c7525d0f"
RUN_ID_BASE = "ieee-cis-v03-multi-island-20260826"
PYTHON = "/workspaces/kaggle-ieee-cis-fraud-detection/.venv/bin/python"


@dataclass(frozen=True)
class Island:
    agent_id: str
    branch: str
    worktree: Path
    proposal_path: Path


def islands(worktree_root: Path, *, cycle: int) -> tuple[Island, ...]:
    return tuple(
        Island(
            agent_id=f"island-{index:02d}",
            branch=f"agents/v03-island-{index:02d}",
            worktree=worktree_root / f"island-{index:02d}",
            proposal_path=Path(
                f"proposals/island-{index:02d}.yaml"
                if cycle == 1
                else f"proposals/island-{index:02d}-cycle-{cycle:02d}.yaml"
            ),
        )
        for index in range(1, 4)
    )


def mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return value


def string_list(value: object, *, field: str) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list) and value and all(isinstance(item, str) and item.strip() for item in value):
        return [item.strip() for item in value]
    raise ValueError(f"{field} must be a non-empty string or string list")


def semantic_signature(payload: dict[str, Any]) -> SemanticExperimentSignature:
    raw = payload.get("semantic_signature")
    if not isinstance(raw, dict):
        raise ValueError("proposal requires semantic_signature")
    target_hypotheses = raw.get("target_hypotheses", [private_claim(payload)])
    data_slice = raw.get("data_slice", raw.get("validation", raw.get("data_scope")))
    decision_affected = raw.get("decision_affected", payload.get("decision_binding"))
    if isinstance(decision_affected, dict):
        decision_affected = [
            str(decision_affected.get("decision", decision_affected.get("decision_id", "candidate_policy")))
        ]
    return SemanticExperimentSignature(
        target_hypotheses=string_list(target_hypotheses, field="target_hypotheses"),
        data_slice=string_list(data_slice, field="data_slice"),
        operation=string_list(raw.get("operation"), field="operation"),
        observable=string_list(raw.get("observable"), field="observable"),
        decision_affected=string_list(decision_affected, field="decision_affected"),
        candidate_producing=True,
    )


def private_claim(payload: dict[str, Any]) -> str:
    raw = payload.get("private_hypothesis")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, dict):
        for key in ("claim", "statement"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    raise ValueError("proposal requires private_hypothesis")


def numeric_max(value: object, fallback: float, *, upper_bound: float | None = None) -> float:
    values = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", str(value))]
    if upper_bound is not None:
        values = [item for item in values if item <= upper_bound]
    return max(values, default=fallback)


def resource_estimate(payload: dict[str, Any]) -> ResourceEstimate:
    raw = payload.get("resource_estimate")
    if not isinstance(raw, dict):
        raise ValueError("proposal requires resource_estimate")
    memory = numeric_max(raw.get("memory_gb", raw.get("peak_ram_gb", 12)), 12, upper_bound=256)
    cpu = int(numeric_max(raw.get("cpu_cores", raw.get("threads", 2)), 2, upper_bound=64))
    minutes = numeric_max(raw.get("expected_minutes", raw.get("wall_time_minutes", 60)), 60, upper_bound=600)
    columns = int(numeric_max(raw.get("parquet_scan_columns", raw.get("feature_count", 100)), 100))
    return ResourceEstimate(
        cpu_cores=cpu,
        memory_gb=memory,
        expected_minutes=minutes,
        parquet_scan_columns=columns,
        full_table_materialization=bool(raw.get("full_table_materialization", False)),
        heavy=True,
    )


def proposal_command(
    payload: dict[str, Any],
    island: Island,
    *,
    sample: int,
    estimators: int,
    threads: int,
    output_name: str,
) -> tuple[list[str], Path]:
    raw = payload.get("command")
    if isinstance(raw, dict):
        raw = raw.get("argv")
    if not isinstance(raw, list) or not raw or not all(isinstance(item, str) for item in raw):
        raise ValueError("proposal command must be a non-empty argv list")
    original = list(raw)
    script_index = next((index for index, item in enumerate(original) if item.endswith(".py")), None)
    if script_index is None:
        raise ValueError("candidate command must identify a Python script")
    argv = [PYTHON, *original[script_index:]]
    replacements = {
        "--sample": str(sample),
        "--n-estimators": str(estimators),
        "--estimators": str(estimators),
        "--threads": str(threads),
        "--n-jobs": str(threads),
    }
    for option, replacement in replacements.items():
        if option in argv:
            argv[argv.index(option) + 1] = replacement
    if "--output" not in argv:
        raise ValueError("candidate command requires --output")
    output_index = argv.index("--output") + 1
    if not output_name or Path(output_name).name != output_name:
        raise ValueError("output name must be a safe path component")
    output = island.worktree / "results" / output_name
    argv[output_index] = str(output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite candidate output: {output}")
    return argv, output


def structural_hypothesis(
    payload: dict[str, Any],
    *,
    island: Island,
    run_id: str,
) -> tuple[StructuralHypothesis | None, list[StructuralAlternative]]:
    raw = payload.get("structural_hypothesis")
    if raw is None:
        return None, []
    if not isinstance(raw, dict):
        raise ValueError("structural_hypothesis must be an object")
    dimensions = [StructuralDimension(str(item).strip().lower()) for item in raw.get("affected_dimensions", [])]
    alternatives_raw = raw.get("alternatives", raw.get("competing_hypotheses", []))
    if not isinstance(alternatives_raw, list):
        raise ValueError("structural alternatives must be a list")
    alternatives = []
    for index, item in enumerate(alternatives_raw, start=1):
        if not isinstance(item, dict):
            raise ValueError("each structural alternative must be an object")
        alternatives.append(
            StructuralAlternative(
                id=str(item.get("id", f"{island.agent_id}-ALT-{index:02d}")),
                claim=str(item.get("claim", item.get("statement", ""))),
                observable_predictions=string_list(
                    item.get("observable_predictions", item.get("predictions")),
                    field="alternative.observable_predictions",
                ),
                falsification_conditions=string_list(
                    item.get("falsification_conditions", item.get("falsification_condition")),
                    field="alternative.falsification_conditions",
                ),
                null_model=bool(item.get("null_model", False)),
            )
        )
    hypothesis_id = str(raw.get("id", f"{island.agent_id}-STRUCT-001"))
    hypothesis = StructuralHypothesis(
        id=hypothesis_id,
        run_id=run_id,
        owner_agent=island.agent_id,
        claim=str(raw.get("claim", "")),
        structure_type=str(raw.get("structure_type", "agent_discovered")),
        observation_refs=string_list(
            raw.get("observation_refs", [f"proposal:{island.agent_id}"]), field="observation_refs"
        ),
        affected_dimensions=dimensions,
        observable_predictions=string_list(raw.get("observable_predictions"), field="observable_predictions"),
        falsification_conditions=string_list(raw.get("falsification_conditions"), field="falsification_conditions"),
        discrimination_plan=string_list(raw.get("discrimination_plan"), field="discrimination_plan"),
        decisions_affected=string_list(raw.get("decisions_affected"), field="decisions_affected"),
        lifecycle_state=StructureLifecycleState.PROVISIONAL_STRUCTURE,
    )
    return hypothesis, alternatives


def build_proposal(
    island: Island,
    payload: dict[str, Any],
    argv: list[str],
    estimate: ResourceEstimate,
    signature: SemanticExperimentSignature,
    structure: StructuralHypothesis | None,
    *,
    run_id: str,
) -> ExperimentProposal:
    seed = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 42
    return ExperimentProposal(
        id=str(payload.get("proposal_id", f"{island.agent_id}-candidate")),
        run_id=run_id,
        proposer_agent=island.agent_id,
        experiment_type=ExperimentType.EPISTEMIC,
        experiment_kind=ExperimentKind.CANDIDATE_PRODUCING,
        candidate_producing=True,
        semantic_signature=signature,
        resource_estimate=estimate,
        hypothesis_ids=[f"{island.agent_id}-H-001"],
        structural_hypothesis_id=structure.id if structure else None,
        research_question=private_claim(payload),
        protocol="agent-authored candidate with multi-horizon forward-gap fraud-label validation",
        controls=["no hidden score", "no test label", "fold-local learned transforms"],
        split_strategy="multi_horizon_forward_gap",
        seeds=[seed],
        metrics=["primary_score", "known_client_auc", "new_client_auc"],
        predicted_outcomes=[
            PredictedOutcome(
                description="forward and subgroup metrics determine candidate eligibility",
                metric_name="primary_score",
                expected_direction=Direction.PATTERN,
                condition="at least three forward fraud-label horizons with a non-zero time gap",
            )
        ],
        decision_rule=str(payload.get("decision_binding", "promote only after artifact and leakage gates")),
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
            rationale="one seed, temporal folds, subgroup slices and explicit leakage checks",
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
            representation=signature.operation[0],
            shift_hypothesis=signature.target_hypotheses[0],
            entity_hypothesis="agent_local",
            error_profile=signature.observable[0],
            source_agent=island.agent_id,
            validation_world="forward_gap",
        ),
    )


def git(worktree: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(worktree), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


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


def optional_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else None


def candidate_record(
    island: Island,
    output: Path,
    signature: SemanticExperimentSignature,
    structure: StructuralHypothesis | None,
) -> CandidateArtifactRecord:
    candidate = mapping(output / "candidate.yaml")
    validation = candidate.get("validation")
    if not isinstance(validation, dict):
        raise ValueError("candidate validation section must be an object")
    slices = candidate.get("slices")
    slices = slices if isinstance(slices, dict) else {}
    return CandidateArtifactRecord(
        candidate_id=str(candidate["candidate_id"]),
        source_agent=island.agent_id,
        git_commit=str(candidate["git_commit"]),
        dataset_hash=str(candidate["dataset_hash"]),
        environment_hash=str(candidate["environment_hash"]),
        artifact_root=str(output),
        descriptor=CandidateDescriptors(
            validation_type="multi_horizon_forward_gap",
            model_family=str(candidate.get("selected_family", candidate.get("model_family", "unknown"))),
            representation=signature.operation[0],
            shift_hypothesis=signature.target_hypotheses[0],
            entity_hypothesis="agent_local",
            error_profile=signature.observable[0],
            source_agent=island.agent_id,
            validation_world="forward_gap",
        ),
        primary_score=float(validation["primary_score"]),
        score_std=float(validation["score_std"]),
        known_client_auc=optional_float(slices.get("known_client_auc")),
        new_client_auc=optional_float(slices.get("new_client_auc")),
        expected_forward_score=float(validation["primary_score"]),
        robustness=max(0.0, 1.0 - min(1.0, float(validation["score_std"]))),
        uncertainty=float(validation["score_std"]),
        leakage_risk=0,
        leakage_check_passed=bool(candidate["leakage_check"]["passed"]),
        reproducibility_passed=bool(candidate["reproducibility"]["passed"]),
        structural_hypothesis_ids=[structure.id] if structure else [],
    )


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(args: argparse.Namespace) -> dict[str, Any]:
    run_root = args.run_root.resolve()
    if run_root.exists():
        raise FileExistsError(f"refusing to overwrite existing run root: {run_root}")
    run_id = f"{RUN_ID_BASE}-cycle-{args.cycle:02d}"
    campaign = islands(args.worktree_root.resolve(), cycle=args.cycle)
    if args.agents:
        requested = set(args.agents.split(","))
        campaign = tuple(item for item in campaign if item.agent_id in requested)
        unknown = requested - {item.agent_id for item in campaign}
        if unknown:
            raise ValueError(f"unknown agent ids: {sorted(unknown)}")
    if not campaign:
        raise ValueError("at least one agent is required")
    branch_state = {item.agent_id: verify_branch(item) for item in campaign}
    payloads = {item.agent_id: mapping(item.worktree / item.proposal_path) for item in campaign}
    signatures = {item.agent_id: semantic_signature(payloads[item.agent_id]) for item in campaign}
    structures: dict[str, StructuralHypothesis | None] = {}
    alternatives: dict[str, list[StructuralAlternative]] = {}
    commands: dict[str, list[str]] = {}
    outputs: dict[str, Path] = {}
    estimates: dict[str, ResourceEstimate] = {}
    proposals: list[ExperimentProposal] = []
    for island in campaign:
        payload = payloads[island.agent_id]
        command, output = proposal_command(
            payload,
            island,
            sample=args.sample,
            estimators=args.estimators,
            threads=args.threads,
            output_name=args.output_name,
        )
        estimate = resource_estimate(payload)
        structure, rivals = structural_hypothesis(payload, island=island, run_id=run_id)
        structures[island.agent_id] = structure
        alternatives[island.agent_id] = rivals
        commands[island.agent_id] = command
        outputs[island.agent_id] = output
        estimates[island.agent_id] = estimate
        proposals.append(
            build_proposal(
                island,
                payload,
                command,
                estimate,
                signatures[island.agent_id],
                structure,
                run_id=run_id,
            )
        )

    dataset_hash = canonical_ieee_cis_dataset_hash(args.data_root.resolve())
    dataset_manifest = mapping(args.data_root.resolve() / "manifest.json")
    expected_test_rows = int(dataset_manifest["splits"]["test"]["rows"])
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
        agents=[AgentNicheAssignment(agent_id=item.agent_id) for item in campaign],
        remaining_budget=RemainingBudget(cpu_minutes=600, wall_clock_minutes=240, llm_tokens=300_000),
        scheduler=scheduler,
    )
    structure_forks: dict[str, str] = {}
    for island in campaign:
        loop.create_belief_island(
            AgentBeliefState(
                agent_id=island.agent_id,
                hypotheses=[
                    LocalHypothesisBelief(
                        id=f"{island.agent_id}-H-001",
                        claim=private_claim(payloads[island.agent_id]),
                        prior_probability=0.5,
                        posterior_probability=0.5,
                    )
                ],
                validation_world_beliefs={"forward_gap": 0.5, "other": 0.5},
                private_working_notes=["No fixed niche or other-agent result was supplied."],
            )
        )
        structure = structures[island.agent_id]
        if structure is not None:
            loop.register_structural_hypothesis(structure, requester=island.agent_id)
            rivals = alternatives[island.agent_id]
            if rivals:
                matured = StructuralHypothesis.model_validate(
                    {
                        **structure.model_dump(),
                        "alternatives": rivals,
                        "lifecycle_state": StructureLifecycleState.ALTERNATIVES_REGISTERED,
                    }
                )
                loop.advance_structural_hypothesis(matured, requester=island.agent_id)
                fork = loop.create_structure_maturation_fork(
                    structure.id,
                    checkpoint_ref=f"git:{branch_state[island.agent_id]['head']}",
                    requester=island.agent_id,
                )
                structure_forks[island.agent_id] = fork.fork_id
    for proposal in proposals:
        loop.propose(proposal, requester=proposal.proposer_agent)

    report: dict[str, Any] = {
        "run_id": run_id,
        "cycle": args.cycle,
        "base_ref": BASE_REF,
        "base_sha": BASE_SHA,
        "dataset_hash": dataset_hash,
        "sample_rows": args.sample,
        "branches": branch_state,
        "agent_initial_state": "generic_research",
        "fixed_niches": False,
        "execution_policy": "sequential_heavy",
        "structure_forks": structure_forks,
        "experiments": {},
    }
    write_json(run_root / "report.json", report)
    preflight = IEEEArtifactPreflight(expected_test_rows=expected_test_rows)
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
        artifact_validation = preflight.validate(outputs[island.agent_id], expected_dataset_hash=dataset_hash)
        test_prediction_rows = artifact_validation.test_prediction_row_count
        full_test_rows_match = test_prediction_rows == expected_test_rows
        record = None
        hash_matches = artifact_validation.dataset_hash_matches
        if process.returncode == 0 and artifact_validation.valid:
            record = candidate_record(
                island,
                outputs[island.agent_id],
                signatures[island.agent_id],
                structures[island.agent_id],
            )
        completed = process.returncode == 0 and artifact_validation.valid
        if completed:
            terminal_status = TerminalStatus.COMPLETED
        elif process.returncode in {137, -9} or "memoryerror" in process.stderr.lower():
            terminal_status = TerminalStatus.FAILED_RESOURCE
            record = None
        elif process.returncode == 0:
            terminal_status = TerminalStatus.INVALID_ARTIFACT
            record = None
        else:
            terminal_status = TerminalStatus.FAILED_EXECUTION
            record = None
        result = ExperimentResult(
            experiment_id=proposal.id,
            run_id=run_id,
            attempt=1,
            status="completed" if completed else "failed",
            terminal_status=terminal_status,
            exit_code=process.returncode,
            commit_sha=branch_state[island.agent_id]["head"],
            environment_hash=record.environment_hash if record else "unavailable",
            dataset_fingerprint=dataset_hash,
            metrics=(
                primary_metrics(outputs[island.agent_id] / "metrics.json")
                if process.returncode == 0 and (outputs[island.agent_id] / "metrics.json").is_file()
                else {}
            ),
            artifact_refs=(
                [str(outputs[island.agent_id] / item) for item in candidate_required_outputs()]
                if outputs[island.agent_id].exists()
                else []
            ),
            runtime={"wall_seconds": time.monotonic() - started},
            failure_excerpt=(process.stderr[-2000:] or None) if not completed else None,
        )
        loop.complete(result, candidate=record)
        report["experiments"][island.agent_id] = {
            "proposal_id": proposal.id,
            "semantic_signature": signatures[island.agent_id].model_dump(mode="json"),
            "structural_hypothesis_id": (
                structure.id if (structure := structures[island.agent_id]) is not None else None
            ),
            "terminal_status": terminal_status.value,
            "exit_code": process.returncode,
            "wall_seconds": result.runtime["wall_seconds"],
            "artifact_valid": artifact_validation.valid,
            "artifact_errors": artifact_validation.errors,
            "dataset_hash_matches": hash_matches,
            "test_prediction_rows": test_prediction_rows,
            "expected_test_rows": expected_test_rows,
            "full_test_rows_match": full_test_rows_match,
            "oof_honesty_passed": artifact_validation.oof_honesty_passed,
            "output": str(outputs[island.agent_id]),
            "parallel_probe_for_next": (
                {"accepted": parallel_probe.accepted, "reason": parallel_probe.reason}
                if parallel_probe is not None
                else None
            ),
        }
        write_json(run_root / "report.json", report)

    similarities = {
        f"{left.proposer_agent}:{right.proposer_agent}": semantic_similarity(
            cast(SemanticExperimentSignature, left.semantic_signature),
            cast(SemanticExperimentSignature, right.semantic_signature),
        )
        for index, left in enumerate(proposals)
        for right in proposals[index + 1 :]
    }
    clusters = loop.duplicates.clusters(proposals)
    mean_similarity = fmean(similarities.values()) if similarities else 0.0
    operations = [item.semantic_signature.operation[0] for item in proposals if item.semantic_signature]
    collapse = loop.assess_collapse(
        CollapseMetrics(
            dominant_cluster_fraction=max(len(item) for item in clusters) / len(proposals),
            experiment_family_effective_count=effective_count(operations),
            qd_niche_occupancy=len(loop.archive.occupancy),
            hypothesis_family_budget_fraction=1 / len(proposals),
            mean_agent_proposal_similarity=mean_similarity,
            cycle=args.cycle,
        )
    )
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
                "agent_views": {item.agent_id: loop.archive.agent_view(item.agent_id) for item in campaign},
            },
            "evidence": {
                "global_count": len(loop.evidence.all()),
                "routed_counts": {
                    item.agent_id: len(loop.routed_evidence(recipient_agent=item.agent_id, current_cycle=args.cycle))
                    for item in campaign
                },
            },
            "structure": {
                "active_forks": list(loop.structures.active_fork_ids()),
                "validation_debts": [item.model_dump(mode="json") for item in loop.structures.all_debts()],
                "promotion_assessments": [item.model_dump(mode="json") for item in loop.structures.all_assessments()],
            },
            "global_control": loop.control.load().model_dump(mode="json"),
        }
    )
    write_json(run_root / "report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree-root", type=Path, default=Path(".state/worktrees/ieee-cis-v03"))
    parser.add_argument("--data-root", type=Path, default=Path(".data/ieee-cis/parquet"))
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path(".runs/ieee-cis-v03-multi-island-20260826"),
    )
    parser.add_argument("--sample", type=int, default=40_000)
    parser.add_argument("--cycle", type=int, choices=(1, 2, 3, 4), default=1)
    parser.add_argument("--estimators", type=int, default=80)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--output-name", default="v03-validation")
    parser.add_argument(
        "--agents",
        default="",
        help="comma-separated agent ids for an isolated retry; empty runs all agents",
    )
    parser.add_argument("--timeout-minutes", type=int, default=60)
    parser.add_argument("--total-memory-gb", type=float, default=62)
    parser.add_argument("--total-cpu-cores", type=int, default=24)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2, sort_keys=True))
