from collections.abc import AsyncIterator

import pytest

from ai_explain.llm import LLMMessage


class FakeLLM:
    model = "fake-qwen"

    def __init__(
        self,
        response: str = "The shipment is at medium risk.",
        *,
        ready: bool = True,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.ready = ready
        self.error = error
        self.calls: list[tuple[list[LLMMessage], int]] = []

    async def is_ready(self) -> bool:
        return self.ready

    async def complete(self, messages: list[LLMMessage], max_tokens: int) -> str:
        self.calls.append((messages, max_tokens))
        if self.error is not None:
            raise self.error
        return self.response

    async def stream(
        self, messages: list[LLMMessage], max_tokens: int
    ) -> AsyncIterator[str]:
        self.calls.append((messages, max_tokens))
        if self.error is not None:
            raise self.error
        for chunk in ("Risiko ", "pengiriman sedang."):
            yield chunk


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def explanation_payload() -> dict[str, object]:
    return {
        "language": "id",
        "source": "transportation_monitoring",
        "product": "Frozen tuna",
        "facts": {
            "current_temperature": "-16 °C",
            "target_temperature": "-18 °C",
            "delay_minutes": 20,
        },
        "risk_level": "medium",
        "recommendation": "Inspect the cooling unit at the next checkpoint.",
    }
