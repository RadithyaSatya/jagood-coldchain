"""Offline proof that an uncached BMKG outage does not break maritime planning."""

import httpx
import requests
from fastapi.testclient import TestClient

from app.main import app
from app.services import enrichment_service, route_generator

client = TestClient(app)


class UnavailableORSClient:
    def directions(self, *args, **kwargs):
        raise requests.ConnectionError("ORS intentionally unavailable")


def test_maritime_route_survives_bmkg_network_failure(monkeypatch):
    monkeypatch.setattr(route_generator, "_get_client", lambda: UnavailableORSClient())

    async def unavailable_bmkg(*args, **kwargs):
        request = httpx.Request("GET", "https://example.invalid/bmkg")
        raise httpx.ConnectError("BMKG intentionally unavailable", request=request)

    monkeypatch.setattr(enrichment_service, "get_sea_leg_conditions", unavailable_bmkg)
    monkeypatch.setattr(enrichment_service, "get_port_conditions", unavailable_bmkg)

    response = client.post(
        "/predict-route",
        json={
            "shipment_id": "shipment-bmkg-offline",
            "origin": {"lat": -6.2088, "lon": 106.8456},
            "destination": {"lat": -5.1477, "lon": 119.4327},
            "commodity_type": "Salmon Segar",
            "departure_time": "2026-08-15T08:00:00Z",
            "transport_mode_preference": "kombinasi",
            "cold_chain_equipment": "reefer",
        },
    )

    assert response.status_code == 200
    route = response.json()["recommended_route"]
    assert route["transport_mode"] == "kombinasi"
    assert route["environmental_data_quality"] == "fallback"
    assert route["cargo_temperature_data_quality"] == "assumed"
    assert route["wave_height_m"] == 0
    assert route["port_ambient_temp_c"] == 30
    assert route["risk_explanation_factors"]
