"""Offline API test proving baseline and counterfactual use the real risk pipeline."""
import pytest
import requests
from fastapi.testclient import TestClient

from app.main import app
from app.services import enrichment_service, route_generator

client = TestClient(app)


class UnavailableORSClient:
    def directions(self, *args, **kwargs):
        raise requests.ConnectionError("ORS unavailable during offline test")


def test_delay_scenario_compares_model_outputs(monkeypatch):
    monkeypatch.setattr(route_generator, "_get_client", lambda: UnavailableORSClient())

    response = client.post(
        "/simulate-scenario",
        json={
            "baseline": {
                "shipment_id": "shipment-scenario-test",
                "origin": {"lat": -6.2088, "lon": 106.8456},
                "destination": {"lat": -7.2575, "lon": 112.7521},
                "commodity_type": "Salmon Segar",
                "departure_time": "2026-08-15T08:00:00Z",
                "ranking_preference": "risiko",
                "transport_mode_preference": "darat",
                "cold_chain_equipment": "reefer",
            },
            "changes": {"delay_hours": 12},
        },
    )

    assert response.status_code == 200
    body = response.json()
    baseline = body["baseline"]
    simulated = body["simulated"]

    assert body["scenario_id"].startswith("scn-")
    assert baseline["data_quality"] == "estimated"
    assert simulated["data_quality"] == "estimated"
    assert baseline["expected_delay_hours"] == 0
    assert simulated["expected_delay_hours"] == 12
    assert simulated["estimated_duration_hours"] == baseline["estimated_duration_hours"]
    assert body["risk_delta"] == pytest.approx(
        simulated["risk_probability"] - baseline["risk_probability"],
        abs=1e-6,
    )
    assert body["risk_delta"] > 0
    assert any(
        factor["factor"] == "expected_delay_hours"
        for factor in body["affected_factors"]
    )
    assert baseline["risk_explanation_factors"]
    assert simulated["risk_explanation_factors"]
    assert body["recommendation"]


def test_passive_cooling_disruption_produces_material_risk_delta(monkeypatch):
    monkeypatch.setattr(route_generator, "_get_client", lambda: UnavailableORSClient())

    async def hot_ambient_temperature(*args, **kwargs):
        return 35.0

    monkeypatch.setattr(enrichment_service, "fetch_ambient_temp_c", hot_ambient_temperature)

    response = client.post(
        "/simulate-scenario",
        json={
            "baseline": {
                "origin": {"lat": -6.2088, "lon": 106.8456},
                "destination": {"lat": -7.2575, "lon": 112.7521},
                "commodity_type": "Salmon Segar",
                "departure_time": "2026-08-15T08:00:00Z",
                "transport_mode_preference": "darat",
                "cold_chain_equipment": "reefer",
            },
            "changes": {
                "delay_hours": 12,
                "cold_chain_equipment": "pasif",
                "insulation_quality": "buruk",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["baseline"]["risk_level"] == "Low"
    assert body["simulated"]["risk_level"] in {"Medium", "High"}
    assert body["risk_delta"] >= 0.15
    assert body["simulated"]["max_cargo_temp_excess_c"] > 0
    assert "meningkat signifikan" in body["recommendation"]
