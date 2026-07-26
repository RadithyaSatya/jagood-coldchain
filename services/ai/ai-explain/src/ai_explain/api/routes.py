import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from ai_explain.explanation import ExplanationService
from ai_explain.llm.errors import LLMServiceError, LLMTimeoutError
from ai_explain.schemas import ExplanationRequest, ExplanationResponse

router = APIRouter()


@router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/v1/explanations",
    response_model=ExplanationResponse,
    tags=["explanations"],
)
async def create_explanation(
    payload: ExplanationRequest,
    request: Request,
) -> ExplanationResponse:
    service = ExplanationService(request.app.state.llm)
    try:
        return await service.explain(payload)
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The inference server timed out.",
        ) from exc
    except LLMServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The inference server could not generate an explanation.",
        ) from exc


@router.post(
    "/v1/explanations/stream",
    response_class=StreamingResponse,
    tags=["explanations"],
)
async def stream_explanation(
    payload: ExplanationRequest,
    request: Request,
) -> StreamingResponse:
    service = ExplanationService(request.app.state.llm)

    async def events() -> AsyncIterator[str]:
        yield _event(
            "metadata",
            {
                "language": payload.language.value,
                "source": payload.source.value,
                "model": request.app.state.llm.model,
            },
        )
        try:
            async for chunk in service.stream(payload):
                yield _event("token", {"content": chunk})
        except (LLMTimeoutError, LLMServiceError):
            yield _event("error", {"message": "Explanation generation failed."})
            return
        yield _event("done", {})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _event(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

