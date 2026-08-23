from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings shared by Ollama and vLLM deployments."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AI_EXPLAIN_",
        extra="ignore",
    )

    service_name: str = "Jagood ColdChain AI Explain"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str | None = None
    llm_model: str = "llama-jagood-ai-explain:latest"
    llm_reasoning_effort: Literal["none", "low", "medium", "high"] = "none"
    llm_timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    llm_readiness_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    llm_temperature: float = Field(default=0.2, ge=0, le=1)

    @property
    def chat_completions_url(self) -> str:
        return f"{self.llm_base_url.rstrip('/')}/chat/completions"

    @property
    def models_url(self) -> str:
        return f"{self.llm_base_url.rstrip('/')}/models"


@lru_cache
def get_settings() -> Settings:
    return Settings()
