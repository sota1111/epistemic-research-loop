from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class StructuredLlm(Protocol):
    def generate(self, prompt: str, schema: type[T], context: dict[str, Any]) -> T: ...
