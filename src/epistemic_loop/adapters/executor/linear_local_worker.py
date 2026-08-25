from __future__ import annotations

from pathlib import Path

from epistemic_loop.adapters.executor.ai_dev_control_plane import AiDevControlPlaneAdapter
from epistemic_loop.adapters.executor.base import ExecutorAdapter
from epistemic_loop.adapters.executor.local import LocalExecutor
from epistemic_loop.domain.models import ExperimentRequest, ExperimentResult


class LinearLocalWorkerAdapter(ExecutorAdapter):
    """Files the Linear ticket for real, then runs it on this machine.

    `ai_dev_control_plane` files a ticket and waits for a worker fleet to pick it up. That fleet is
    not part of this repository, so a verification run using that adapter alone stalls after the
    first dispatch and proves only that a ticket can be created.

    This adapter keeps the half that is under test — the loop deciding what to file next, and filing
    it automatically — and substitutes a local process for the fleet. **The ticket is genuine and
    auto-filed; the execution is local.** It is a verification harness, not a production executor:
    a real run uses `ai_dev_control_plane` and a real worker, and nothing here should be read as
    evidence that the control plane's queue, worker selection, or retry policy was exercised.

    The Linear issue identifier is carried through on the result as `external_ref`, so every
    experiment in the event log can be traced back to the ticket the loop filed for it.
    """

    def __init__(self, control_plane: AiDevControlPlaneAdapter, local: LocalExecutor):
        self.control_plane = control_plane
        self.local = local

    def submit(self, request: ExperimentRequest) -> ExperimentResult:
        filed = self.control_plane.submit(request)
        executed = self.local.submit(request)
        result = executed.model_copy(update={"external_ref": filed.external_ref})
        self._result_path(request).write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return result

    def _result_path(self, request: ExperimentRequest) -> Path:
        return self.local.result_root / request.run_id / request.experiment_id / "result.json"

    def result(self, request: ExperimentRequest) -> ExperimentResult | None:
        return self.local.result(request)
