"""Offline end-to-end test of POST /predict-route through the real pipeline.

Only the OpenRouteService boundary is replaced with a client that raises a
transport error. The request still exercises FastAPI, candidate generation,
the documented haversine fallback, enrichment, model inference, SHAP, ranking,
and response serialization without relying on DNS, API keys, or a cassette.
"""
import requests
from fastapi.testclient import TestClient

from app.main import app
from app.services import enrichment_service, route_generator

client = TestClient(app)


class UnavailableORSClient:
    def directions(self, *args, **kwargs):
        raise requests.ConnectionError("ORS unavailable during offline test")


async def _unavailable_weathercode(*args, **kwargs):
    return None


def test_predict_route_end_to_end_jakarta_surabaya(monkeypatch):
    monkeypatch.setattr(route_generator, "_get_client", lambda: UnavailableORSClient())
    # Forces the LAND_DEFAULT_CONDITIONS fallback (weather_data_quality="configured")
    # instead of a live Open-Meteo call, so environmental_data_quality/weather_delay_hours
    # below stay deterministic regardless of real-world weather at test time.
    monkeypatch.setattr(enrichment_service, "fetch_weathercode", _unavailable_weathercode)

    response = client.post(
        "/predict-route",
        json={
            "origin": {"lat": -6.2088, "lon": 106.8456},
            "destination": {"lat": -7.2575, "lon": 112.7521},
            "commodity_type": "Salmon Segar",
            "departure_time": "2026-08-15T08:00:00Z",
            "ranking_preference": "risiko",
            "transport_mode_preference": "darat",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["shipment_id"]
    recommended = body["recommended_route"]
    assert recommended["risk_level"] in {"Low", "Medium", "High"}
    assert recommended["transport_mode"] in {"darat", "laut", "kombinasi"}
    assert recommended["distance_km"] > 0
    assert recommended["data_quality"] == "estimated"
    assert recommended["environmental_data_quality"] == "configured"
    assert recommended["cargo_temperature_data_quality"] == "assumed"
    assert "risk_explanation_summary" in recommended

    assert recommended["remaining_shelf_life_hours"] >= 0
    assert 0 <= recommended["remaining_shelf_life_pct"] <= 100
    assert recommended["quality_status"] in {"Baik", "Menurun", "Kritis"}

    assert recommended["weather_delay_hours"] >= 0
    assert recommended["weather_delay_data_quality"] in {"bootstrap", "learned"}

    # FR-5: the recommended route must be at least as low-risk as every
    # alternative -- i.e. actually sorted risk-first, not just "some response".
    all_routes = [recommended, *body["alternative_routes"]]
    risk_order = ["Low", "Medium", "High"]
    assert risk_order.index(recommended["risk_level"]) == min(
        risk_order.index(r["risk_level"]) for r in all_routes
    )
