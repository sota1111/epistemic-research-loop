import subprocess

from epistemic_loop.adapters.kaggle.cli import KaggleCliSubmissionAdapter


def test_submit_uses_argument_vector_and_returns_receipt(tmp_path) -> None:
    artifact = tmp_path / "submission.csv"
    artifact.write_text("id,target\n", encoding="utf-8")
    calls = []

    def runner(args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "100%|####| 14.0M/14.0M\nSuccessfully submitted 55749923", "")

    receipt = KaggleCliSubmissionAdapter(runner).submit("example", artifact, "message")
    assert calls[0][0] == [
        "kaggle",
        "competitions",
        "submit",
        "-c",
        "example",
        "-f",
        str(artifact),
        "-m",
        "message",
    ]
    assert receipt.reference == "55749923", "a real Kaggle reference is a long digit run"


def test_upload_chatter_is_not_mistaken_for_a_submission_reference(tmp_path) -> None:
    """Most `kaggle competitions submit` runs print no reference at all.

    Its output is a progress bar and a success line, and the short numbers in them belong to the
    upload size. Reading one of those as a reference makes `wait_for_terminal_status` poll for an id
    that will never appear, so the caller waits out its whole deadline on a submission that already
    finished. None is the correct answer, and it means "match the newest row".
    """
    artifact = tmp_path / "submission.csv"
    artifact.write_text("id,target\n", encoding="utf-8")

    def runner(args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args, 0, "100%|##########| 14.0M/14.0M [00:03<00:00, 4.20MB/s]", "")

    assert KaggleCliSubmissionAdapter(runner).submit("example", artifact, "message").reference is None


def test_waiting_falls_back_to_the_newest_row_when_the_reference_never_appears(tmp_path) -> None:
    """A wrongly-parsed reference must not cost the caller its entire timeout."""
    rows = (
        "ref,fileName,date,description,status,publicScore,privateScore\n"
        "999,submission.csv,2026-08-24,m,SubmissionStatus.COMPLETE,0.93,0.90\n"
    )

    def runner(args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args, 0, rows, "")

    row = KaggleCliSubmissionAdapter(runner).wait_for_terminal_status(
        "example", reference="12345678", timeout_seconds=1, poll_seconds=0
    )
    assert str(row["ref"]) == "999"
    assert row["publicScore"] == 0.93
