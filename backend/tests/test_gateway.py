import json

import httpx
import pytest

from app.config import Settings
from app.main import create_app


class AsyncBytes(httpx.AsyncByteStream):
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def __aiter__(self):
        yield self.content


def _route() -> dict:
    return {
        "route_id": "darat-1",
        "transport_mode": "darat",
        "distance_km": 120.0,
        "estimated_duration_hours": 3.0,
        "expected_delay_hours": 0.42,
        "estimated_arrival": "2026-08-23T13:25:00Z",
        "risk_level": "Medium",
        "risk_probability": 0.42,
        "confidence_score": 0.81,
        "trigger_reason": None,
        "data_quality": "live",
        "environmental_data_quality": "forecast",
        "wave_category": "Tenang",
        "wave_height_m": 0.0,
        "wind_speed_kmh": 15.0,
        "weather_condition": "Hujan Sedang",
        "port_status_flag": 1,
        "port_ambient_temp_c": 30.0,
        "historical_delay_avg_hours": 3.2,
        "historical_damage_rate": 0.1,
        "cold_chain_equipment": "reefer",
        "commodity_temp_ideal_c": 2.0,
        "max_cargo_temp_excess_c": 0.0,
        "cargo_temp_profile": [],
        "cargo_temperature_data_quality": "assumed",
        "remaining_shelf_life_hours": 44.58,
        "remaining_shelf_life_pct": 92.9,
        "quality_status": "Baik",
        "geometry": [],
        "risk_hotspot": None,
        "port_pair": None,
        "risk_explanation_summary": "Cuaca meningkatkan risiko.",
        "risk_explanation_factors": [
            {"factor": "Kondisi cuaca", "effect": "menaikkan", "impact": 0.4}
        ],
    }


def _settings() -> Settings:
    return Settings(
        route_planner_base_url="http://planner",
        ai_explain_base_url="http://explain",
        timeout_seconds=5,
        cors_origins=("http://localhost:3000",),
    )


async def _gateway_client(handler) -> tuple[httpx.AsyncClient, httpx.AsyncClient]:
    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = create_app(settings=_settings(), upstream_client=upstream)
    gateway = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://gateway",
    )
    return gateway, upstream


@pytest.mark.asyncio
async def test_health_and_readiness_report_both_internal_services() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(200, json={"status": "ok"})

    gateway, upstream = await _gateway_client(handler)
    async with gateway, upstream:
        health = await gateway.get("/health")
        readiness = await gateway.get("/ready")

    assert health.json() == {"status": "ok", "service": "jagood-platform-gateway"}
    assert readiness.status_code == 200
    assert readiness.json()["services"] == {
        "route_planner": "ready",
        "ai_explain": "ready",
    }


@pytest.mark.asyncio
async def test_route_planner_proxy_preserves_query_and_response_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "planner"
        assert request.url.path == "/shipments"
        assert request.url.params["limit"] == "5"
        return httpx.Response(200, json={"items": [], "total": 0, "limit": 5, "offset": 0})

    gateway, upstream = await _gateway_client(handler)
    async with gateway, upstream:
        response = await gateway.get("/shipments", params={"limit": 5})

    assert response.status_code == 200
    assert response.json()["limit"] == 5


@pytest.mark.asyncio
async def test_ai_stream_is_exposed_through_the_gateway() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "explain"
        assert request.url.path == "/v1/chat/stream"
        return httpx.Response(
            200,
            stream=AsyncBytes(b'event: token\ndata: {"content": "aman"}\n\n'),
            headers={"content-type": "text/event-stream"},
        )

    gateway, upstream = await _gateway_client(handler)
    async with gateway, upstream:
        response = await gateway.post("/v1/chat/stream", json={"message": "Jelaskan"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: token" in response.text


@pytest.mark.asyncio
async def test_final_recommendation_is_orchestrated_by_fastapi_gateway() -> None:
    received_payload: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "planner"
        assert request.url.path == "/predict-route"
        received_payload.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "shipment_id": "shipment-1",
                "recommended_route": _route(),
                "alternative_routes": [],
            },
        )

    gateway, upstream = await _gateway_client(handler)
    shipment = {
        "origin": {"lat": -6.2, "lon": 106.8},
        "destination": {"lat": -6.9, "lon": 107.6},
        "commodity_type": "Salmon Segar",
        "departure_time": "2026-08-23T10:00:00Z",
        "transport_mode_preference": "darat",
        "cold_chain_equipment": "reefer",
        "insulation_quality": "sedang",
        "ranking_preference": "risiko",
    }
    async with gateway, upstream:
        response = await gateway.post("/final-recommendation", json={"shipment": shipment})

    assert response.status_code == 200
    body = response.json()
    assert received_payload == shipment
    assert body["route_plan"]["shipment_id"] == "shipment-1"
    assert body["final_recommendation"]["route_id"] == "darat-1"
    assert body["final_recommendation"]["provenance"]["environment"] == ("Open-Meteo cuaca darat")
    assert body["explanation_context"]["source"] == "smart_route_planner"


@pytest.mark.asyncio
async def test_final_recommendation_maps_internal_server_error_to_bad_gateway() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "planner failed"})

    gateway, upstream = await _gateway_client(handler)
    async with gateway, upstream:
        response = await gateway.post(
            "/final-recommendation",
            json={"shipment": {"commodity_type": "Salmon Segar"}},
        )

    assert response.status_code == 502
    assert response.json() == {"detail": "planner failed"}
