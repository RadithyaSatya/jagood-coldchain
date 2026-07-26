from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ai_explain.api.routes import router
from ai_explain.config import Settings, get_settings
from ai_explain.llm import LLMGateway, OpenAICompatibleLLM


def create_app(
    *,
    settings: Settings | None = None,
    llm: LLMGateway | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned_llm: OpenAICompatibleLLM | None = None
        if llm is None:
            owned_llm = OpenAICompatibleLLM(resolved_settings)
            app.state.llm = owned_llm
        else:
            app.state.llm = llm
        yield
        if owned_llm is not None:
            await owned_llm.close()

    application = FastAPI(
        title=resolved_settings.service_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    if llm is not None:
        application.state.llm = llm
    application.include_router(router)
    return application


app = create_app()

