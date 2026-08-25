import pytest
from conftest import FakeLLM

from ai_explain.chat import ChatService
from ai_explain.llm.errors import LLMTimeoutError
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
        "JaGOOD (Jaga Food) adalah prototipe decision-support"
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


@pytest.mark.asyncio
async def test_contextual_chat_falls_back_to_structured_facts_on_llm_timeout() -> None:
    llm = FakeLLM(error=LLMTimeoutError("offline"))
    service = ChatService(llm)
    request = ChatRequest.model_validate(
        {
            "message": "Jelaskan dampak skenario ini",
            "shipment_context": {
                "shipment_id": "SHP-123",
                "source": "scenario_simulator",
                "product": "Salmon Segar",
                "facts": {
                    "baseline_risk": "1.00%",
                    "simulated_risk": "49.92%",
                    "risk_delta": "48.92 poin persentase",
                },
                "risk_level": "medium",
                "recommendation": "Gunakan reefer aktif.",
            },
        }
    )

    response = await service.chat(request)

    assert response.handled_by == "rule"
    assert response.model is None
    assert "49.92%" in response.answer
    assert "48.92 poin persentase" in response.answer
    assert "Gunakan reefer aktif." in response.answer
    assert llm.calls == []


@pytest.mark.asyncio
async def test_fallback_prioritizes_quality_and_data_provenance_facts() -> None:
    llm = FakeLLM(error=LLMTimeoutError("offline"))
    service = ChatService(llm)
    request = ChatRequest.model_validate(
        {
            "message": "Jelaskan rekomendasi rute ini",
            "shipment_context": {
                "shipment_id": "SHP-QUALITY-1",
                "source": "smart_route_planner",
                "product": "Salmon Segar",
                "facts": {
                    "route_id": "darat-1",
                    "transport_mode": "darat",
                    "distance": "780 km",
                    "travel_duration": "14 jam",
                    "model_confidence": "91%",
                    "weather_condition": "Berawan",
                    "risk_probability": "18.00%",
                    "expected_delay": "2.0 jam",
                    "estimated_remaining_shelf_life": "44.0 jam",
                    "quality_retention_proxy": "61.1%",
                    "environmental_data_source": "Default darat terkonfigurasi",
                },
                "risk_level": "low",
            },
        }
    )

    response = await service.chat(request)

    assert response.handled_by == "fallback"
    assert "18.00%" in response.answer
    assert "44.0 jam" in response.answer
    assert "61.1%" in response.answer
    assert "Default darat terkonfigurasi" in response.answer


@pytest.mark.asyncio
async def test_awkward_model_output_uses_safe_friendly_fallback() -> None:
    llm = FakeLLM(
        "Data sistem berupa reefer dan sistem berupa Cerah. Faktor utama berupa Reiker."
    )
    service = ChatService(llm)
    request = ChatRequest.model_validate(
        {
            "message": "Jelaskan risiko rute ini",
            "shipment_context": {
                "source": "smart_route_planner",
                "product": "Salmon Segar",
                "facts": {
                    "expected_delay": "0.0 jam",
                    "cold_chain_equipment": "pendingin aktif (reefer)",
                    "weather_condition": "Cerah",
                    "environmental_data_source": (
                        "data BMKG yang dilengkapi estimasi cadangan"
                    ),
                },
                "risk_level": "low",
            },
        }
    )

    response = await service.chat(request)

    assert response.handled_by == "fallback"
    assert "Salmon Segar" in response.answer
    assert "0.0 jam" in response.answer
    assert "pendingin aktif (reefer)" in response.answer
    assert "data BMKG yang dilengkapi estimasi cadangan" in response.answer
    assert "sistem berupa" not in response.answer.casefold()
    assert "Reiker" not in response.answer


@pytest.mark.asyncio
async def test_stream_falls_back_without_emitting_partial_llm_output() -> None:
    llm = FakeLLM(error=LLMTimeoutError("offline"))
    service = ChatService(llm)
    request = ChatRequest.model_validate(
        {
            "message": "Jelaskan risiko rute ini",
            "shipment_context": {
                "source": "smart_route_planner",
                "product": "Tuna Segar",
                "facts": {"risk_probability": "35.00%"},
                "risk_level": "medium",
            },
        }
    )

    prepared = await service.prepare_stream(request)

    assert prepared.handled_by == "fallback"
    assert prepared.model is None
    assert len(prepared.chunks) == 1
    assert "35.00%" in prepared.chunks[0]
