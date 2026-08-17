from dataclasses import dataclass

from ai_explain.chat.fallback import deterministic_fallback_answer
from ai_explain.chat.prompt_builder import build_chat_messages
from ai_explain.chat.retriever import KnowledgeChunk, retrieve_knowledge
from ai_explain.chat.rules import (
    classify_chat_intent,
    missing_knowledge_answer,
    rule_answer,
    uses_knowledge_base,
)
from ai_explain.guardrails import validate_model_output
from ai_explain.llm.errors import LLMServiceError, LLMTimeoutError
from ai_explain.llm.protocol import LLMGateway
from ai_explain.schemas.chat import ChatIntent, ChatRequest, ChatResponse


@dataclass(frozen=True, slots=True)
class PreparedChatStream:
    chunks: list[str]
    intent: ChatIntent
    handled_by: str
    model: str | None
    sources: list[str]


class ChatService:
    def __init__(self, llm: LLMGateway) -> None:
        self._llm = llm

    async def chat(self, request: ChatRequest) -> ChatResponse:
        intent = classify_chat_intent(request)
        deterministic_answer = rule_answer(request, intent)
        if deterministic_answer is not None:
            return ChatResponse(
                answer=deterministic_answer,
                language=request.language,
                intent=intent,
                handled_by="rule",
            )

        knowledge = self.retrieve(request, intent)
        if uses_knowledge_base(intent) and not knowledge:
            return ChatResponse(
                answer=missing_knowledge_answer(request),
                language=request.language,
                intent=intent,
                handled_by="rule",
            )

        try:
            content = await self._llm.complete(
                build_chat_messages(request, intent, knowledge),
                max_tokens=request.max_output_tokens,
            )
            answer = validate_model_output(content)
        except (LLMTimeoutError, LLMServiceError):
            return ChatResponse(
                answer=deterministic_fallback_answer(request),
                language=request.language,
                intent=intent,
                handled_by="fallback",
            )
        return ChatResponse(
            answer=answer,
            language=request.language,
            intent=intent,
            handled_by="llm",
            model=self._llm.model,
            sources=[chunk.citation for chunk in knowledge],
        )

    async def prepare_stream(self, request: ChatRequest) -> PreparedChatStream:
        intent = classify_chat_intent(request)
        deterministic_answer = rule_answer(request, intent)
        if deterministic_answer is not None:
            return PreparedChatStream(
                chunks=[deterministic_answer],
                intent=intent,
                handled_by="rule",
                model=None,
                sources=[],
            )

        knowledge = self.retrieve(request, intent)
        if uses_knowledge_base(intent) and not knowledge:
            return PreparedChatStream(
                chunks=[missing_knowledge_answer(request)],
                intent=intent,
                handled_by="rule",
                model=None,
                sources=[],
            )

        chunks: list[str] = []
        try:
            async for chunk in self._llm.stream(
                build_chat_messages(request, intent, knowledge),
                max_tokens=request.max_output_tokens,
            ):
                chunks.append(chunk)
                if sum(len(item) for item in chunks) > 8_000:
                    raise LLMServiceError("model explanation exceeded the output limit")
            validate_model_output("".join(chunks))
        except (LLMTimeoutError, LLMServiceError):
            return PreparedChatStream(
                chunks=[deterministic_fallback_answer(request)],
                intent=intent,
                handled_by="fallback",
                model=None,
                sources=[],
            )

        return PreparedChatStream(
            chunks=chunks,
            intent=intent,
            handled_by="llm",
            model=self._llm.model,
            sources=[chunk.citation for chunk in knowledge],
        )

    @staticmethod
    def retrieve(request: ChatRequest, intent: ChatIntent) -> list[KnowledgeChunk]:
        if uses_knowledge_base(intent):
            return retrieve_knowledge(request.message)
        return []
