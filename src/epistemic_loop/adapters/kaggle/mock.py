from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MockSubmissionAdapter:
    scores: dict[str, tuple[float | None, float | None]]
    submitted: list[str] = field(default_factory=list)

    def submit(self, fingerprint: str) -> str:
        if fingerprint not in self.scores:
            raise KeyError(fingerprint)
        self.submitted.append(fingerprint)
        return f"mock-submission-{len(self.submitted)}"

    def score(self, fingerprint: str) -> dict[str, float | str | None]:
        public, private = self.scores[fingerprint]
        return {
            "public_score": public if public is not None else "not_available",
            "private_score": private if private is not None else "not_available",
        }
