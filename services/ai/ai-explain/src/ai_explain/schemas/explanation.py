from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
FactValue = str | int | float | bool


class Language(StrEnum):
    INDONESIAN = "id"
    ENGLISH = "en"


class ExplanationSource(StrEnum):
    SMART_ROUTE_PLANNER = "smart_route_planner"
    SCENARIO_SIMULATOR = "scenario_simulator"
    TRANSPORTATION_MONITORING = "transportation_monitoring"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ExplanationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Language
    source: ExplanationSource
    product: ShortText
    facts: dict[str, FactValue] = Field(min_length=1, max_length=30)
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    recommendation: LongText | None = None
    max_output_tokens: int = Field(default=400, ge=64, le=800)

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


class ExplanationResponse(BaseModel):
    explanation: str
    language: Language
    source: ExplanationSource
    model: str

