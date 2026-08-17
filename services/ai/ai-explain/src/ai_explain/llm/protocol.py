from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: str
    content: str


class LLMGateway(Protocol):
    model: str

    async def is_ready(self) -> bool: ...

    async def complete(self, messages: list[LLMMessage], max_tokens: int) -> str: ...

    def stream(self, messages: list[LLMMessage], max_tokens: int) -> AsyncIterator[str]: ...
