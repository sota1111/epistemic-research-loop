from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from epistemic_loop.domain.models import CandidateArtifactRecord, OOFEnsemble, OOFRecord
from epistemic_loop.oof.ensemble import build_cross_fitted_ensemble


@dataclass(frozen=True)
class FinalUtilityWeights:
    expected_forward_score: float = 1.0
    robustness: float = 0.15
    new_client_performance: float = 0.15
    marginal_ensemble_gain: float = 0.15
    uncertainty: float = 1.0
    leakage_risk: float = 1.0


@dataclass(frozen=True)
class LockedSubmission:
    candidate_id: str
    submission: Path
    sha256: str
    manifest: Path


def final_utility(candidate: CandidateArtifactRecord, weights: FinalUtilityWeights | None = None) -> float:
    weights = weights or FinalUtilityWeights()
    forward = candidate.expected_forward_score
    if forward is None:
        forward = candidate.primary_score
    new_client = candidate.new_client_auc if candidate.new_client_auc is not None else 0.0
    return (
        weights.expected_forward_score * forward
        + weights.robustness * candidate.robustness
        + weights.new_client_performance * new_client
        + weights.marginal_ensemble_gain * candidate.marginal_ensemble_gain
        - weights.uncertainty * candidate.uncertainty
        - weights.leakage_risk * candidate.leakage_risk
    )


class FinalMetaSelector:
    """Compare generated candidates, never merge the agents' beliefs."""

    COMMON_PROTOCOL = "multi_horizon_forward_gap+known_new_client+fold_safe_features"

    def shortlist(self, candidates: Sequence[CandidateArtifactRecord]) -> tuple[CandidateArtifactRecord, ...]:
        valid = [
            item
            for item in candidates
            if item.leakage_check_passed
            and item.reproducibility_passed
            and Path(item.artifact_root, "oof_predictions.parquet").is_file()
        ]
        if not valid:
            raise ValueError("no candidate passes leakage, reproducibility and OOF gates")
        return tuple(sorted(valid, key=lambda item: (-final_utility(item), item.candidate_id)))

    def common_crossfit(
        self,
        candidates: Sequence[CandidateArtifactRecord],
        evaluator: Callable[[CandidateArtifactRecord, str], CandidateArtifactRecord],
    ) -> tuple[CandidateArtifactRecord, ...]:
        rerun = tuple(evaluator(item, self.COMMON_PROTOCOL) for item in self.shortlist(candidates))
        for before, after in zip(self.shortlist(candidates), rerun, strict=True):
            if after.candidate_id != before.candidate_id:
                raise ValueError("common cross-fit evaluator changed candidate identity")
            if after.expected_forward_score is None:
                raise ValueError("common cross-fit must report expected_forward_score")
        return rerun

    def select(self, candidates: Sequence[CandidateArtifactRecord]) -> CandidateArtifactRecord:
        return max(self.shortlist(candidates), key=lambda item: (final_utility(item), item.candidate_id))

    def build_ensemble(
        self,
        records: Iterable[OOFRecord],
        *,
        run_id: str,
        ensemble_id: str,
        quality_floor_candidate_ids: Sequence[str],
    ) -> OOFEnsemble:
        allowed = set(quality_floor_candidate_ids)
        filtered = [item for item in records if item.candidate_id in allowed]
        if len({item.candidate_id for item in filtered}) < 2:
            raise ValueError("ensemble quality floor leaves fewer than two candidates")
        return build_cross_fitted_ensemble(filtered, run_id=run_id, ensemble_id=ensemble_id)

    def lock_submission(self, candidate: CandidateArtifactRecord, destination: str | Path) -> LockedSubmission:
        source = Path(candidate.artifact_root) / "submission.csv"
        if not source.is_file():
            raise FileNotFoundError(source)
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        target = root / "submission.csv"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise FileExistsError("locked submission already exists with different content")
        if not target.exists():
            shutil.copy2(source, target)
        manifest = root / "locked_submission.json"
        payload = {
            "candidate_id": candidate.candidate_id,
            "submission": str(target),
            "sha256": digest,
            "selection_utility": final_utility(candidate),
            "locked": True,
        }
        if manifest.exists() and json.loads(manifest.read_text(encoding="utf-8")) != payload:
            raise FileExistsError("locked selection manifest is immutable")
        manifest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return LockedSubmission(candidate.candidate_id, target, digest, manifest)

    @staticmethod
    def evaluate_hidden(
        locked: LockedSubmission,
        evaluator: Callable[[Path], float],
    ) -> float:
        if hashlib.sha256(locked.submission.read_bytes()).hexdigest() != locked.sha256:
            raise ValueError("locked submission content changed before hidden evaluation")
        return float(evaluator(locked.submission))
