import json

import httpx
import pytest

from ai_explain.config import Settings
from ai_explain.llm import LLMMessage, OpenAICompatibleLLM


@pytest.mark.asyncio
async def test_complete_uses_openai_compatible_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == "http://inference.test/v1/chat/completions"
        assert payload["model"] == "Qwen/Qwen3-4B-Instruct-2507"
        assert payload["stream"] is False
        assert payload["max_tokens"] == 300
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "A supported explanation."}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    llm = OpenAICompatibleLLM(
        Settings(
            llm_base_url="http://inference.test/v1",
            llm_model="Qwen/Qwen3-4B-Instruct-2507",
        ),
        client=client,
    )

    result = await llm.complete([LLMMessage(role="user", content="Explain")], 300)

    assert result == "A supported explanation."
    await client.aclose()


@pytest.mark.asyncio
async def test_stream_reads_openai_compatible_sse_events() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is True
        content = (
            'data: {"choices":[{"delta":{"content":"Cold "}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"chain"}}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, text=content, headers={"content-type": "text/event-stream"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    llm = OpenAICompatibleLLM(Settings(), client=client)

    chunks = [
        chunk
        async for chunk in llm.stream(
            [LLMMessage(role="user", content="Explain")],
            300,
        )
    ]

    assert chunks == ["Cold ", "chain"]
    await client.aclose()

