import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ai_explain.config import Settings
from ai_explain.llm.errors import LLMServiceError, LLMTimeoutError
from ai_explain.llm.protocol import LLMMessage


class OpenAICompatibleLLM:
    """Async client for Ollama and vLLM OpenAI-compatible endpoints."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.model = settings.llm_model
        self._url = settings.chat_completions_url
        self._models_url = settings.models_url
        self._readiness_timeout = settings.llm_readiness_timeout_seconds
        self._temperature = settings.llm_temperature
        self._reasoning_effort = settings.llm_reasoning_effort
        self._client = client or httpx.AsyncClient(timeout=settings.llm_timeout_seconds)
        self._owns_client = client is None
        self._headers = (
            {"Authorization": f"Bearer {settings.llm_api_key}"}
            if settings.llm_api_key
            else {}
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def is_ready(self) -> bool:
        try:
            response = await self._client.get(
                self._models_url,
                headers=self._headers,
                timeout=self._readiness_timeout,
            )
            response.raise_for_status()
            models = response.json().get("data", [])
        except (httpx.HTTPError, ValueError, AttributeError):
            return False
        return any(isinstance(item, dict) and item.get("id") == self.model for item in models)

    async def complete(self, messages: list[LLMMessage], max_tokens: int) -> str:
        try:
            response = await self._client.post(
                self._url,
                headers=self._headers,
                json=self._payload(messages, max_tokens, stream=False),
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("inference request timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMServiceError("inference server request failed") from exc

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMServiceError("inference server returned an invalid response") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMServiceError("inference server returned empty content")
        return content.strip()

    async def stream(
        self, messages: list[LLMMessage], max_tokens: int
    ) -> AsyncIterator[str]:
        try:
            async with self._client.stream(
                "POST",
                self._url,
                headers=self._headers,
                json=self._payload(messages, max_tokens, stream=True),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    chunk = self._read_stream_chunk(data)
                    if chunk:
                        yield chunk
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("inference stream timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMServiceError("inference stream failed") from exc

    def _payload(
        self, messages: list[LLMMessage], max_tokens: int, *, stream: bool
    ) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "temperature": self._temperature,
            "reasoning_effort": self._reasoning_effort,
            "max_tokens": max_tokens,
            "stream": stream,
        }

    @staticmethod
    def _read_stream_chunk(data: str) -> str | None:
        try:
            body = json.loads(data)
            content = body["choices"][0]["delta"].get("content")
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMServiceError("inference server returned an invalid stream event") from exc
        return content if isinstance(content, str) else None
