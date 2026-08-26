from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from epistemic_loop.controller.budget_manager import BudgetManager
from epistemic_loop.controller.research_state import derive_research_state
from epistemic_loop.controller.run_state import load_run_state
from epistemic_loop.domain.enums import ExperimentStatus, HypothesisStatus
from epistemic_loop.domain.events import EventEnvelope, EventType
from epistemic_loop.domain.models import StructurePromotionAssessment, StructureValidationDebt


def build_run_report(
    run_id: str,
    events: list[EventEnvelope],
    *,
    qd_maximum_size: int = 100,
    preferred_targets: Mapping[str, float] | None = None,
    preferred_weights: Mapping[str, float] | None = None,
    structural_assessments: Sequence[StructurePromotionAssessment] = (),
    structure_validation_debts: Sequence[StructureValidationDebt] = (),
) -> str:
    counts = Counter(event.event_type.value for event in events)
    run = next((event.payload for event in events if event.event_type == EventType.RUN_CREATED), {})
    hypotheses = [event.payload for event in events if event.event_type == EventType.HYPOTHESIS_PROPOSED]
    experiments = [event.payload for event in events if event.event_type == EventType.EXPERIMENT_PROPOSED]
    violations = [event.payload for event in events if event.event_type == EventType.VIOLATION_DETECTED]
    validation_worlds = {
        event.payload["id"]: dict(event.payload)
        for event in events
        if event.event_type == EventType.VALIDATION_WORLD_REGISTERED
    }
    for event in events:
        if event.event_type == EventType.VALIDATION_POSTERIOR_UPDATED:
            for identifier, probability in event.payload.get("posterior", {}).items():
                if identifier in validation_worlds:
                    validation_worlds[identifier]["posterior_probability"] = probability
    qd_candidates = [event.payload for event in events if event.event_type == EventType.QD_CANDIDATE_EVALUATED]
    oof_artifacts = [event.payload for event in events if event.event_type == EventType.OOF_ARTIFACT_RECORDED]
    latest_oof = next(
        (event.payload for event in reversed(events) if event.event_type == EventType.OOF_ANALYSIS_RECORDED),
        None,
    )
    state = load_run_state(events)
    latest_phase = state.phase.value
    research_state = derive_research_state(
        state,
        maximum_archive_size=qd_maximum_size,
        preferred_targets=preferred_targets,
        preferred_weights=preferred_weights,
        structural_assessments=structural_assessments,
    ).model_dump(mode="json")
    best_candidate = max(
        state.qd_candidates.values(),
        key=lambda item: (item.expected_hidden_score, item.robustness, item.id),
        default=None,
    )
    agent_costs: dict[str, dict[str, float | int]] = {}
    for proposal in state.proposals.values():
        values = agent_costs.setdefault(
            proposal.proposer_agent,
            {"experiments": 0, "cpu_hours": 0.0, "gpu_hours": 0.0, "wall_hours": 0.0, "llm_tokens": 0},
        )
        values["experiments"] += 1
        values["cpu_hours"] += proposal.estimated_cost.cpu_hours
        values["gpu_hours"] += proposal.estimated_cost.gpu_hours
        values["wall_hours"] += proposal.estimated_cost.wall_hours
        values["llm_tokens"] += proposal.estimated_cost.llm_tokens
    agent_actual_costs: dict[str, dict[str, float | int]] = {}
    for record in state.agent_resource_records:
        values = agent_actual_costs.setdefault(
            record.agent,
            {"calls": 0, "llm_tokens": 0, "monetary_cost": 0.0},
        )
        values["calls"] += 1
        values["llm_tokens"] += record.total_tokens
        values["monetary_cost"] += record.monetary_cost
    observability = {
        "remaining_budget": BudgetManager(state.run.budgets, state.usage).remaining(),
        "experiment_queue": [
            identifier
            for identifier, status in state.experiment_statuses.items()
            if status in {ExperimentStatus.PROPOSED, ExperimentStatus.SELECTED, ExperimentStatus.RUNNING}
        ],
        "active_hypotheses": sum(
            item.status not in {HypothesisStatus.FALSIFIED, HypothesisStatus.RETIRED}
            for item in state.hypotheses.values()
        ),
        "hypothesis_entropy_bits": research_state["hypothesis_entropy_bits"],
        "validation_world_posterior": {
            identifier: world.posterior_probability for identifier, world in state.validation_worlds.items()
        },
        "qd_occupancy": research_state["qd_occupancy"],
        "best_candidate": best_candidate.model_dump(mode="json") if best_candidate else None,
        "robustness": best_candidate.robustness if best_candidate else None,
        "oof_effective_rank": research_state["oof_effective_rank"],
        "failure_count": sum(status == ExperimentStatus.FAILED for status in state.experiment_statuses.values()),
        "infrastructure_retry_count": len(state.experiment_retries),
        "public_query_count": counts[EventType.LEADERBOARD_FEEDBACK_RECORDED.value],
        "agent_estimated_costs": agent_costs,
        "agent_actual_costs": agent_actual_costs,
        "cycle_utility_breakdown": [
            {"sequence": event.sequence, "utilities": event.payload.get("utility_breakdown", {})}
            for event in events
            if event.event_type == EventType.EXPERIMENT_SELECTED
        ],
        "observed_runtime": state.observed_runtime(),
        "structure_validation_debts": [item.model_dump(mode="json") for item in structure_validation_debts],
        "open_structure_validation_debt_count": sum(
            item.remaining_requirements != () for item in structure_validation_debts
        ),
    }
    return (
        "\n".join(
            [
                f"# Research Run {run_id}",
                "",
                "## Run conditions",
                "",
                f"- Competition: {run.get('competition_id', 'unknown')}",
                f"- Mode: {run.get('mode', 'unknown')}",
                f"- Phase: {latest_phase}",
                f"- Base commit: {run.get('base_commit_sha', 'unknown')}",
                f"- Dataset fingerprint: {run.get('dataset_fingerprint', 'unknown')}",
                "",
                "## Audit summary",
                "",
                f"- Events: {len(events)}",
                f"- Hypotheses proposed: {len(hypotheses)}",
                f"- Experiments proposed: {len(experiments)}",
                f"- Holdout/rule violations: {len(violations)}",
                f"- Validation worlds: {len(validation_worlds)}",
                f"- QD candidates evaluated: {len(qd_candidates)}",
                f"- OOF artifacts: {len(oof_artifacts)}",
                f"- OOF effective rank: "
                f"{latest_oof.get('covariance_effective_rank') if latest_oof else 'not measured'}",
                "",
                "## Validation-world posterior",
                "",
                "```json",
                json.dumps(
                    {
                        identifier: world["posterior_probability"]
                        for identifier, world in sorted(validation_worlds.items())
                    },
                    indent=2,
                ),
                "```",
                "",
                "## Derived research state",
                "",
                "```json",
                json.dumps(research_state, indent=2, default=str),
                "```",
                "",
                "## Operational observability",
                "",
                "```json",
                json.dumps(observability, indent=2, default=str),
                "```",
                "",
                "## Event counts",
                "",
                "```json",
                json.dumps(dict(sorted(counts.items())), indent=2),
                "```",
            ]
        )
        + "\n"
    )


def write_run_report(
    run_id: str,
    events: list[EventEnvelope],
    destination: str | Path,
    *,
    qd_maximum_size: int = 100,
    preferred_targets: Mapping[str, float] | None = None,
    preferred_weights: Mapping[str, float] | None = None,
    structural_assessments: Sequence[StructurePromotionAssessment] = (),
    structure_validation_debts: Sequence[StructureValidationDebt] = (),
) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        build_run_report(
            run_id,
            events,
            qd_maximum_size=qd_maximum_size,
            preferred_targets=preferred_targets,
            preferred_weights=preferred_weights,
            structural_assessments=structural_assessments,
            structure_validation_debts=structure_validation_debts,
        ),
        encoding="utf-8",
    )
    return path
