"""Tests for when a leaderboard submission is worth spending.

The thing being protected is that a submission has to be able to change a decision. Each test
below is a situation where the naive answer -- "submit the best candidate" -- spends a fifth of a
day to learn nothing, or refuses to spend one that would have taught the run something.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from epistemic_loop.controller.submission_policy import (
    Candidate,
    SubmittedPoint,
    decide,
    kendall_tau,
)


@pytest.fixture
def files(tmp_path: Path):
    """Real files, because a candidate that is not on disk is not a candidate."""

    def make(*names: str) -> dict[str, str]:
        paths = {}
        for name in names:
            path = tmp_path / f"{name}.csv"
            path.write_text(name, encoding="utf-8")
            paths[name] = str(path)
        return paths

    return make


def _fingerprint(path: str) -> str:
    return Path(path).name


def _decide(candidates, submitted, **overrides):  # type: ignore[no-untyped-def]
    arguments = {
        "remaining_today": 5,
        "metric_direction": "minimize",
        "fingerprint_of": _fingerprint,
    }
    arguments.update(overrides)
    return decide(candidates, submitted, **arguments)  # type: ignore[arg-type]


def test_tau_handles_ties_and_refuses_to_answer_from_one_point() -> None:
    assert kendall_tau([1.0], [2.0]) is None, "one point orders nothing"
    assert kendall_tau([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None, "an all-tied side has no ranking"
    assert kendall_tau([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0
    assert kendall_tau([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) == -1.0


def test_the_first_submission_goes_to_the_best_local_candidate(files) -> None:
    """With nothing measured, the local estimate is the only thing there is to act on."""
    paths = files("a", "b")
    decision = _decide(
        [
            Candidate("a", paths["a"], local_estimate=15.9),
            Candidate("b", paths["b"], local_estimate=12.3),
        ],
        [],
    )

    assert decision.spend and decision.candidate is not None
    assert decision.candidate.name == "b", "12.3 beats 15.9 on a minimised metric"
    assert "has not been shown to transfer" in decision.reason
    assert decision.agreement is None and decision.calibration_points == 0


def test_while_calibrating_spread_beats_quality(files) -> None:
    """Two submissions with near-identical local estimates barely constrain the relationship.

    The point of an early submission is to learn how the local number maps to the leaderboard, and
    a point next to one already measured teaches almost nothing about the mapping.
    """
    paths = files("near", "far")
    decision = _decide(
        [
            Candidate("near", paths["near"], local_estimate=12.2),
            Candidate("far", paths["far"], local_estimate=40.0),
        ],
        [SubmittedPoint("old.csv", local_estimate=12.3, public_score=13.0)],
    )

    assert decision.spend and decision.candidate is not None
    assert decision.candidate.name == "far", "'near' is locally better and teaches less"
    assert "is not yet usable" in decision.reason


def test_once_the_ranking_transfers_a_gain_inside_the_noise_is_refused(files) -> None:
    """A leaderboard cannot resolve a difference the local estimate did not measure."""
    paths = files("marginal")
    submitted = [
        SubmittedPoint("s1", local_estimate=20.0, public_score=21.0),
        SubmittedPoint("s2", local_estimate=15.0, public_score=16.0),
        SubmittedPoint("s3", local_estimate=12.0, public_score=13.0),
    ]
    decision = _decide(
        [Candidate("marginal", paths["marginal"], local_estimate=11.8, local_noise=1.3)],
        submitted,
    )

    assert not decision.spend
    assert decision.agreement == 1.0
    assert "within its measurement noise" in decision.reason

    clear = _decide(
        [Candidate("marginal", paths["marginal"], local_estimate=8.0, local_noise=1.3)],
        submitted,
    )
    assert clear.spend and "exceeds its own measurement noise" in clear.reason


def test_when_the_ranking_does_not_transfer_being_locally_best_is_not_a_reason(files) -> None:
    """The IEEE-CIS result: local CV and the public leaderboard agreed at tau 0.00, and the
    locally worst candidate won. Submitting the locally best one is then a bet on a relationship
    that has been measured and found absent."""
    paths = files("best_local", "distant")
    submitted = [
        SubmittedPoint("s1", local_estimate=10.0, public_score=13.0),
        SubmittedPoint("s2", local_estimate=11.0, public_score=12.0),
        SubmittedPoint("s3", local_estimate=12.0, public_score=14.0),
        SubmittedPoint("s4", local_estimate=13.0, public_score=12.5),
    ]
    decision = _decide(
        [
            Candidate("best_local", paths["best_local"], local_estimate=9.9, local_noise=0.2),
            Candidate("distant", paths["distant"], local_estimate=30.0, local_noise=0.2),
        ],
        submitted,
    )

    assert decision.agreement is not None and decision.agreement < 0.3
    assert decision.spend and decision.candidate is not None
    assert decision.candidate.name == "distant", "not a bet on the local estimate"
    assert "does not transfer" in decision.reason and "constrains the relationship" in decision.reason


def test_an_exhausted_allowance_and_a_duplicate_artifact_both_refuse(files) -> None:
    paths = files("a")
    candidates = [Candidate("a", paths["a"], local_estimate=12.0)]

    spent = _decide(candidates, [], remaining_today=0)
    assert not spent.spend and "daily allowance is spent" in spent.reason

    duplicate = _decide(candidates, [SubmittedPoint(_fingerprint(paths["a"]))])
    assert not duplicate.spend and "already known" in duplicate.reason

    missing = _decide([Candidate("gone", "/nowhere/x.csv", local_estimate=1.0)], [])
    assert not missing.spend


def test_direction_decides_which_candidate_is_best(files) -> None:
    """The same numbers, the opposite choice. Nothing else in the decision changes."""
    paths = files("low", "high")
    candidates = [
        Candidate("low", paths["low"], local_estimate=0.90),
        Candidate("high", paths["high"], local_estimate=0.96),
    ]

    assert _decide(candidates, [], metric_direction="maximize").candidate.name == "high"
    assert _decide(candidates, [], metric_direction="minimize").candidate.name == "low"


def _observation(identifier: str, metrics: dict[str, float], uris: list[str], status: str = "completed"):  # type: ignore[no-untyped-def]
    from datetime import UTC, datetime

    from epistemic_loop.domain.models import ArtifactRef, Observation

    return Observation(
        id=f"OB-{identifier}",
        experiment_id=identifier,
        run_id="run-1",
        metrics=metrics,
        artifacts=[
            ArtifactRef(
                uri=uri,
                sha256="a" * 64,
                experiment_id=identifier,
                code_commit_sha="c" * 40,
                dataset_fingerprint="d" * 64,
                environment_hash="e" * 64,
                mime_type="text/csv",
                size=1,
            )
            for uri in uris
        ],
        code_commit_sha="c" * 40,
        environment_hash="e" * 64,
        dataset_fingerprint="d" * 64,
        exit_status=status,
        created_at=datetime(2026, 8, 25, tzinfo=UTC),
    )


def test_candidates_come_from_the_run_s_own_record_with_the_number_that_produced_them() -> None:
    """A hand-maintained candidate list drifts from the results it claims to describe, and then a
    submission is decided on a number belonging to a different file."""
    from types import SimpleNamespace

    from epistemic_loop.controller.submission_policy import candidates_from_state

    state = SimpleNamespace(
        observations={
            "a": _observation("E-A", {"rmse": 12.3, "rmse_fold_std": 1.1, "rmse_seed_std": 0.2}, ["/x/submission.csv"]),
            "b": _observation("E-B", {"rmse": 15.9}, ["/y/per_well.csv"]),
            "c": _observation("E-C", {"rmse": 9.9}, ["/z/submission.csv"], status="failed"),
            "d": _observation("E-D", {"other": 1.0}, ["/w/submission.csv"]),
        }
    )

    candidates = candidates_from_state(state, primary_metric="rmse")  # type: ignore[arg-type]

    assert [item.name for item in candidates] == ["E-A"], "only completed runs with the metric and the artifact"
    assert candidates[0].local_estimate == 12.3
    assert candidates[0].local_noise == 1.1, "the widest measured spread, not the most flattering one"


def test_a_revealed_score_reaches_the_calibration_without_editing_the_ledger() -> None:
    """The ledger is append-only, so a score revealed later arrives as its own record. The spend
    and the disclosure stay separately timestamped, and the calibration still sees both."""
    from epistemic_loop.controller.submission_policy import submitted_from_ledger

    records = [
        {"mode": "execute", "competition": "c", "sha256": "f1", "score_id": "s1", "local_estimate": 12.3},
        {"mode": "execute", "competition": "c", "sha256": "f2", "score_id": "s2", "local_estimate": 15.9},
        {"mode": "execute", "competition": "other", "sha256": "f3", "score_id": "s3", "local_estimate": 1.0},
        {"mode": "score_revealed", "score_id": "s1", "public_score": 13.0},
    ]

    points = submitted_from_ledger(records, "c")

    assert [item.fingerprint for item in points] == ["f1", "f2"], "another competition is not this one's evidence"
    assert points[0].public_score == 13.0
    assert points[1].public_score is None, "a submission whose score is still sealed cannot calibrate anything"
