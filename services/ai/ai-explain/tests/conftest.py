from collections.abc import AsyncIterator

import pytest

from ai_explain.llm import LLMMessage


class FakeLLM:
    model = "fake-qwen"

    def __init__(self, response: str = "The shipment is at medium risk.") -> None:
        self.response = response
        self.calls: list[tuple[list[LLMMessage], int]] = []

    async def complete(self, messages: list[LLMMessage], max_tokens: int) -> str:
        self.calls.append((messages, max_tokens))
        return self.response

    async def stream(
        self, messages: list[LLMMessage], max_tokens: int
    ) -> AsyncIterator[str]:
        self.calls.append((messages, max_tokens))
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

