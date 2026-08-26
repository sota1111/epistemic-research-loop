from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class LlmUsage:
    model: str
    input_tokens: int
    output_tokens: int
    cache_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_tokens


class StructuredLlm(Protocol):
    def generate(self, prompt: str, schema: type[T], context: dict[str, Any]) -> T: ...
