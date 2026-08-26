from __future__ import annotations

import json
from pathlib import Path

import yaml

from epistemic_loop.controller.candidate_artifacts import candidate_required_outputs
from epistemic_loop.domain.models import CandidateArtifactRecord, CandidateDescriptors, OOFRecord
from epistemic_loop.qd.candidate_archive import CandidateArchive
from epistemic_loop.qd.meta_selector import FinalMetaSelector


def make_candidate(root: Path, identifier: str, agent: str, score: float) -> CandidateArtifactRecord:
    root.mkdir()
    (root / "model_artifact").mkdir()
    (root / "model_artifact" / "model.bin").write_bytes(b"model")
    candidate = {
        "candidate_id": identifier,
        "source_agent": agent,
        "git_commit": "abc123",
        "dataset_hash": "sha256:data",
        "environment_hash": "sha256:env",
        "validation": {
            "protocol": "multi_horizon_time_gap",
            "primary_score": score,
            "fold_scores": [score - 0.01, score, score + 0.01],
            "score_std": 0.01,
        },
        "leakage_check": {"passed": True},
        "reproducibility": {"passed": True, "seeds": [42, 43, 44]},
    }
    (root / "candidate.yaml").write_text(yaml.safe_dump(candidate), encoding="utf-8")
    (root / "run_manifest.yaml").write_text(
        yaml.safe_dump({"candidate_id": identifier, "dataset_hash": "sha256:data", "environment_hash": "sha256:env"}),
        encoding="utf-8",
    )
    (root / "feature_manifest.yaml").write_text(yaml.safe_dump({"features": ["uid_count"]}), encoding="utf-8")
    (root / "metrics.json").write_text(json.dumps({"auc": score}), encoding="utf-8")
    for name in set(candidate_required_outputs()) - {
        "candidate.yaml",
        "run_manifest.yaml",
        "feature_manifest.yaml",
        "metrics.json",
        "model_artifact",
    }:
        (root / name).write_bytes(b"artifact")
    return CandidateArtifactRecord(
        candidate_id=identifier,
        source_agent=agent,
        git_commit="abc123",
        dataset_hash="sha256:data",
        environment_hash="sha256:env",
        artifact_root=str(root),
        descriptor=CandidateDescriptors(
            source_agent=agent,
            epistemic_niche="entity_client" if agent == "agent-a" else "temporal",
            validation_world="time_group",
            model_family="lightgbm" if agent == "agent-a" else "logistic",
            representation="uid_aggregate",
            routing="known_new_client",
            post_processing="client_average",
            error_profile="new_client_specialist",
        ),
        primary_score=score,
        expected_forward_score=score,
        new_client_auc=score - 0.02,
        robustness=0.9,
        leakage_check_passed=True,
        reproducibility_passed=True,
    )


def test_archive_hides_other_agent_score_and_code(tmp_path: Path) -> None:
    archive = CandidateArchive()
    first = make_candidate(tmp_path / "a", "CAND-A", "agent-a", 0.91)
    second = make_candidate(tmp_path / "b", "CAND-B", "agent-b", 0.92)
    archive.promote(first)
    archive.promote(second)
    view = archive.agent_view("agent-a")
    assert view["own_candidates"] == [
        {"candidate_id": "CAND-A", "cell": next(iter(archive.occupancy)), "resource_cost": 0.0}
    ]
    assert "score" not in json.dumps(view)
    try:
        archive.artifact_root("CAND-B", requester="agent-a")
    except PermissionError:
        pass
    else:  # pragma: no cover
        raise AssertionError("another agent's code must be hidden")


def test_final_selector_uses_common_candidate_artifacts_and_locks_submission(tmp_path: Path) -> None:
    first = make_candidate(tmp_path / "a", "CAND-A", "agent-a", 0.91)
    second = make_candidate(tmp_path / "b", "CAND-B", "agent-b", 0.93)
    selector = FinalMetaSelector()
    selected = selector.select([first, second])
    assert selected.candidate_id == "CAND-B"
    locked = selector.lock_submission(selected, tmp_path / "locked")
    assert locked.submission.read_bytes() == b"artifact"
    assert selector.evaluate_hidden(locked, lambda _: 0.94) == 0.94


def test_final_selector_builds_nested_oof_ensemble() -> None:
    records = []
    for candidate_id, predictions in {"A": [0.1, 0.8, 0.3, 0.9], "B": [0.2, 0.7, 0.1, 0.8]}.items():
        records.extend(
            OOFRecord(
                row_id=str(index),
                fold_id=str(index % 2),
                target=target,
                oof_prediction=prediction,
                validation_world="common-forward",
                candidate_id=candidate_id,
            )
            for index, (target, prediction) in enumerate(zip([0, 1, 0, 1], predictions, strict=True))
        )
    ensemble = FinalMetaSelector().build_ensemble(
        records,
        run_id="run",
        ensemble_id="ENS-1",
        quality_floor_candidate_ids=["A", "B"],
    )
    assert set(ensemble.weights) == {"A", "B"}
    assert len(ensemble.fold_weights) == 2
