"""Tests for route selection + checkpoint check-ins (app/core/db.py's
shipment_checkpoints/weather_delay_stats tables, app/services/historical_baseline.py's
process_trip_weather_delay, app/routers/shipments.py's /select-route and /checkpoints).

Requires a reachable Postgres (`docker compose up -d postgres`). Skipped automatically
if the DB can't be reached -- same pattern as TestRealPersistence in test_shipment_store_e2e.py.
"""
import datetime as dt

import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core import db
from app.main import app
from app.services import enrichment_service, historical_baseline, route_generator

client = TestClient(app)


class UnavailableORSClient:
    def directions(self, *args, **kwargs):
        raise requests.ConnectionError("ORS unavailable during offline test")


async def _fixed_weathercode(client, lat, lon, target_time):
    return 61  # "Hujan Sedang" -> severity "hujan_lebat"


def _postgres_reachable() -> bool:
    try:
        with db.engine.connect():
            return True
    except OperationalError:
        return False


def _predict_route_payload(**overrides):
    payload = {
        "origin": {"lat": -6.9175, "lon": 107.6191},
        "destination": {"lat": -6.2088, "lon": 106.8456},
        "commodity_type": "Salmon Segar",
        "departure_time": "2026-08-15T08:00:00Z",
        "ranking_preference": "risiko",
        "transport_mode_preference": "darat",
    }
    payload.update(overrides)
    return payload


@pytest.mark.skipif(not _postgres_reachable(), reason="Postgres not reachable; run `docker compose up -d postgres`")
class TestCheckpoints:
    def test_select_route_rejects_unknown_route_id(self, monkeypatch):
        monkeypatch.setattr(route_generator, "_get_client", lambda: UnavailableORSClient())
        predict_response = client.post("/predict-route", json=_predict_route_payload())
        shipment_id = predict_response.json()["shipment_id"]

        response = client.post(f"/shipments/{shipment_id}/select-route", json={"route_id": "not-a-real-route"})
        assert response.status_code == 422

    def test_select_route_accepts_recommended_route_id(self, monkeypatch):
        monkeypatch.setattr(route_generator, "_get_client", lambda: UnavailableORSClient())
        predict_response = client.post("/predict-route", json=_predict_route_payload())
        body = predict_response.json()
        shipment_id = body["shipment_id"]
        route_id = body["recommended_route"]["route_id"]

        response = client.post(f"/shipments/{shipment_id}/select-route", json={"route_id": route_id})
        assert response.status_code == 200
        assert response.json()["selected_route_id"] == route_id

    def test_checkpoints_endpoint_404s_for_unknown_shipment(self):
        response = client.post(
            "/shipments/does-not-exist/checkpoints",
            json={"points": [{"lat": 0, "lon": 0, "recorded_at": "2026-08-15T08:00:00Z"}]},
        )
        assert response.status_code == 404

    def test_weather_delay_learns_from_slow_checkpoint_trips(self, monkeypatch):
        """The "learning" loop for weather delay: submit several trips whose checkpoints
        imply a very slow actual speed (well below any plausible nominal speed) under a
        fixed detected weather condition, report the outcome, and confirm a fresh
        prediction's weather_delay_data_quality progresses to 'learned' with a delay
        pulled toward the observed (large) value."""
        monkeypatch.setattr(route_generator, "_get_client", lambda: UnavailableORSClient())
        monkeypatch.setattr(enrichment_service, "fetch_weathercode", _fixed_weathercode)
        monkeypatch.setattr(historical_baseline, "fetch_weathercode", _fixed_weathercode)

        payload = _predict_route_payload()
        for _ in range(5):
            predict_response = client.post("/predict-route", json=payload)
            body = predict_response.json()
            shipment_id = body["shipment_id"]
            route_id = body["recommended_route"]["route_id"]

            select_response = client.post(f"/shipments/{shipment_id}/select-route", json={"route_id": route_id})
            assert select_response.status_code == 200

            # Two checkpoints 1km apart, 2 hours apart -- an extremely slow 0.5km/h actual
            # speed, guaranteed to register a large delay against any plausible nominal speed.
            start = dt.datetime(2026, 8, 15, 8, 0, tzinfo=dt.timezone.utc)
            checkpoint_response = client.post(
                f"/shipments/{shipment_id}/checkpoints",
                json={
                    "points": [
                        {"lat": -6.9175, "lon": 107.6191, "recorded_at": start.isoformat(), "checkpoint_label": "keberangkatan"},
                        {"lat": -6.9085, "lon": 107.6191, "recorded_at": (start + dt.timedelta(hours=2)).isoformat(), "checkpoint_label": "tiba"},
                    ]
                },
            )
            assert checkpoint_response.status_code == 202

            outcome_response = client.patch(
                f"/shipments/{shipment_id}/outcome",
                json={"actual_delay_hours": 0.1, "actual_damage_occurred": False},
            )
            assert outcome_response.status_code == 200

        learned_response = client.post("/predict-route", json=payload)
        recommended = learned_response.json()["recommended_route"]
        assert recommended["weather_delay_data_quality"] == "learned"
        assert recommended["weather_delay_hours"] > historical_baseline.WEATHER_DELAY_BOOTSTRAP_HOURS["hujan_lebat"]
