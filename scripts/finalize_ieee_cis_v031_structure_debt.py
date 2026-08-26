#!/usr/bin/env python3
"""Close the Island-01 payment-process debt from the completed 20-null test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from epistemic_loop.controller.structure_maturation import StructureMaturationController
from epistemic_loop.controller.structure_validation import (
    MatchedNullSequentialFutilityRule,
    StructureTerminalEvidence,
    decide_structure_terminal_state,
)
from epistemic_loop.domain.enums import (
    StructureLifecycleState,
    ValidationRequirementOutcome,
)
from epistemic_loop.domain.models import StructuralHypothesis, StructureTestPreregistration

HYPOTHESIS_ID = "ISLAND-01-H-AMOUNT-RAIL-001"
OWNER = "island-01"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(arguments: argparse.Namespace) -> dict[str, object]:
    output = arguments.output.resolve()
    report_path = output / "terminal_report.json"
    if report_path.exists():
        raise FileExistsError(report_path)
    ablation_path = arguments.null_artifact.resolve() / "ablation_metrics.json"
    ablation = _json(ablation_path)
    real_auc = float(ablation["real_mean_auc"])
    null_95 = float(ablation["null_95pct_mean_auc"])
    null_scores = tuple(float(item) for item in ablation["null_mean_auc_by_repetition"])  # type: ignore[union-attr]
    if len(null_scores) < 20:
        raise ValueError("terminal matched-null decision requires at least 20 valid repetitions")
    null_rejected = real_auc > null_95
    futility = MatchedNullSequentialFutilityRule().assess(
        real_gain=real_auc,
        matched_null_gains=null_scores,
    )
    decision = decide_structure_terminal_state(
        StructureTerminalEvidence(
            null_rejected=null_rejected,
            independent_implication_reproduced=False,
            multi_context_multi_seed_reproduced=False,
            decision_improved=False,
            predictive_gain_reproduced=True,
            sufficient_power=True,
        )
    )

    source = StructuralHypothesis.model_validate(_json(arguments.hypothesis.resolve()))
    controller = StructureMaturationController(output / "control")
    provisional = source.model_copy(
        update={
            "alternatives": [],
            "preregistered_tests": [],
            "evidence_refs": [],
            "lifecycle_state": StructureLifecycleState.PROVISIONAL_STRUCTURE,
            "classification": None,
        }
    )
    controller.register(provisional, requester=OWNER)
    alternatives_registered = provisional.model_copy(
        update={
            "alternatives": source.alternatives,
            "lifecycle_state": StructureLifecycleState.ALTERNATIVES_REGISTERED,
        }
    )
    controller.advance(alternatives_registered, requester=OWNER)
    test = StructureTestPreregistration(
        test_id="TEST-PAYMENT-PROCESS-MATCHED-NULL-20",
        target_hypothesis_id=HYPOTHESIS_ID,
        competing_hypothesis_ids=[item.id for item in source.alternatives],
        prediction_by_hypothesis={
            HYPOTHESIS_ID: "real linkage exceeds the matched-null 95th percentile",
            source.alternatives[0].id: "raw amount encoding has no linkage-specific gain",
            source.alternatives[1].id: "matched null equals or exceeds real linkage",
            source.alternatives[2].id: "arbitrary residue linkage matches real linkage",
        },
        falsification_condition="real mean AUC does not exceed the 20-null 95th percentile",
        confounders_preserved=[
            "ProductCD",
            "fourteen-day time bin",
            "log2 amount magnitude",
            "joint decimal residue marginal distribution",
            "raw missingness pattern",
        ],
        decision_affected="continue independent implications or retain encoding without structure claim",
        power_plan="20 matched-null repetitions on three forward horizons; sequential futility recorded",
        fold_safe=True,
        semantic_signature={
            "target_hypotheses": ["latent payment process proxy"],
            "data_slice": ["three forward product-time-amount contexts"],
            "operation": ["confounder-preserving matched linkage null"],
            "observable": ["real minus null AUC and null 95th percentile"],
            "decision_affected": ["structure promotion"],
            "candidate_producing": False,
        },
        null_repetitions=20,
    )
    critic = controller.preregister_test(HYPOTHESIS_ID, test, requester=OWNER)
    if not critic.passed:
        raise ValueError(f"falsification critic rejected the terminal test: {critic.reasons}")
    controller.record_partial_evidence(HYPOTHESIS_ID, [str(ablation_path)], requester=OWNER)
    controller.open_debt(
        HYPOTHESIS_ID,
        candidate_id="CAND-ISLAND-01-AMOUNT-MICROSTRUCTURE-CYCLE-03",
        requester=OWNER,
    )
    outcomes = {
        "competing_hypothesis_test": ValidationRequirementOutcome.PASSED,
        "confounder_preserving_null": (
            ValidationRequirementOutcome.PASSED if null_rejected else ValidationRequirementOutcome.FAILED
        ),
        "independent_implication": ValidationRequirementOutcome.WAIVED_BY_FAILED_PREREQUISITE,
        "fold_safety": ValidationRequirementOutcome.PASSED,
        "multi_context_replication": ValidationRequirementOutcome.WAIVED_BY_FAILED_PREREQUISITE,
        "decision_adoption": ValidationRequirementOutcome.WAIVED_BY_FAILED_PREREQUISITE,
    }
    for requirement, outcome in outcomes.items():
        controller.resolve_requirement(
            HYPOTHESIS_ID,
            requirement,
            artifact_ref=f"{ablation_path}#{requirement}:{outcome.value}",
            requester=OWNER,
            outcome=outcome,
        )
    assessment = controller.assess_promotion(
        HYPOTHESIS_ID,
        structural_validity_passed=decision.structural_validity_passed,
        predictive_improvement_passed=decision.predictive_improvement_passed,
        evidence_refs=[str(ablation_path)],
        requester=OWNER,
    )
    report: dict[str, object] = {
        "hypothesis_id": HYPOTHESIS_ID,
        "real_mean_auc": real_auc,
        "null_95pct_mean_auc": null_95,
        "real_exceeds_null_95pct": null_rejected,
        "null_repetitions": len(null_scores),
        "null_exceedances": sum(item >= real_auc for item in null_scores),
        "sequential_futility": futility.__dict__,
        "independent_implication_executed": False,
        "multi_context_multi_seed_executed": False,
        "adoption_test_executed": False,
        "downstream_tests_waived_after_required_null_gate_failure": not null_rejected,
        "debt": controller.debt(HYPOTHESIS_ID, controller=True).model_dump(mode="json"),
        "assessment": assessment.model_dump(mode="json"),
        "confirmed_fact_shareable": controller.can_share_as_confirmed_fact(HYPOTHESIS_ID),
        "terminal_reason": decision.reason,
    }
    _write(report_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--null-artifact",
        type=Path,
        default=Path(".runs/ieee-cis-v031-structure-debt/null-20"),
    )
    parser.add_argument(
        "--hypothesis",
        type=Path,
        default=Path(
            ".runs/ieee-cis-v03-adaptive-cycle-03-20260826/control/structures/"
            "hypotheses/island-01/ISLAND-01-H-AMOUNT-RAIL-001.json"
        ),
    )
    parser.add_argument("--output", type=Path, default=Path(".runs/ieee-cis-v031-structure-debt/terminal"))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2, sort_keys=True))
