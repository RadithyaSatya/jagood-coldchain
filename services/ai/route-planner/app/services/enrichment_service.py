"""Combines a raw route candidate (from route_generator.py) with commodity
lookup, the deterministic historical prior (historical_baseline.py), and live
BMKG weather/wave conditions (weather_service.py) into one full feature row
matching the route_candidates schema (PRD 7.1) -- ready to feed straight into
the trained model via ranking_service.py."""
import asyncio
import datetime as dt

import httpx

from app.services.commodity_service import get_commodity
from app.services.historical_baseline import estimate_historical_baseline
from app.services.weather_service import get_port_conditions, get_sea_leg_conditions

# BMKG has no general inland-weather product (only maritime perairan/pelabuhan
# forecasts), so pure land legs use a fixed neutral default rather than a
# fabricated "live" call. This mirrors LAND_WEATHER_DIST's central tendency in
# backend/training/generate_synthetic_data.py.
LAND_DEFAULT_CONDITIONS = {
    "weather_condition": "Berawan",
    "wave_category": "Tenang",
    "wave_height_m": 0.0,
    "wind_speed_kmh": 15.0,
    "port_status_flag": 1,
}


async def _resolve_conditions(client: httpx.AsyncClient, candidate: dict, target_time: dt.datetime) -> dict:
    if candidate["transport_mode"] == "darat":
        return dict(LAND_DEFAULT_CONDITIONS)
    return await get_sea_leg_conditions(client, candidate["sea_waypoints"], target_time)


async def enrich_candidate(
    client: httpx.AsyncClient,
    candidate: dict,
    commodity_type: str,
    departure_time: dt.datetime,
    shipment_id: str,
    route_id: str,
) -> dict:
    commodity = get_commodity(commodity_type)
    baseline = estimate_historical_baseline(candidate["transport_mode"], candidate["distance_km"])
    conditions = await _resolve_conditions(client, candidate, departure_time)

    return {
        "shipment_id": shipment_id,
        "route_id": route_id,
        "commodity_type": commodity_type,
        "commodity_temp_ideal_c": (commodity["temp_ideal_min_c"] + commodity["temp_ideal_max_c"]) / 2,
        "commodity_shelf_life_hours": commodity["shelf_life_hours_at_ideal_temp"],
        "commodity_delay_tolerance_hours": commodity["delay_tolerance_hours"],
        "transport_mode": candidate["transport_mode"],
        "distance_km": candidate["distance_km"],
        "estimated_duration_hours": candidate["estimated_duration_hours"],
        "wave_height_m": conditions["wave_height_m"],
        "wave_category": conditions["wave_category"],
        "wind_speed_kmh": conditions["wind_speed_kmh"],
        "weather_condition": conditions["weather_condition"],
        "port_status_flag": conditions["port_status_flag"],
        "historical_delay_avg_hours": baseline["historical_delay_avg_hours"],
        "historical_damage_rate": baseline["historical_damage_rate"],
        "departure_hour": departure_time.hour,
        "data_quality": candidate.get("data_quality", "live"),
        "port_pair": candidate.get("port_pair"),
    }


async def enrich_all_candidates(
    candidates: list[dict],
    commodity_type: str,
    departure_time: dt.datetime,
    shipment_id: str,
) -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        route_ids = [f"{c['transport_mode']}-{i + 1}" for i, c in enumerate(candidates)]
        tasks = [
            enrich_candidate(client, candidate, commodity_type, departure_time, shipment_id, route_id)
            for candidate, route_id in zip(candidates, route_ids)
        ]
        return await asyncio.gather(*tasks)
