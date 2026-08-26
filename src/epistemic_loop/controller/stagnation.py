from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

PREDICTIVE_DIVERSITY_NOTICE_JA = (
    "研究上のSemantic Diversityは存在しますが、CandidateのResidualは既存Archiveと強く相関しています。"
    "次のProposalでは、どのData Sliceで既存Candidateと異なる誤りをするかを事前登録し、"
    "その差を生むメカニズムを説明してください。"
)


@dataclass(frozen=True)
class ExplorationProgressSnapshot:
    cycle: int
    qd_occupancy: int
    validated_structure_count: int
    best_accepted_primary_metric: float | None
    open_validation_debt_count: int


@dataclass(frozen=True)
class ExplorationStagnationDecision:
    stagnated: bool
    consecutive_stagnant_cycles: int
    active_conditions: tuple[str, ...]


class ExplorationStagnationDetector:
    """Detect research progress stalling without calling semantic diversity collapse."""

    def __init__(self, *, required_consecutive_cycles: int = 2, metric_tolerance: float = 1e-12):
        if required_consecutive_cycles < 1:
            raise ValueError("required_consecutive_cycles must be positive")
        self.required_consecutive_cycles = required_consecutive_cycles
        self.metric_tolerance = metric_tolerance
        self._previous: ExplorationProgressSnapshot | None = None
        self._consecutive = 0

    def assess(self, snapshot: ExplorationProgressSnapshot) -> ExplorationStagnationDecision:
        if self._previous is not None and snapshot.cycle <= self._previous.cycle:
            raise ValueError("cycle numbers must strictly increase")
        conditions: tuple[str, ...] = ()
        if self._previous is not None:
            previous = self._previous
            metric_improved = _metric_improved(
                previous.best_accepted_primary_metric,
                snapshot.best_accepted_primary_metric,
                self.metric_tolerance,
            )
            checks = {
                "qd_occupancy_not_increased": snapshot.qd_occupancy <= previous.qd_occupancy,
                "no_new_validated_structure": (
                    snapshot.validated_structure_count <= previous.validated_structure_count
                ),
                "accepted_primary_metric_not_improved": not metric_improved,
                "validation_debt_not_reduced": (
                    snapshot.open_validation_debt_count >= previous.open_validation_debt_count
                ),
            }
            conditions = tuple(name for name, active in checks.items() if active)
            self._consecutive = self._consecutive + 1 if len(conditions) == len(checks) else 0
        self._previous = snapshot
        return ExplorationStagnationDecision(
            stagnated=self._consecutive >= self.required_consecutive_cycles,
            consecutive_stagnant_cycles=self._consecutive,
            active_conditions=conditions,
        )


def _metric_improved(previous: float | None, current: float | None, tolerance: float) -> bool:
    if current is None:
        return False
    if previous is None:
        return True
    return current > previous + tolerance


@dataclass(frozen=True)
class PredictiveCollapseMetrics:
    candidate_count: int
    residual_effective_rank: float
    mean_residual_correlation: float
    nested_ensemble_auc_gain: float


@dataclass(frozen=True)
class PredictiveCollapseDecision:
    collapsed: bool
    active_conditions: tuple[str, ...]
    notification: str | None


class PredictiveCollapseDetector:
    def __init__(
        self,
        *,
        minimum_candidates: int = 3,
        effective_rank_threshold: float = 1.2,
        residual_correlation_threshold: float = 0.95,
        ensemble_auc_gain_threshold: float = 0.0,
    ):
        self.minimum_candidates = minimum_candidates
        self.effective_rank_threshold = effective_rank_threshold
        self.residual_correlation_threshold = residual_correlation_threshold
        self.ensemble_auc_gain_threshold = ensemble_auc_gain_threshold

    def assess(self, metrics: PredictiveCollapseMetrics) -> PredictiveCollapseDecision:
        checks = {
            "enough_common_crossfit_candidates": metrics.candidate_count >= self.minimum_candidates,
            "low_residual_effective_rank": (metrics.residual_effective_rank < self.effective_rank_threshold),
            "high_mean_residual_correlation": (metrics.mean_residual_correlation > self.residual_correlation_threshold),
            "no_nested_ensemble_auc_gain": (metrics.nested_ensemble_auc_gain <= self.ensemble_auc_gain_threshold),
        }
        collapsed = all(checks.values())
        return PredictiveCollapseDecision(
            collapsed=collapsed,
            active_conditions=tuple(name for name, active in checks.items() if active),
            notification=PREDICTIVE_DIVERSITY_NOTICE_JA if collapsed else None,
        )


class PredictiveDiversityDebtStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


@dataclass(frozen=True)
class PredictiveDiversityDebt:
    debt_id: str
    candidate_id: str
    preregistered_data_slice: str
    proposed_error_mechanism: str
    archive_residual_correlation_floor: float
    quality_floor: float
    status: PredictiveDiversityDebtStatus = PredictiveDiversityDebtStatus.OPEN
    resolution_reason: str | None = None

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.debt_id,
                self.candidate_id,
                self.preregistered_data_slice,
                self.proposed_error_mechanism,
            )
        ):
            raise ValueError("predictive diversity debt requires a candidate, slice, and mechanism")
        if not -1 <= self.archive_residual_correlation_floor <= 1:
            raise ValueError("archive residual correlation floor must lie in [-1, 1]")

    def assess_candidate(
        self,
        *,
        candidate_quality: float,
        minimum_residual_correlation: float,
        nested_marginal_auc_gain: float,
    ) -> PredictiveDiversityDebt:
        quality_passed = candidate_quality >= self.quality_floor
        lower_correlation = minimum_residual_correlation < self.archive_residual_correlation_floor
        positive_ensemble_gain = nested_marginal_auc_gain > 0.0
        if quality_passed and (lower_correlation or positive_ensemble_gain):
            reason = (
                "quality_floor_and_lower_residual_correlation"
                if lower_correlation
                else "quality_floor_and_positive_nested_ensemble_gain"
            )
            return PredictiveDiversityDebt(
                debt_id=self.debt_id,
                candidate_id=self.candidate_id,
                preregistered_data_slice=self.preregistered_data_slice,
                proposed_error_mechanism=self.proposed_error_mechanism,
                archive_residual_correlation_floor=self.archive_residual_correlation_floor,
                quality_floor=self.quality_floor,
                status=PredictiveDiversityDebtStatus.RESOLVED,
                resolution_reason=reason,
            )
        return self


class PredictiveDiversityDebtRegistry:
    """Durably manage opt-in v0.4-candidate debts without changing v0.3 policy."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def open(self, debt: PredictiveDiversityDebt) -> PredictiveDiversityDebt:
        path = self._path(debt.debt_id)
        if path.exists():
            raise ValueError(f"predictive diversity debt already exists: {debt.debt_id}")
        self._write(path, debt)
        return debt

    def get(self, debt_id: str) -> PredictiveDiversityDebt:
        path = self._path(debt_id)
        if not path.is_file():
            raise KeyError(debt_id)
        value = json.loads(path.read_text(encoding="utf-8"))
        value["status"] = PredictiveDiversityDebtStatus(value["status"])
        return PredictiveDiversityDebt(**value)

    def assess(
        self,
        debt_id: str,
        *,
        candidate_quality: float,
        minimum_residual_correlation: float,
        nested_marginal_auc_gain: float,
    ) -> PredictiveDiversityDebt:
        updated = self.get(debt_id).assess_candidate(
            candidate_quality=candidate_quality,
            minimum_residual_correlation=minimum_residual_correlation,
            nested_marginal_auc_gain=nested_marginal_auc_gain,
        )
        self._write(self._path(debt_id), updated)
        return updated

    def _path(self, debt_id: str) -> Path:
        if not debt_id or Path(debt_id).name != debt_id:
            raise ValueError("debt identifier must be a safe path component")
        return self.root / f"{debt_id}.json"

    @staticmethod
    def _write(path: Path, debt: PredictiveDiversityDebt) -> None:
        payload = {**debt.__dict__, "status": debt.status.value}
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
