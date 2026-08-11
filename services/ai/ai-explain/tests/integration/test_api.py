import httpx
import pytest
from conftest import FakeLLM

from ai_explain.main import create_app


@pytest.mark.asyncio
async def test_create_explanation_endpoint(
    fake_llm: FakeLLM,
    explanation_payload: dict[str, object],
) -> None:
    app = create_app(llm=fake_llm)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/explanations", json=explanation_payload)

    assert response.status_code == 200
    assert response.json() == {
        "explanation": "The shipment is at medium risk.",
        "language": "id",
        "source": "transportation_monitoring",
        "model": "fake-qwen",
    }


@pytest.mark.asyncio
async def test_stream_explanation_endpoint(
    fake_llm: FakeLLM,
    explanation_payload: dict[str, object],
) -> None:
    app = create_app(llm=fake_llm)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/explanations/stream", json=explanation_payload)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: metadata" in response.text
    assert 'data: {"content": "Risiko "}' in response.text
    assert "event: done" in response.text


@pytest.mark.asyncio
async def test_rejects_unstructured_or_unknown_fields(
    fake_llm: FakeLLM,
    explanation_payload: dict[str, object],
) -> None:
    explanation_payload["prompt"] = "Make up a safe route"
    app = create_app(llm=fake_llm)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/explanations", json=explanation_payload)

    assert response.status_code == 422
    assert fake_llm.calls == []


@pytest.mark.asyncio
async def test_chat_endpoint_uses_rule_for_unsupported_topic(fake_llm: FakeLLM) -> None:
    app = create_app(llm=fake_llm)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat",
            json={"language": "id", "message": "Siapa presiden Indonesia?"},
        )

    assert response.status_code == 200
    assert response.json()["intent"] == "unsupported"
    assert response.json()["handled_by"] == "rule"
    assert response.json()["model"] is None
    assert fake_llm.calls == []


@pytest.mark.asyncio
async def test_chat_endpoint_calls_llm_for_allowed_question(fake_llm: FakeLLM) -> None:
    fake_llm.response = "Suhu saat ini -16 °C dengan risiko sedang."
    app = create_app(llm=fake_llm)
    transport = httpx.ASGITransport(app=app)
    payload = {
        "language": "id",
        "message": "Jelaskan risiko pengiriman ini",
        "shipment_context": {
            "shipment_id": "SHP-123",
            "source": "transportation_monitoring",
            "product": "Frozen tuna",
            "facts": {"current_temperature": "-16 °C"},
            "risk_level": "medium",
        },
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/chat", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Suhu saat ini -16 °C dengan risiko sedang.",
        "language": "id",
        "intent": "risk_explanation",
        "handled_by": "llm",
        "model": "fake-qwen",
        "sources": [],
    }


@pytest.mark.asyncio
async def test_chat_endpoint_retrieves_jagood_markdown(fake_llm: FakeLLM) -> None:
    fake_llm.response = "Jagood memiliki fitur Smart Route Planner."
    app = create_app(llm=fake_llm)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat",
            json={"language": "id", "message": "Apa fungsi Smart Route Planner?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "feature_information"
    assert body["handled_by"] == "llm"
    assert "ai-modules.md#smart-route-planner" in body["sources"]
    assert "Best Route" in fake_llm.calls[0][0][1].content


@pytest.mark.asyncio
async def test_chat_stream_can_return_rule_response(fake_llm: FakeLLM) -> None:
    app = create_app(llm=fake_llm)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/chat/stream", json={"message": "Buatkan puisi"})

    assert response.status_code == 200
    assert '"intent": "unsupported"' in response.text
    assert '"handled_by": "rule"' in response.text
    assert "event: done" in response.text
    assert fake_llm.calls == []
