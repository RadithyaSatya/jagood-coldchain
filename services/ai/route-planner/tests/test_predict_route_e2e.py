"""End-to-end test of POST /predict-route through the real pipeline
(generate_candidates -> enrich_all_candidates -> rank_candidates), unlike
test_ranking_service.py which calls rank_candidates directly with hand-built
candidates and never touches route_generator.py or enrichment_service.py.

Outbound HTTP (OpenRouteService via `requests`, BMKG/Open-Meteo via `httpx`)
is recorded once into a VCR cassette (tests/cassettes/) and replayed on every
later run -- no live network, no API keys, no rate-limit burn in CI. The
recorded ORS calls happen to be unauthenticated (no ORS_API_KEY in this
environment) and got a real 401 back, which route_generator.py's ApiError
handler turns into the documented haversine-based `data_quality: "estimated"`
fallback -- so this test also doubles as a regression test for that fallback
path. Re-record with a real key if you want to freeze the live-data path
instead: `pytest --record-mode=rewrite tests/test_predict_route_e2e.py`.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.mark.vcr
def test_predict_route_end_to_end_jakarta_surabaya():
    response = client.post(
        "/predict-route",
        json={
            "origin": {"lat": -6.2088, "lon": 106.8456},
            "destination": {"lat": -7.2575, "lon": 112.7521},
            "commodity_type": "Salmon Segar",
            "departure_time": "2026-08-15T08:00:00Z",
            "ranking_preference": "risiko",
            # "darat" keeps this cassette small and reproducible: "semua"/"kombinasi"
            # additionally fan out concurrent ORS + BMKG calls across every candidate
            # port pair, and re-recording it turned out to be non-deterministic (the
            # live ORS endpoint didn't return identical responses/bodies run to run).
            # The multimodal path's business logic (FR-6 demotion) is already covered
            # without any network in test_ranking_service.py.
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
    assert "risk_explanation_summary" in recommended

    # FR-5: the recommended route must be at least as low-risk as every
    # alternative -- i.e. actually sorted risk-first, not just "some response".
    all_routes = [recommended, *body["alternative_routes"]]
    risk_order = ["Low", "Medium", "High"]
    assert risk_order.index(recommended["risk_level"]) == min(
        risk_order.index(r["risk_level"]) for r in all_routes
    )
