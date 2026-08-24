from datetime import UTC, datetime

from epistemic_loop.adapters.kaggle.submission import (
    SubmissionCandidate,
    SubmissionLedger,
    fingerprint,
    plan_submission,
)


def test_plan_obeys_priority_cap_and_duplicate_guard(tmp_path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_text("id,target\n1,0\n", encoding="utf-8")
    second.write_text("id,target\n1,1\n", encoding="utf-8")
    candidates = [
        SubmissionCandidate("second", str(second), priority=2),
        SubmissionCandidate("first", str(first), priority=1),
    ]
    plan = plan_submission("example", candidates, submitted_today=0, daily_cap=2)
    assert plan.selected == candidates[1]
    plan = plan_submission(
        "example",
        candidates,
        submitted_today=1,
        daily_cap=2,
        submitted_fingerprints={fingerprint(first)},
    )
    assert plan.selected == candidates[0]
    assert plan_submission("example", candidates, submitted_today=2, daily_cap=2).selected is None


def test_ledger_is_append_only_and_counts_utc_day(tmp_path) -> None:
    ledger = SubmissionLedger(tmp_path / "ledger.jsonl")
    ledger.append(
        {
            "competition": "example",
            "mode": "execute",
            "created_at": "2026-08-24T01:00:00+00:00",
            "sha256": "abc",
        }
    )
    assert ledger.submitted_today("example", datetime(2026, 8, 24, tzinfo=UTC)) == 1
    assert ledger.fingerprints("example") == {"abc"}
