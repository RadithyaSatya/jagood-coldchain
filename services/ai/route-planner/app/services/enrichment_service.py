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
from app.services.temperature_service import (
    INSULATION_K_PER_HOUR,
    fetch_ambient_temp_c,
    simulate_cargo_temperature,
    synthetic_ambient_temp_c,
)
from app.services.weather_service import get_port_conditions, get_sea_leg_conditions

CARGO_TEMP_SAMPLE_POINTS = 6

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
    "hotspot_lat": None,
    "hotspot_lon": None,
}

# Neutral Indonesian tropical baseline used when there's no port stop to fetch
# a real BMKG reading for (darat routes), or the reading is unavailable. Kept
# below the 33C "equipment-stress-relevant" threshold in feature_pipeline.py
# so it contributes zero extra risk without needing a special case there.
PORT_AMBIENT_TEMP_DEFAULT_C = 30.0


def _port_info(port) -> dict:
    return {"port_name": port.port_name, "lat": port.lat, "lon": port.lon}


def _sample_geometry(geometry: list[list[float]], n: int) -> list[tuple[float, float]]:
    if not geometry:
        return []
    if len(geometry) <= n:
        return [(p[0], p[1]) for p in geometry]
    step = (len(geometry) - 1) / (n - 1)
    return [(geometry[round(i * step)][0], geometry[round(i * step)][1]) for i in range(n)]


async def _resolve_cargo_temperature(
    client: httpx.AsyncClient,
    candidate: dict,
    ideal_c: float,
    departure_time: dt.datetime,
    cold_chain_equipment: str,
    insulation_quality: str,
) -> dict:
    """For 'reefer' (default): cargo assumed to stay at ideal temp throughout
    -- no Open-Meteo call, zero added latency/failure-risk for the common
    case. For 'pasif': samples real ambient temperature along the route at
    the estimated arrival time of each sampled point, then simulates cargo
    temperature drifting toward it (temperature_service.py)."""
    duration = candidate["estimated_duration_hours"]
    if cold_chain_equipment != "pasif":
        return {"max_cargo_temp_c": ideal_c, "effective_consumed_hours": duration, "profile": []}

    points = _sample_geometry(candidate.get("geometry") or [], CARGO_TEMP_SAMPLE_POINTS)
    if not points:
        return {"max_cargo_temp_c": ideal_c, "effective_consumed_hours": duration, "profile": []}

    n = len(points)
    ambient_samples: list[tuple[float, float]] = []
    for i, (lat, lon) in enumerate(points):
        elapsed = duration * i / max(1, n - 1)
        arrival_time = departure_time + dt.timedelta(hours=elapsed)
        temp = await fetch_ambient_temp_c(client, lat, lon, arrival_time)
        if temp is None:
            temp = synthetic_ambient_temp_c(arrival_time.month, arrival_time.hour + arrival_time.minute / 60)
        ambient_samples.append((elapsed, temp))

    k = INSULATION_K_PER_HOUR.get(insulation_quality, INSULATION_K_PER_HOUR["sedang"])
    report_hours = [s[0] for s in ambient_samples]
    return simulate_cargo_temperature(
        initial_temp_c=ideal_c,
        ambient_samples=ambient_samples,
        total_duration_hours=duration,
        ideal_c=ideal_c,
        k_per_hour=k,
        report_at_hours=report_hours,
    )


async def _resolve_conditions(client: httpx.AsyncClient, candidate: dict, target_time: dt.datetime) -> dict:
    if candidate["transport_mode"] == "darat":
        return dict(LAND_DEFAULT_CONDITIONS)
    return await get_sea_leg_conditions(client, candidate["sea_waypoints"], target_time)


async def _resolve_port_ambient_temp_c(client: httpx.AsyncClient, port_pair: dict | None, target_time: dt.datetime) -> float:
    """Worst-case (hottest) ambient temperature across the embark/disembark
    port stops -- that's where cargo sits idle and reefer units are most
    exposed to equipment/infrastructure stress. Defaults for darat routes
    (no port pair) or if BMKG has no reading for either port."""
    if port_pair is None:
        return PORT_AMBIENT_TEMP_DEFAULT_C

    embark_conditions, disembark_conditions = await asyncio.gather(
        get_port_conditions(client, port_pair["embark"], target_time),
        get_port_conditions(client, port_pair["disembark"], target_time),
    )
    temps = [
        c["ambient_temp_c"]
        for c in (embark_conditions, disembark_conditions)
        if c["ambient_temp_c"] is not None
    ]
    return max(temps) if temps else PORT_AMBIENT_TEMP_DEFAULT_C


async def enrich_candidate(
    client: httpx.AsyncClient,
    candidate: dict,
    commodity_type: str,
    departure_time: dt.datetime,
    shipment_id: str,
    route_id: str,
    cold_chain_equipment: str = "reefer",
    insulation_quality: str = "sedang",
) -> dict:
    commodity = get_commodity(commodity_type)
    ideal_c = (commodity["temp_ideal_min_c"] + commodity["temp_ideal_max_c"]) / 2
    baseline = estimate_historical_baseline(candidate["transport_mode"], candidate["distance_km"])
    port_pair = candidate.get("port_pair")
    conditions, port_ambient_temp_c, cargo_sim = await asyncio.gather(
        _resolve_conditions(client, candidate, departure_time),
        _resolve_port_ambient_temp_c(client, port_pair, departure_time),
        _resolve_cargo_temperature(client, candidate, ideal_c, departure_time, cold_chain_equipment, insulation_quality),
    )

    risk_hotspot = None
    if conditions.get("hotspot_lat") is not None:
        risk_hotspot = {"lat": conditions["hotspot_lat"], "lon": conditions["hotspot_lon"]}

    return {
        "shipment_id": shipment_id,
        "route_id": route_id,
        "commodity_type": commodity_type,
        "commodity_temp_ideal_c": ideal_c,
        "commodity_shelf_life_hours": commodity["shelf_life_hours_at_ideal_temp"],
        "commodity_delay_tolerance_hours": commodity["delay_tolerance_hours"],
        "transport_mode": candidate["transport_mode"],
        "distance_km": candidate["distance_km"],
        "estimated_duration_hours": candidate["estimated_duration_hours"],
        "estimated_arrival": departure_time + dt.timedelta(hours=candidate["estimated_duration_hours"]),
        "wave_height_m": conditions["wave_height_m"],
        "wave_category": conditions["wave_category"],
        "wind_speed_kmh": conditions["wind_speed_kmh"],
        "weather_condition": conditions["weather_condition"],
        "port_status_flag": conditions["port_status_flag"],
        "port_ambient_temp_c": port_ambient_temp_c,
        "historical_delay_avg_hours": baseline["historical_delay_avg_hours"],
        "historical_damage_rate": baseline["historical_damage_rate"],
        "departure_hour": departure_time.hour,
        "data_quality": candidate.get("data_quality", "live"),
        "geometry": candidate.get("geometry", []),
        "risk_hotspot": risk_hotspot,
        "port_pair": {"embark": _port_info(port_pair["embark"]), "disembark": _port_info(port_pair["disembark"])}
        if port_pair
        else None,
        "cold_chain_equipment": cold_chain_equipment,
        "max_cargo_temp_excess_c": round(max(0.0, cargo_sim["max_cargo_temp_c"] - ideal_c), 2),
        "cargo_temp_profile": cargo_sim.get("profile", []),
    }


async def enrich_all_candidates(
    candidates: list[dict],
    commodity_type: str,
    departure_time: dt.datetime,
    shipment_id: str,
    cold_chain_equipment: str = "reefer",
    insulation_quality: str = "sedang",
) -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        route_ids = [f"{c['transport_mode']}-{i + 1}" for i, c in enumerate(candidates)]
        tasks = [
            enrich_candidate(
                client,
                candidate,
                commodity_type,
                departure_time,
                shipment_id,
                route_id,
                cold_chain_equipment,
                insulation_quality,
            )
            for candidate, route_id in zip(candidates, route_ids)
        ]
        return await asyncio.gather(*tasks)
