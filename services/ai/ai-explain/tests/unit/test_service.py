import pytest
from conftest import FakeLLM

from ai_explain.explanation import ExplanationService
from ai_explain.schemas import ExplanationRequest


@pytest.mark.asyncio
async def test_service_returns_model_metadata(explanation_payload: dict[str, object]) -> None:
    llm = FakeLLM("Pengiriman memiliki risiko sedang.")
    service = ExplanationService(llm)

    response = await service.explain(ExplanationRequest.model_validate(explanation_payload))

    assert response.explanation == "Pengiriman memiliki risiko sedang."
    assert response.language == "id"
    assert response.model == "fake-qwen"
    assert llm.calls[0][1] == 400
