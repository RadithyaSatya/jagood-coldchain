from ai_explain.llm.errors import LLMServiceError

MAX_EXPLANATION_CHARACTERS = 8_000


def validate_model_output(content: str) -> str:
    normalized = content.strip()
    if not normalized:
        raise LLMServiceError("model returned an empty explanation")
    if len(normalized) > MAX_EXPLANATION_CHARACTERS:
        raise LLMServiceError("model explanation exceeded the output limit")
    return normalized

