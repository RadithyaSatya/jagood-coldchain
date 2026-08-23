"""Tests for the shipment_records persistence store (app/core/db.py,
app/services/shipment_service.py, app/routers/shipments.py).

Two tiers:
1. No-DB tests (run in default CI, no Postgres available): prove the
   best-effort write in POST /predict-route never breaks the prediction
   response, even when DATABASE_URL is unreachable.
2. Real persistence tests: require a reachable Postgres (`docker compose up
   -d postgres`). Skipped automatically if the DB can't be reached.
"""
import requests
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core import db
from app.main import app
from app.services import historical_baseline, route_generator

client = TestClient(app)


class UnavailableORSClient:
    def directions(self, *args, **kwargs):
        raise requests.ConnectionError("ORS unavailable during offline test")


def _predict_route_payload(**overrides):
    payload = {
        "origin": {"lat": -6.2088, "lon": 106.8456},
        "destination": {"lat": -7.2575, "lon": 112.7521},
        "commodity_type": "Salmon Segar",
        "departure_time": "2026-08-15T08:00:00Z",
        "ranking_preference": "risiko",
        "transport_mode_preference": "darat",
    }
    payload.update(overrides)
    return payload


def _postgres_reachable() -> bool:
    try:
        with db.engine.connect():
            return True
    except OperationalError:
        return False


def test_predict_route_survives_unreachable_database(monkeypatch):
    """Proves the design decision: a DB outage must never fail /predict-route."""
    monkeypatch.setattr(route_generator, "_get_client", lambda: UnavailableORSClient())
    monkeypatch.setattr(
        db,
        "insert_shipment_record",
        lambda record: (_ for _ in ()).throw(OperationalError("insert", {}, Exception("no db"))),
    )

    response = client.post("/predict-route", json=_predict_route_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["shipment_id"]
    assert body["recommended_route"]["risk_level"] in {"Low", "Medium", "High"}


def test_simulate_scenario_never_calls_shipment_persistence(monkeypatch):
    monkeypatch.setattr(route_generator, "_get_client", lambda: UnavailableORSClient())
    calls = []
    monkeypatch.setattr(db, "insert_shipment_record", lambda record: calls.append(record))

    response = client.post(
        "/simulate-scenario",
        json={
            "baseline": {
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
    assert calls == []


def test_predict_route_survives_unreachable_corridor_stats(monkeypatch):
    """Proves the blend lookup in estimate_historical_baseline() is best-effort too."""
    monkeypatch.setattr(route_generator, "_get_client", lambda: UnavailableORSClient())
    monkeypatch.setattr(
        db,
        "get_corridor_stats",
        lambda transport_mode, distance_bucket_km: (_ for _ in ()).throw(
            OperationalError("select", {}, Exception("no db"))
        ),
    )

    response = client.post("/predict-route", json=_predict_route_payload())

    assert response.status_code == 200
    assert response.json()["recommended_route"]["historical_delay_avg_hours"] > 0


def test_predict_route_survives_unreachable_weather_delay_stats(monkeypatch):
    """Proves the blend lookup in estimate_weather_delay_hours() is best-effort too."""
    monkeypatch.setattr(route_generator, "_get_client", lambda: UnavailableORSClient())
    monkeypatch.setattr(
        db,
        "get_weather_delay_stats",
        lambda transport_mode, weather_severity: (_ for _ in ()).throw(
            OperationalError("select", {}, Exception("no db"))
        ),
    )

    response = client.post("/predict-route", json=_predict_route_payload())

    assert response.status_code == 200
    assert response.json()["recommended_route"]["weather_delay_data_quality"] == "bootstrap"


def test_blend_weight_ramps_from_zero_to_full_trust():
    assert historical_baseline._blend_weight(0) == 0.0
    assert historical_baseline._blend_weight(historical_baseline.MIN_SAMPLES_FOR_BLEND - 1) == 0.0
    assert historical_baseline._blend_weight(historical_baseline.MIN_SAMPLES_FOR_BLEND) == 0.0
    mid = (historical_baseline.MIN_SAMPLES_FOR_BLEND + historical_baseline.FULL_TRUST_SAMPLES) // 2
    assert 0.0 < historical_baseline._blend_weight(mid) < 1.0
    assert historical_baseline._blend_weight(historical_baseline.FULL_TRUST_SAMPLES) == 1.0
    assert historical_baseline._blend_weight(historical_baseline.FULL_TRUST_SAMPLES + 100) == 1.0


def test_shipment_not_found_returns_404(monkeypatch):
    monkeypatch.setattr(db, "select_shipment_by_id", lambda shipment_id: None)
    response = client.get("/shipments/does-not-exist")
    assert response.status_code == 404


def test_report_outcome_not_found_returns_404(monkeypatch):
    monkeypatch.setattr(db, "update_shipment_outcome", lambda shipment_id, outcome: None)
    response = client.patch(
        "/shipments/does-not-exist/outcome",
        json={"actual_delay_hours": 2.5, "actual_damage_occurred": False},
    )
    assert response.status_code == 404


class TestRealPersistence:
    """Requires a reachable Postgres. Run `docker compose up -d postgres` first."""

    @classmethod
    def setup_class(cls):
        if not _postgres_reachable():
            import pytest

            pytest.skip("Postgres not reachable; run `docker compose up -d postgres`")

    def test_predict_route_then_read_and_report_outcome(self, monkeypatch):
        monkeypatch.setattr(route_generator, "_get_client", lambda: UnavailableORSClient())

        predict_response = client.post("/predict-route", json=_predict_route_payload())
        assert predict_response.status_code == 200
        shipment_id = predict_response.json()["shipment_id"]

        get_response = client.get(f"/shipments/{shipment_id}")
        assert get_response.status_code == 200
        record = get_response.json()
        assert record["outcome_status"] == "predicted_only"
        assert record["actual_delay_hours"] is None

        list_response = client.get("/shipments", params={"commodity_type": "Salmon Segar"})
        assert list_response.status_code == 200
        assert any(item["shipment_id"] == shipment_id for item in list_response.json()["items"])

        patch_response = client.patch(
            f"/shipments/{shipment_id}/outcome",
            json={"actual_delay_hours": 3.5, "actual_damage_occurred": False, "outcome_notes": "arrived fine"},
        )
        assert patch_response.status_code == 200
        updated = patch_response.json()
        assert updated["outcome_status"] == "outcome_reported"
        assert updated["actual_delay_hours"] == 3.5
        assert updated["actual_damage_occurred"] is False

    def test_corridor_baseline_learns_from_reported_outcomes(self, monkeypatch):
        """The "learning" loop: report a handful of outcomes with a distinctive
        actual_delay_hours for one corridor, then confirm a fresh prediction on
        that same corridor shows historical_delay_avg_hours pulled toward it --
        not just returning the formula-only prior anymore."""
        monkeypatch.setattr(route_generator, "_get_client", lambda: UnavailableORSClient())

        # Bandung -> Jakarta: a distinct corridor/distance bucket from the
        # Jakarta -> Surabaya pair other tests in this file use, so accumulated
        # samples don't cross-contaminate between tests.
        payload = _predict_route_payload(
            origin={"lat": -6.9175, "lon": 107.6191},
            destination={"lat": -6.2088, "lon": 106.8456},
        )

        baseline_response = client.post("/predict-route", json=payload)
        assert baseline_response.status_code == 200
        distance_km = baseline_response.json()["recommended_route"]["distance_km"]
        formula_only_delay = historical_baseline.expected_base_delay_hours("darat", distance_km, "None")

        distinctive_delay = 999.0
        for _ in range(5):
            predict_response = client.post("/predict-route", json=payload)
            shipment_id = predict_response.json()["shipment_id"]
            patch_response = client.patch(
                f"/shipments/{shipment_id}/outcome",
                json={"actual_delay_hours": distinctive_delay, "actual_damage_occurred": False},
            )
            assert patch_response.status_code == 200

        learned_response = client.post("/predict-route", json=payload)
        learned_delay = learned_response.json()["recommended_route"]["historical_delay_avg_hours"]

        # A handful of consistent 999h reports must pull the blended baseline
        # well past what the formula alone would ever produce for a darat route.
        assert learned_delay > formula_only_delay + 50

    def test_simulate_scenario_creates_no_shipment_row(self, monkeypatch):
        monkeypatch.setattr(route_generator, "_get_client", lambda: UnavailableORSClient())

        before_total = client.get("/shipments", params={"limit": 1}).json()["total"]
        client.post(
            "/simulate-scenario",
            json={
                "baseline": {
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
        after_total = client.get("/shipments", params={"limit": 1}).json()["total"]
        assert after_total == before_total
