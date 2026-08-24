import subprocess

from epistemic_loop.adapters.kaggle.cli import KaggleCliSubmissionAdapter


def test_submit_uses_argument_vector_and_returns_receipt(tmp_path) -> None:
    artifact = tmp_path / "submission.csv"
    artifact.write_text("id,target\n", encoding="utf-8")
    calls = []

    def runner(args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "Successfully submitted 12345", "")

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
    assert receipt.reference == "12345"
