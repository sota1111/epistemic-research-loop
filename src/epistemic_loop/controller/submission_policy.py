"""When to spend one of the day's submissions, and on what.

A leaderboard submission is not a measurement the run is entitled to; it is a fifth of a day. The
question is never "is this candidate good" but "can the answer change what happens next". Three
things make that a real question rather than a formality:

- The local estimate may not transfer. On the IEEE-CIS run the rank correlation between local CV
  and the public leaderboard was measured at 0.00 across five preregistered candidates -- the
  candidate ranked last locally won on private. Assuming the local ranking transfers is the
  failure mode this module exists to prevent.
- Whether it transfers is itself measurable, but only by spending submissions. Early submissions
  are worth spending *because* the relationship is unknown, and the ones that teach the most are
  the ones spread furthest apart, not the ones that look best.
- Once the relationship is known, a candidate whose local improvement is smaller than the local
  measurement noise cannot change anything, whichever way the correlation went.

Nothing here reads a private score. The public figures it consumes reach it through the budgeted
leaderboard gate, and the decision it returns is a recommendation with its reasoning attached, not
a side effect.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from epistemic_loop.scoring.normalization import higher_is_better

if TYPE_CHECKING:
    from epistemic_loop.controller.run_state import RunState

#: How a candidate file is identified for duplicate detection. Injected rather than imported so
#: the policy can be tested without hashing real submission files.
Fingerprint = Callable[[str], str]


@dataclass(frozen=True)
class Candidate:
    """A submittable artifact and the local estimate that argues for it."""

    name: str
    file: str
    local_estimate: float
    #: Spread of the local estimate under reruns -- fold or seed standard deviation. An improvement
    #: smaller than this is not an improvement that was measured.
    local_noise: float = 0.0
    experiment_id: str | None = None


@dataclass(frozen=True)
class SubmittedPoint:
    """A submission already spent, and what it paired."""

    fingerprint: str
    local_estimate: float | None = None
    public_score: float | None = None


@dataclass(frozen=True)
class SubmissionDecision:
    spend: bool
    reason: str
    remaining_today: int
    calibration_points: int
    candidate: Candidate | None = None
    agreement: float | None = None
    considered: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, object]:
        return {
            "spend": self.spend,
            "reason": self.reason,
            "remaining_today": self.remaining_today,
            "calibration_points": self.calibration_points,
            "agreement": self.agreement,
            "candidate": None if self.candidate is None else self.candidate.__dict__,
            "considered": list(self.considered),
        }


def kendall_tau(left: list[float], right: list[float]) -> float | None:
    """Rank correlation (tau-b) between two equal-length sequences.

    Used rather than a linear correlation because what matters is whether the leaderboard *orders*
    candidates the way the local estimate does. A perfectly calibrated ranking with a nonlinear
    scale is still a ranking worth trusting; a high linear correlation with reversed order is not.
    """
    if len(left) != len(right):
        raise ValueError("kendall_tau needs two sequences of the same length")
    if len(left) < 2:
        return None
    concordant = discordant = tied_left = tied_right = 0
    for i in range(len(left)):
        for j in range(i + 1, len(left)):
            a, b = left[i] - left[j], right[i] - right[j]
            if a == 0 and b == 0:
                continue
            if a == 0:
                tied_left += 1
            elif b == 0:
                tied_right += 1
            elif (a > 0) == (b > 0):
                concordant += 1
            else:
                discordant += 1
    denominator = ((concordant + discordant + tied_left) * (concordant + discordant + tied_right)) ** 0.5
    return None if denominator == 0 else (concordant - discordant) / denominator


def _eligible(candidates: list[Candidate], spent: set[str], fingerprint_of: Fingerprint) -> list[Candidate]:
    return [item for item in candidates if Path(item.file).is_file() and fingerprint_of(item.file) not in spent]


def decide(
    candidates: list[Candidate],
    submitted: list[SubmittedPoint],
    *,
    remaining_today: int,
    metric_direction: str,
    fingerprint_of: Fingerprint,
    minimum_calibration_points: int = 3,
    agreement_threshold: float = 0.3,
    noise_multiplier: float = 1.0,
) -> SubmissionDecision:
    """Recommend whether to spend a submission now, and on which candidate.

    The order of the checks is the argument. Allowance and duplication come first because they are
    facts, not judgements. Then the question splits on whether the local-to-public relationship has
    been measured at all: before it has, a submission buys the relationship; after it has, a
    submission is only worth spending if the relationship says the candidate's local advantage
    means something and the advantage is larger than the noise it was measured with.
    """
    ranked = sorted(candidates, key=lambda item: higher_is_better(item.local_estimate, metric_direction), reverse=True)
    considered = tuple(item.name for item in ranked)
    paired = [
        item for item in submitted if item.local_estimate is not None and item.public_score is not None
    ]
    agreement = kendall_tau(
        [higher_is_better(item.local_estimate, metric_direction) for item in paired],  # type: ignore[arg-type]
        [higher_is_better(item.public_score, metric_direction) for item in paired],  # type: ignore[arg-type]
    )

    def refuse(reason: str) -> SubmissionDecision:
        return SubmissionDecision(
            spend=False,
            reason=reason,
            remaining_today=remaining_today,
            calibration_points=len(paired),
            agreement=agreement,
            considered=considered,
        )

    def commit(candidate: Candidate, reason: str) -> SubmissionDecision:
        return SubmissionDecision(
            spend=True,
            reason=reason,
            remaining_today=remaining_today,
            calibration_points=len(paired),
            candidate=candidate,
            agreement=agreement,
            considered=considered,
        )

    if remaining_today <= 0:
        return refuse("the daily allowance is spent; the next one resets at 00:00 UTC")

    available = _eligible(ranked, {item.fingerprint for item in submitted}, fingerprint_of)
    if not available:
        return refuse(
            "no candidate is both present on disk and unsubmitted; an identical artifact would "
            "return a score that is already known"
        )

    submitted_locals = [item.local_estimate for item in submitted if item.local_estimate is not None]

    if len(paired) < minimum_calibration_points:
        if not submitted_locals:
            best = available[0]
            return commit(
                best,
                f"nothing has been submitted yet, so the local estimate has not been shown to "
                f"transfer at all; spending on the best local candidate ({best.local_estimate:g}) "
                f"establishes the first point of the relationship",
            )
        # Spread beats quality while calibrating. Two submissions with near-identical local
        # estimates constrain the local-to-public relationship barely more than one does.
        distant = max(available, key=lambda item: min(abs(item.local_estimate - value) for value in submitted_locals))
        separation = min(abs(distant.local_estimate - value) for value in submitted_locals)
        return commit(
            distant,
            f"the local-to-public relationship rests on {len(paired)} of {minimum_calibration_points} "
            f"points and is not yet usable; this candidate sits {separation:g} from the nearest "
            f"local estimate already measured, which is the most any available candidate would add",
        )

    best = available[0]
    best_submitted = max(higher_is_better(value, metric_direction) for value in submitted_locals)
    improvement = higher_is_better(best.local_estimate, metric_direction) - best_submitted
    threshold = noise_multiplier * best.local_noise

    if agreement is not None and agreement >= agreement_threshold:
        if improvement > threshold:
            return commit(
                best,
                f"the local ranking transfers (tau {agreement:+.2f} over {len(paired)} points) and "
                f"this candidate improves on the best already submitted by {improvement:g}, which "
                f"exceeds its own measurement noise of {threshold:g}",
            )
        return refuse(
            f"the local ranking transfers (tau {agreement:+.2f}) but the best candidate's "
            f"improvement of {improvement:g} is within its measurement noise of {threshold:g}; the "
            f"leaderboard cannot resolve a difference the local estimate did not"
        )

    # The local estimate does not order the leaderboard. A locally-better candidate is then not
    # evidence of anything, so "best" is not a reason to spend. What is still worth buying is a
    # point that constrains the relationship, which means the one furthest from what is known.
    distant = max(available, key=lambda item: min(abs(item.local_estimate - value) for value in submitted_locals))
    separation = min(abs(distant.local_estimate - value) for value in submitted_locals)
    if separation <= threshold:
        return refuse(
            f"the local ranking does not transfer (tau {agreement:+.2f} over {len(paired)} points), "
            f"so a locally better candidate is not a reason to submit, and no available candidate "
            f"is far enough from what has been measured ({separation:g}) to constrain the "
            f"relationship further"
        )
    return commit(
        distant,
        f"the local ranking does not transfer (tau {agreement:+.2f} over {len(paired)} points), so "
        f"this is not a bet on the local estimate; it is the candidate that best constrains the "
        f"relationship, sitting {separation:g} from the nearest measured point",
    )


#: Metric keys that describe how much a local estimate moves under reruns. The largest one wins,
#: because the noise a candidate should be judged against is the widest spread anyone measured for
#: it -- taking the smallest would let a method pick its own most flattering error bar.
NOISE_KEYS = ("_seed_std", "_fold_std", "_std")


def candidates_from_state(
    state: RunState,
    *,
    primary_metric: str,
    artifact_suffix: str = "submission.csv",
) -> list[Candidate]:
    """Read submittable candidates out of the run's own record.

    A candidate is not something a human lists in a file; it is an artifact some experiment already
    produced, together with the number that experiment measured for it. Deriving it from the event
    log is what keeps the two attached -- a hand-maintained candidate list drifts from the results
    it claims to describe, and then the decision is made about a number belonging to a different
    file.
    """
    candidates: list[Candidate] = []
    for observation in sorted(state.observations.values(), key=lambda item: item.created_at):
        estimate = observation.metrics.get(primary_metric)
        if estimate is None or observation.exit_status != "completed":
            continue
        noise = max(
            (
                value
                for key, value in observation.metrics.items()
                if key.startswith(primary_metric) and key.endswith(NOISE_KEYS)
            ),
            default=0.0,
        )
        for artifact in observation.artifacts:
            if not str(artifact.uri).endswith(artifact_suffix):
                continue
            candidates.append(
                Candidate(
                    name=observation.experiment_id,
                    file=str(artifact.uri),
                    local_estimate=float(estimate),
                    local_noise=float(noise),
                    experiment_id=observation.experiment_id,
                )
            )
    return candidates


def submitted_from_ledger(records: list[dict[str, object]], competition: str) -> list[SubmittedPoint]:
    """Reconstruct what has been spent, and what each spend paired.

    `public_score` is present only for submissions whose score has been revealed through the
    leaderboard gate. One that has not been revealed still counts against the allowance and still
    blocks its own duplicate, but it cannot contribute to the calibration -- which is the honest
    outcome, since the run genuinely does not know its score yet.
    """
    # The ledger is append-only, so a score revealed after the fact arrives as its own record
    # rather than as an edit to the submission's. Merging them here keeps the audit trail intact:
    # the spend and the disclosure stay two separate, separately-timestamped events.
    revealed = {
        str(record.get("score_id")): _optional_float(record.get("public_score"))
        for record in records
        if record.get("mode") == "score_revealed" and record.get("score_id")
    }
    points = []
    for record in records:
        if record.get("competition") != competition or record.get("mode") != "execute":
            continue
        public = _optional_float(record.get("public_score"))
        if public is None:
            public = revealed.get(str(record.get("score_id")))
        points.append(
            SubmittedPoint(
                fingerprint=str(record.get("sha256") or ""),
                local_estimate=_optional_float(record.get("local_estimate")),
                public_score=public,
            )
        )
    return points


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
