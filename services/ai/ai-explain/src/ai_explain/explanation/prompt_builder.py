import json
from importlib.resources import files

from ai_explain.llm.protocol import LLMMessage
from ai_explain.schemas import ExplanationRequest, Language

LANGUAGE_NAMES = {
    Language.INDONESIAN: "Bahasa Indonesia",
    Language.ENGLISH: "English",
}


def build_messages(request: ExplanationRequest) -> list[LLMMessage]:
    prompt_package = files("ai_explain.prompts")
    system_prompt = prompt_package.joinpath("system.txt").read_text(encoding="utf-8").strip()
    task_template = prompt_package.joinpath("explanation.txt").read_text(encoding="utf-8")

    payload = request.model_dump(
        mode="json",
        exclude={"language", "max_output_tokens"},
        exclude_none=True,
    )
    task_prompt = task_template.format(
        language_name=LANGUAGE_NAMES[request.language],
        source=request.source.value,
        payload=json.dumps(payload, ensure_ascii=False, indent=2),
    ).strip()

    return [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=task_prompt),
    ]

