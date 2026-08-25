import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from ai_explain.chat import ChatService
from ai_explain.explanation import ExplanationService
from ai_explain.llm.errors import LLMServiceError, LLMTimeoutError
from ai_explain.schemas import ChatRequest, ChatResponse, ExplanationRequest, ExplanationResponse

router = APIRouter()


@router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", tags=["health"])
async def readiness(request: Request) -> JSONResponse:
    llm_ready = await request.app.state.llm.is_ready()
    return JSONResponse(
        status_code=status.HTTP_200_OK if llm_ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ready" if llm_ready else "degraded",
            "llm": "ready" if llm_ready else "unavailable",
            "model": request.app.state.llm.model,
            "fallback_available": True,
        },
    )


@router.post("/v1/chat", response_model=ChatResponse, tags=["chat"])
async def create_chat_response(payload: ChatRequest, request: Request) -> ChatResponse:
    service = ChatService(request.app.state.llm)
    try:
        return await service.chat(payload)
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The inference server timed out.",
        ) from exc
    except LLMServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The inference server could not generate a chat response.",
        ) from exc


@router.post("/v1/chat/stream", response_class=StreamingResponse, tags=["chat"])
async def stream_chat_response(payload: ChatRequest, request: Request) -> StreamingResponse:
    service = ChatService(request.app.state.llm)
    prepared = await service.prepare_stream(payload)

    async def events() -> AsyncIterator[str]:
        yield _event(
            "metadata",
            {
                "language": payload.language.value,
                "intent": prepared.intent.value,
                "handled_by": prepared.handled_by,
                "model": prepared.model,
                "sources": prepared.sources,
            },
        )
        for chunk in prepared.chunks:
            yield _event("token", {"content": chunk})
        yield _event("done", {})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
