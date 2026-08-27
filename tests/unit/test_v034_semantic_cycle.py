from __future__ import annotations

import hashlib
from pathlib import Path

from epistemic_loop.controller.cycle_contract import CycleArtifactContract, V034LockedRunContract
from epistemic_loop.controller.semantic_overlap import (
    SemanticExperimentRecord,
    SemanticOverlapClass,
    SemanticOverlapClassifier,
)
from epistemic_loop.evaluation.v032 import SystemArm


def _record(experiment: str, agent: str, *, model: str, preregistered: bool = True) -> SemanticExperimentRecord:
    return SemanticExperimentRecord(
        experiment,
        agent,
        "validation_random_vs_forward",
        "random validation inflates future score",
        "split comparison",
        "rank gap",
        "validation eligibility",
        model,
        "later rows",
        "learner sensitivity" if model == "linear" else "horizon replication",
        preregistered,
    )


def test_overlap_distinguishes_independent_replication_from_duplicate() -> None:
    classifier = SemanticOverlapClassifier()
    replication = classifier.classify((_record("e1", "a", model="tree"), _record("e2", "b", model="linear")))[0]
    duplicate = classifier.classify((_record("e1", "a", model="tree"), _record("e2", "a", model="tree")))[0]

    assert replication.classification is SemanticOverlapClass.INDEPENDENT_REPLICATION
    assert replication.qd_contribution
    assert "model" in replication.new_evidence_dimensions
    assert duplicate.classification is SemanticOverlapClass.REDUNDANT_DUPLICATION
    assert not duplicate.qd_contribution


def test_cycle_contract_grows_by_arm_and_validates_files(tmp_path: Path) -> None:
    contract = CycleArtifactContract()
    assert len(contract.required(SystemArm.B)) == 9
    assert len(contract.required(SystemArm.B_PLUS)) == 11
    assert len(contract.required(SystemArm.C)) == 16

    for name in contract.required(SystemArm.C):
        path = tmp_path / name
        if name == "experiment_source":
            path.mkdir()
            (path / "run.py").write_text("pass\n", encoding="utf-8")
        else:
            path.write_text("{}\n", encoding="utf-8")
    assert contract.validate(tmp_path, SystemArm.C).valid

    (tmp_path / "belief_update.yaml").unlink()
    result = contract.validate(tmp_path, SystemArm.C)
    assert not result.valid
    assert result.missing == ("belief_update.yaml",)


def test_locked_run_contract_requires_three_reports_nine_decisions_and_checksum(tmp_path: Path) -> None:
    for directory, count in (("agent_reports", 3), ("cycle_decisions", 9)):
        root = tmp_path / directory
        root.mkdir()
        for index in range(count):
            (root / f"{index}.json").write_text("{}\n", encoding="utf-8")
    for directory in ("common_crossfit", "sealed_predictions"):
        root = tmp_path / directory
        root.mkdir()
        (root / "artifact.json").write_text("{}\n", encoding="utf-8")
    for name in (
        "run_manifest.json",
        "locked_candidate_manifest.json",
        "locked_selection_reason.json",
        "final_retrain_lock.json",
    ):
        (tmp_path / name).write_text("{}\n", encoding="utf-8")
    submission = tmp_path / "locked_submission.csv"
    submission.write_text("TransactionID,isFraud\n1,0.1\n", encoding="utf-8")
    checksum = hashlib.sha256(submission.read_bytes()).hexdigest()
    (tmp_path / "locked_submission.sha256").write_text(checksum + "\n", encoding="utf-8")

    assert V034LockedRunContract().validate(tmp_path).valid

    (tmp_path / "locked_submission.sha256").write_text("bad\n", encoding="utf-8")
    invalid = V034LockedRunContract().validate(tmp_path)
    assert not invalid.valid
    assert "locked submission checksum mismatch" in invalid.invalid
