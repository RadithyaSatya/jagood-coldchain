from collections.abc import AsyncIterator

from ai_explain.explanation.prompt_builder import build_messages
from ai_explain.guardrails import validate_model_output
from ai_explain.llm.protocol import LLMGateway
from ai_explain.schemas import ExplanationRequest, ExplanationResponse


class ExplanationService:
    def __init__(self, llm: LLMGateway) -> None:
        self._llm = llm

    async def explain(self, request: ExplanationRequest) -> ExplanationResponse:
        content = await self._llm.complete(
            build_messages(request),
            max_tokens=request.max_output_tokens,
        )
        return ExplanationResponse(
            explanation=validate_model_output(content),
            language=request.language,
            source=request.source,
            model=self._llm.model,
        )

    async def stream(self, request: ExplanationRequest) -> AsyncIterator[str]:
        character_count = 0
        async for chunk in self._llm.stream(
            build_messages(request),
            max_tokens=request.max_output_tokens,
        ):
            character_count += len(chunk)
            if character_count > 8_000:
                return
            yield chunk

