"""Covers PRD FR-5 (risk-first ranking) and FR-6 (extreme conditions demote,
not hard-block, a candidate). This is the exact logic that regressed silently
in scripts/validate_scenarios.py after cold_chain_equipment/port_ambient_temp_c/
max_cargo_temp_excess_c were added to the model's input columns -- the manual
script only caught it when someone happened to run it by hand. These are the
automated equivalent."""
import pytest

from app.services.ranking_service import rank_candidates

SHARED_FIELDS = {
    "shipment_id": "test-shipment",
    "commodity_type": "Tuna Segar",
    "commodity_temp_ideal_c": 0.5,
    "commodity_shelf_life_hours": 96,
    "commodity_delay_tolerance_hours": 4,
    "departure_hour": 8,
    "data_quality": "live",
    "cold_chain_equipment": "reefer",
    "max_cargo_temp_excess_c": 0.0,
    "expected_delay_hours": 0.0,
}

CALM_LAND_ROUTE = {
    **SHARED_FIELDS,
    "route_id": "darat-1",
    "transport_mode": "darat",
    "distance_km": 800.0,
    "estimated_duration_hours": 14.0,
    "wave_height_m": 0.0,
    "wave_category": "Tenang",
    "wind_speed_kmh": 12.0,
    "weather_condition": "Cerah",
    "port_status_flag": 1,
    "historical_delay_avg_hours": 6.0,
    "historical_damage_rate": 0.05,
    "port_ambient_temp_c": 30.0,
}

EXTREME_SEA_ROUTE = {
    **SHARED_FIELDS,
    "route_id": "kombinasi-1",
    "transport_mode": "kombinasi",
    "distance_km": 750.0,
    "estimated_duration_hours": 30.0,
    "wave_height_m": 7.5,
    "wave_category": "Ekstrem",
    "wind_speed_kmh": 85.0,
    "weather_condition": "Hujan Badai",
    "port_status_flag": 0,
    "historical_delay_avg_hours": 20.0,
    "historical_damage_rate": 0.3,
    "port_ambient_temp_c": 29.0,
}


@pytest.fixture
def calm_and_extreme_candidates():
    return [dict(CALM_LAND_ROUTE), dict(EXTREME_SEA_ROUTE)]


def test_risk_first_ranking_recommends_the_calmer_route(calm_and_extreme_candidates):
    """FR-5: with the default 'risiko' preference, the calm land route must
    outrank the extreme-weather sea route even though it's not multimodal."""
    ranked = rank_candidates(calm_and_extreme_candidates, ranking_preference="risiko")

    assert ranked["recommended_route"]["route_id"] == "darat-1"
    assert [r["route_id"] for r in ranked["alternative_routes"]] == ["kombinasi-1"]


def test_extreme_candidate_is_demoted_not_hard_blocked(calm_and_extreme_candidates):
    """FR-6: extreme conditions must demote a candidate and set trigger_reason,
    not remove it from the response entirely."""
    ranked = rank_candidates(calm_and_extreme_candidates, ranking_preference="risiko")
    all_routes = [ranked["recommended_route"], *ranked["alternative_routes"]]
    demoted = next(r for r in all_routes if r["route_id"] == "kombinasi-1")

    assert demoted["trigger_reason"] is not None
    assert "ekstrem" in demoted["trigger_reason"]
    assert demoted in ranked["alternative_routes"]


def test_calm_route_has_no_trigger_reason(calm_and_extreme_candidates):
    ranked = rank_candidates(calm_and_extreme_candidates, ranking_preference="risiko")
    assert ranked["recommended_route"]["trigger_reason"] is None


def test_speed_ranking_ignores_risk(calm_and_extreme_candidates):
    """'kecepatan' should order purely by estimated_duration_hours: the calm
    route is also the faster one here, so make the slower route lower-risk to
    prove ordering really flips on duration rather than continuing to favor risk."""
    fast_risky = {**EXTREME_SEA_ROUTE, "route_id": "fast-risky", "estimated_duration_hours": 5.0}
    slow_safe = {**CALM_LAND_ROUTE, "route_id": "slow-safe", "estimated_duration_hours": 40.0}

    ranked = rank_candidates([fast_risky, slow_safe], ranking_preference="kecepatan")

    assert ranked["recommended_route"]["route_id"] == "fast-risky"


def test_unrecognized_ranking_preference_falls_back_to_risk_first(calm_and_extreme_candidates):
    """An unrecognized ranking_preference must fall back to risk-first, not
    speed-first -- silently ranking cold-chain shipments by speed is the more
    dangerous failure mode."""
    ranked = rank_candidates(calm_and_extreme_candidates, ranking_preference="not-a-real-preference")
    assert ranked["recommended_route"]["route_id"] == "darat-1"
