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
