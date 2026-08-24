from __future__ import annotations

from abc import ABC, abstractmethod

from epistemic_loop.domain.models import ExperimentRequest, ExperimentResult


class ExecutorAdapter(ABC):
    @abstractmethod
    def submit(self, request: ExperimentRequest) -> ExperimentResult:
        raise NotImplementedError

    @abstractmethod
    def result(self, request: ExperimentRequest) -> ExperimentResult | None:
        raise NotImplementedError
