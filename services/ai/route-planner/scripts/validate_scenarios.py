"""Runs a handful of end-to-end shipment scenarios spanning different
commodities/routes/seasons against the live backend, plus one forced
extreme-weather case (bypassing live BMKG data, which we don't control) to
validate FR-6: extreme conditions should demote a candidate and set
trigger_reason rather than hard-blocking it."""
import asyncio
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.enrichment_service import enrich_all_candidates  # noqa: E402
from app.services.ranking_service import rank_candidates  # noqa: E402
from app.services.route_generator import generate_candidates  # noqa: E402

SCENARIOS = [
    {"name": "Jakarta -> Surabaya, Salmon Segar", "origin": (-6.2088, 106.8456), "destination": (-7.2575, 112.7521), "commodity": "Salmon Segar"},
    {"name": "Jakarta -> Makassar, Udang Beku", "origin": (-6.2088, 106.8456), "destination": (-5.1477, 119.4327), "commodity": "Udang Beku"},
    {"name": "Medan -> Jakarta, Ayam Segar", "origin": (3.5952, 98.6722), "destination": (-6.2088, 106.8456), "commodity": "Ayam Segar"},
    {"name": "Denpasar -> Makassar, Susu Segar", "origin": (-8.6705, 115.2126), "destination": (-5.1477, 119.4327), "commodity": "Susu Segar"},
]


def print_result(name: str, ranked: dict) -> None:
    print(f"\n=== {name} ===")
    r = ranked["recommended_route"]
    print(
        f"  RECOMMENDED: {r['route_id']} ({r['transport_mode']}) {r['distance_km']}km "
        f"{r['estimated_duration_hours']}h risk={r['risk_level']} p={r['risk_probability']:.3f} "
        f"trigger={r['trigger_reason']}"
    )
    for alt in ranked["alternative_routes"]:
        print(
            f"  alt: {alt['route_id']} ({alt['transport_mode']}) {alt['distance_km']}km "
            f"{alt['estimated_duration_hours']}h risk={alt['risk_level']} p={alt['risk_probability']:.3f} "
            f"trigger={alt['trigger_reason']}"
        )


async def run_live_scenarios() -> None:
    departure_time = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=12)
    for scenario in SCENARIOS:
        candidates = generate_candidates(scenario["origin"], scenario["destination"])
        enriched = await enrich_all_candidates(
            candidates, scenario["commodity"], departure_time, f"demo-{scenario['name']}"
        )
        ranked = rank_candidates(enriched)
        print_result(scenario["name"], ranked)


def run_forced_extreme_weather_scenario() -> None:
    """Two candidates for the same shipment: one calm land route, one sea
    route we force into Ekstrem wave conditions + a closed port. FR-6 requires
    the extreme candidate to still be returned (not hard-blocked) but demoted
    below the calmer alternative, with trigger_reason populated."""
    shared = {
        "shipment_id": "demo-extreme-weather",
        "commodity_type": "Tuna Segar",
        "commodity_temp_ideal_c": 0.5,
        "commodity_shelf_life_hours": 96,
        "commodity_delay_tolerance_hours": 4,
        "departure_hour": 8,
        "data_quality": "live",
    }
    candidates = [
        {
            **shared,
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
        },
        {
            **shared,
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
        },
    ]
    ranked = rank_candidates(candidates)
    print_result("FORCED EXTREME WEATHER (Ekstrem wave + closed port)", ranked)

    recommended = ranked["recommended_route"]
    demoted = next(r for r in [ranked["recommended_route"], *ranked["alternative_routes"]] if r["route_id"] == "kombinasi-1")

    assert recommended["route_id"] == "darat-1", "Expected the calm land route to be recommended over the extreme-weather sea route"
    assert demoted["trigger_reason"] is not None, "Expected trigger_reason to be set on the extreme-weather candidate"
    assert demoted in ranked["alternative_routes"], "Expected the extreme-weather candidate to still be offered as an alternative, not hard-blocked"
    print("\n  PASS: extreme-weather candidate demoted + trigger_reason set + still offered as alternative (FR-6 validated).")


if __name__ == "__main__":
    asyncio.run(run_live_scenarios())
    run_forced_extreme_weather_scenario()
