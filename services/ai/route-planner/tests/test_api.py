"""API-level smoke tests. Only covers what's reachable without a live network
call to OpenRouteService/BMKG or a live Postgres connection (see enrichment_service
and route_generator) -- everything else is exercised via rank_candidates directly
in test_ranking_service.py."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_commodities_endpoint_returns_known_shape():
    response = client.get("/commodities")
    assert response.status_code == 200
    body = response.json()
    assert len(body) > 0
    assert "commodity_type" in body[0]
    assert "temp_sensitivity_level" in body[0]


def test_predict_route_rejects_unknown_commodity_before_touching_network():
    """The commodity lookup happens before generate_candidates/enrich_all_candidates,
    so an unknown commodity_type should 404 immediately -- this must stay true, or a
    bad request starts making live OpenRouteService/BMKG calls for nothing."""
    response = client.post(
        "/predict-route",
        json={
            "origin": {"lat": -6.2088, "lon": 106.8456},
            "destination": {"lat": -7.2575, "lon": 112.7521},
            "commodity_type": "Definitely Not A Real Commodity",
            "departure_time": "2026-08-15T08:00:00Z",
        },
    )
    assert response.status_code == 404


def test_simulate_scenario_requires_a_change():
    response = client.post(
        "/simulate-scenario",
        json={
            "baseline": {
                "origin": {"lat": -6.2088, "lon": 106.8456},
                "destination": {"lat": -7.2575, "lon": 112.7521},
                "commodity_type": "Salmon Segar",
                "departure_time": "2026-08-15T08:00:00Z",
            },
            "changes": {},
        },
    )
    assert response.status_code == 422


def test_simulate_scenario_rejects_unknown_commodity_before_touching_network():
    response = client.post(
        "/simulate-scenario",
        json={
            "baseline": {
                "origin": {"lat": -6.2088, "lon": 106.8456},
                "destination": {"lat": -7.2575, "lon": 112.7521},
                "commodity_type": "Definitely Not A Real Commodity",
                "departure_time": "2026-08-15T08:00:00Z",
            },
            "changes": {"delay_hours": 12},
        },
    )
    assert response.status_code == 404
