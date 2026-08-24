from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from epistemic_loop.domain.models import ExperimentRequest, ExperimentResult


class ExecutorAdapter(ABC):
    @abstractmethod
    def submit(self, request: ExperimentRequest) -> ExperimentResult:
        raise NotImplementedError

    @abstractmethod
    def result(self, request: ExperimentRequest) -> ExperimentResult | None:
        raise NotImplementedError


def result_path(result_root: str | Path, run_id: str, experiment_id: str) -> Path:
    """Shared result-store layout; the local and control-plane adapters both write here."""
    return Path(result_root) / run_id / experiment_id / "result.json"
