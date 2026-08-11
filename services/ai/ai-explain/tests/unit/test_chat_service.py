import pytest
from conftest import FakeLLM

from ai_explain.chat import ChatService
from ai_explain.schemas import ChatRequest


@pytest.mark.asyncio
async def test_rule_response_does_not_call_llm() -> None:
    llm = FakeLLM()
    service = ChatService(llm)

    response = await service.chat(ChatRequest(message="Buatkan saya puisi"))

    assert response.handled_by == "rule"
    assert response.intent == "unsupported"
    assert response.model is None
    assert llm.calls == []


@pytest.mark.asyncio
async def test_in_scope_response_uses_shipment_context() -> None:
    llm = FakeLLM("Risiko sedang karena suhu tercatat -16 °C.")
    service = ChatService(llm)
    request = ChatRequest.model_validate(
        {
            "message": "Kenapa risikonya sedang?",
            "shipment_context": {
                "shipment_id": "SHP-123",
                "source": "transportation_monitoring",
                "product": "Frozen tuna",
                "facts": {"temperature": "-16 °C"},
                "risk_level": "medium",
            },
        }
    )

    response = await service.chat(request)

    assert response.handled_by == "llm"
    assert response.intent == "risk_explanation"
    assert response.model == "fake-qwen"
    assert '"shipment_id": "SHP-123"' in llm.calls[0][0][1].content
    assert '"temperature": "-16 °C"' in llm.calls[0][0][1].content


@pytest.mark.asyncio
async def test_greeting_is_answered_without_llm() -> None:
    llm = FakeLLM()
    service = ChatService(llm)

    response = await service.chat(ChatRequest(message="Halo"))

    assert response.intent == "greeting"
    assert response.handled_by == "rule"
    assert llm.calls == []


@pytest.mark.asyncio
async def test_jagood_question_uses_markdown_knowledge() -> None:
    llm = FakeLLM("Jagood membantu pengiriman cold-chain makanan.")
    service = ChatService(llm)

    response = await service.chat(ChatRequest(message="Jagood itu apa?"))

    assert response.intent == "about_jagood"
    assert response.handled_by == "llm"
    assert "overview.md#jagood" in response.sources
    assert '"knowledge_context"' in llm.calls[0][0][1].content
    assert (
        "JaGOOD (Jaga Food) adalah platform AI Decision Intelligence"
        in llm.calls[0][0][1].content
    )


@pytest.mark.asyncio
async def test_missing_knowledge_returns_safe_message(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AI_EXPLAIN_KNOWLEDGE_DIR", str(tmp_path / "missing"))
    llm = FakeLLM()
    service = ChatService(llm)

    response = await service.chat(ChatRequest(message="Jagood itu apa?"))

    assert response.handled_by == "rule"
    assert response.answer == "Informasi tersebut belum tersedia dalam dokumentasi Jagood."
    assert response.sources == []
    assert llm.calls == []
