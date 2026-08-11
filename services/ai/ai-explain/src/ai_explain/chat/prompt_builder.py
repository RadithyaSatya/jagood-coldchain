import json
from importlib.resources import files

from ai_explain.chat.retriever import KnowledgeChunk, format_knowledge_context
from ai_explain.llm.protocol import LLMMessage
from ai_explain.schemas.chat import ChatIntent, ChatRequest

_LANGUAGE_NAMES = {"id": "Bahasa Indonesia", "en": "English"}


def build_chat_messages(
    request: ChatRequest,
    intent: ChatIntent,
    knowledge: list[KnowledgeChunk] | None = None,
) -> list[LLMMessage]:
    prompt_package = files("ai_explain.prompts")
    system_prompt = prompt_package.joinpath("chat_system.txt").read_text(encoding="utf-8").strip()

    history = [message.model_dump(mode="json") for message in request.history]
    context = (
        request.shipment_context.model_dump(mode="json", exclude_none=True)
        if request.shipment_context is not None
        else None
    )
    task = {
        "output_language": _LANGUAGE_NAMES[request.language.value],
        "allowed_intent": intent.value,
        "conversation_history": history,
        "shipment_context": context,
        "knowledge_context": format_knowledge_context(knowledge or []),
        "current_question": request.message,
    }

    return [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(
            role="user",
            content=(
                "Answer the current question using only the allowed scope and supplied data.\n\n"
                f"<chat_input>\n{json.dumps(task, ensure_ascii=False, indent=2)}\n</chat_input>"
            ),
        ),
    ]
