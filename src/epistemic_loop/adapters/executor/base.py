from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from epistemic_loop.domain.models import ExperimentRequest, ExperimentResult


@dataclass(frozen=True)
class ExecutionContract:
    """What an executor needs a proposal to carry, declared where the executor is defined.

    Every executor has always had such a requirement; none of them stated it anywhere the party
    writing the proposal could read. The shell executors need a `command`; the one that files a
    development ticket needs a `brief`, and a command means nothing to it. A proposal written
    against the wrong one is refused at dispatch -- after design, gating and selection have all
    succeeded -- which loses the round for something checkable before any of it.

    So the requirement travels: the gate enforces it, and the designer is shown it.
    """

    #: `shell` -- the executor runs a command. `brief` -- it instructs a developer.
    kind: str = "shell"
    #: Keys `implementation_request` must carry.
    required_fields: tuple[str, ...] = ("command",)
    #: Keys a `brief` must carry, when one is required.
    required_brief_fields: tuple[str, ...] = ()
    #: Said to the designer in its own terms. This is the sentence that prevents the round.
    note: str = (
        "Write `implementation_request.command` as a single shell command that runs the experiment "
        "and writes its metrics to $ERL_OUTPUT_DIR."
    )

    def describe(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "required_fields": list(self.required_fields),
            "required_brief_fields": list(self.required_brief_fields),
            "note": self.note,
        }


SHELL_CONTRACT = ExecutionContract()

BRIEF_CONTRACT = ExecutionContract(
    kind="brief",
    required_fields=("brief",),
    required_brief_fields=("title", "objective", "approach", "verification"),
    note=(
        "This experiment is carried out by a developer working in the competition repository, not "
        "by a shell. Put the work in `implementation_request.brief` as an object with `title`, "
        "`objective`, `approach` and `verification`, written in that repository's own terms: what "
        "to measure, how, and what would count as done. `metrics`, `artifacts` and `notes` are "
        "optional lists alongside them. A `command` is ignored -- do not spend the design on one."
    ),
)


class ExecutorAdapter(ABC):
    #: Overridden by executors whose proposals must look different. See `ExecutionContract`.
    contract: ExecutionContract = SHELL_CONTRACT

    @abstractmethod
    def submit(self, request: ExperimentRequest) -> ExperimentResult:
        raise NotImplementedError

    @abstractmethod
    def result(self, request: ExperimentRequest) -> ExperimentResult | None:
        raise NotImplementedError


def result_path(result_root: str | Path, run_id: str, experiment_id: str) -> Path:
    """Shared result-store layout; the local and control-plane adapters both write here."""
    return Path(result_root) / run_id / experiment_id / "result.json"
