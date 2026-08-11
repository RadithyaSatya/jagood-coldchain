from collections.abc import AsyncIterator

from ai_explain.chat.prompt_builder import build_chat_messages
from ai_explain.chat.retriever import KnowledgeChunk, retrieve_knowledge
from ai_explain.chat.rules import (
    classify_chat_intent,
    missing_knowledge_answer,
    rule_answer,
    uses_knowledge_base,
)
from ai_explain.guardrails import validate_model_output
from ai_explain.llm.protocol import LLMGateway
from ai_explain.schemas.chat import ChatIntent, ChatRequest, ChatResponse


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

        content = await self._llm.complete(
            build_chat_messages(request, intent, knowledge),
            max_tokens=request.max_output_tokens,
        )
        return ChatResponse(
            answer=validate_model_output(content),
            language=request.language,
            intent=intent,
            handled_by="llm",
            model=self._llm.model,
            sources=[chunk.citation for chunk in knowledge],
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        intent = classify_chat_intent(request)
        deterministic_answer = rule_answer(request, intent)
        if deterministic_answer is not None:
            yield deterministic_answer
            return


        knowledge = self.retrieve(request, intent)
        if uses_knowledge_base(intent) and not knowledge:
            yield missing_knowledge_answer(request)
            return

        character_count = 0
        async for chunk in self._llm.stream(
            build_chat_messages(request, intent, knowledge),
            max_tokens=request.max_output_tokens,
        ):
            character_count += len(chunk)
            if character_count > 8_000:
                return
            yield chunk

    @staticmethod
    def retrieve(request: ChatRequest, intent: ChatIntent) -> list[KnowledgeChunk]:
        if uses_knowledge_base(intent):
            return retrieve_knowledge(request.message)
        return []
