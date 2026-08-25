from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from ai_explain.schemas.explanation import (
    ExplanationSource,
    FactValue,
    Language,
    LongText,
    RiskLevel,
    ShortText,
)

ChatText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatIntent(StrEnum):
    GREETING = "greeting"
    ABOUT_JAGOOD = "about_jagood"
    FEATURE_INFORMATION = "feature_information"
    USAGE_GUIDE = "usage_guide"
    SHIPMENT_STATUS = "shipment_status"
    RISK_EXPLANATION = "risk_explanation"
    RECOMMENDATION = "recommendation"
    ROUTE_EXPLANATION = "route_explanation"
    SCENARIO_EXPLANATION = "scenario_explanation"
    GENERAL_COLD_CHAIN = "general_cold_chain"
    UNSUPPORTED = "unsupported"


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: ChatRole
    content: ChatText


class ShipmentContext(BaseModel):
    """Trusted calculation results supplied by the Jagood application."""

    model_config = ConfigDict(extra="forbid")

    shipment_id: ShortText | None = None
    source: ExplanationSource
    product: ShortText
    facts: dict[str, FactValue] = Field(default_factory=dict, max_length=30)
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    recommendation: LongText | None = None

    @field_validator("facts")
    @classmethod
    def validate_facts(cls, facts: dict[str, FactValue]) -> dict[str, FactValue]:
        normalized: dict[str, FactValue] = {}
        for raw_key, value in facts.items():
            key = raw_key.strip()
            if not key or len(key) > 100:
                raise ValueError("fact keys must contain between 1 and 100 characters")
            if isinstance(value, str):
                value = value.strip()
                if not value or len(value) > 500:
                    raise ValueError("text fact values must contain between 1 and 500 characters")
            normalized[key] = value
        return normalized


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Language = Language.INDONESIAN
    message: ChatText
    history: list[ChatMessage] = Field(default_factory=list, max_length=10)
    shipment_context: ShipmentContext | None = None
    max_output_tokens: int = Field(default=400, ge=64, le=800)


class ChatResponse(BaseModel):
    answer: str
    language: Language
    intent: ChatIntent
    handled_by: Literal["rule", "llm", "fallback"]
    model: str | None = None
    sources: list[str] = Field(default_factory=list)
