import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    route_planner_base_url: str = "http://localhost:8000"
    ai_explain_base_url: str = "http://localhost:8001"
    timeout_seconds: float = 300.0
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:3001")

    @classmethod
    def from_env(cls) -> "Settings":
        origins = tuple(
            origin.strip()
            for origin in os.getenv(
                "GATEWAY_CORS_ORIGINS",
                "http://localhost:3000,http://localhost:3001",
            ).split(",")
            if origin.strip()
        )
        return cls(
            route_planner_base_url=os.getenv(
                "ROUTE_PLANNER_BASE_URL", "http://localhost:8000"
            ).rstrip("/"),
            ai_explain_base_url=os.getenv("AI_EXPLAIN_BASE_URL", "http://localhost:8001").rstrip(
                "/"
            ),
            timeout_seconds=float(os.getenv("GATEWAY_TIMEOUT_SECONDS", "300")),
            cors_origins=origins,
        )
