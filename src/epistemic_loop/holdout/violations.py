from __future__ import annotations

from datetime import datetime

from pydantic import Field

from epistemic_loop.domain.models import DomainModel, utc_now


class HoldoutViolation(DomainModel):
    run_id: str
    code: str
    description: str
    actor: str
    detected_at: datetime = Field(default_factory=utc_now)
    blocked: bool = True


class HoldoutViolationError(PermissionError):
    def __init__(self, violation: HoldoutViolation):
        super().__init__(violation.description)
        self.violation = violation
