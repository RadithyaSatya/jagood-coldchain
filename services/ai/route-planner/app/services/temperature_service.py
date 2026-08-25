"""Ambient temperature + passive-cargo temperature simulation, used only for
`cold_chain_equipment == "pasif"` shipments (no active reefer). Reefer
shipments never call any of this -- cargo is assumed to stay at the
commodity's ideal temperature throughout, matching the pre-existing
behavior (see enrichment_service.py).

Data source is Open-Meteo (https://open-meteo.com) -- free, no API key,
real hourly ambient air temperature for any lat/lon worldwide including
open ocean. `synthetic_ambient_temp_c` is a climatological fallback used
both when Open-Meteo is unreachable (live serving) and to generate
synthetic training data (training/generate_synthetic_data.py) -- one
shared function so the two can never drift apart, same principle as
historical_baseline.py.
"""
import datetime as dt
import json
import math

import httpx

from app.core.config import settings
from app.core.db import get_cached, set_cached

OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"

INSULATION_K_PER_HOUR = {"baik": 0.08, "sedang": 0.15, "buruk": 0.35}
DEFAULT_Q10 = 2.5
DEFAULT_TIMESTEP_HOURS = 0.5

# Indonesian tropical diurnal baseline (deg C): coolest around 04:00, hottest
# around 14:00. Deliberately simple (single sinusoid + a small seasonal
# offset) -- this is a fallback/synthetic-data generator, not a forecast.
_DIURNAL_MIN_C = 25.0
_DIURNAL_MAX_C = 32.0


def _monsoon_offset_c(month: int) -> float:
    if month in (6, 7, 8, 9):  # east monsoon / dry season -- generally hotter
        return 1.0
    if month in (12, 1, 2):  # west monsoon / wet season -- generally cooler
        return -0.5
    return 0.0


def synthetic_ambient_temp_c(month: int, hour_of_day: float) -> float:
    mean = (_DIURNAL_MIN_C + _DIURNAL_MAX_C) / 2
    amplitude = (_DIURNAL_MAX_C - _DIURNAL_MIN_C) / 2
    diurnal = mean + amplitude * math.sin(2 * math.pi * (hour_of_day - 8) / 24)
    return diurnal + _monsoon_offset_c(month)


def _cache_key(lat: float, lon: float, target_time: dt.datetime) -> str:
    return f"openmeteo:{round(lat, 2)}:{round(lon, 2)}:{target_time.strftime('%Y-%m-%d')}"


async def _fetch_open_meteo_hourly(
    client: httpx.AsyncClient, lat: float, lon: float, target_time: dt.datetime
) -> dict | None:
    """Nearest-hour {"temp_c", "precipitation_mm", "weathercode"} at (lat, lon), in one
    Open-Meteo call (its `hourly` param takes several comma-separated variables at once,
    so temperature, precipitation and WMO weather code share a single request/cache
    entry rather than three). None if Open-Meteo is unreachable or the response is
    malformed -- callers should fall back to their own defaults rather than fail
    the request."""
    cache_key = _cache_key(lat, lon, target_time)
    cached = get_cached(cache_key, settings.bmkg_cache_ttl_seconds)
    if cached is not None:
        data = json.loads(cached)
    else:
        try:
            resp = await client.get(
                OPEN_METEO_BASE_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "hourly": "temperature_2m,precipitation,weathercode",
                    "forecast_days": 16,
                    "timezone": "UTC",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError:
            return None
        set_cached(cache_key, json.dumps(data))

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    if not times or not temps:
        return None

    naive_target = target_time.astimezone(dt.timezone.utc).replace(tzinfo=None) if target_time.tzinfo else target_time
    parsed_times = [dt.datetime.fromisoformat(t) for t in times]
    closest_idx = min(range(len(parsed_times)), key=lambda i: abs((parsed_times[i] - naive_target).total_seconds()))

    precipitation = hourly.get("precipitation", [])
    weathercode = hourly.get("weathercode", [])
    return {
        "temp_c": temps[closest_idx],
        "precipitation_mm": precipitation[closest_idx] if closest_idx < len(precipitation) else None,
        "weathercode": weathercode[closest_idx] if closest_idx < len(weathercode) else None,
    }


async def fetch_ambient_temp_c(
    client: httpx.AsyncClient, lat: float, lon: float, target_time: dt.datetime
) -> float | None:
    """Nearest-hour ambient air temperature at (lat, lon). None if Open-Meteo
    is unreachable or the response is malformed -- callers should fall back
    to synthetic_ambient_temp_c rather than fail the request."""
    result = await _fetch_open_meteo_hourly(client, lat, lon, target_time)
    return result["temp_c"] if result is not None else None


async def fetch_weathercode(
    client: httpx.AsyncClient, lat: float, lon: float, target_time: dt.datetime
) -> int | None:
    """Nearest-hour WMO weather code at (lat, lon), or None if unavailable."""
    result = await _fetch_open_meteo_hourly(client, lat, lon, target_time)
    return result["weathercode"] if result is not None else None


def simulate_cargo_temperature(
    initial_temp_c: float,
    ambient_samples: list[tuple[float, float]],
    total_duration_hours: float,
    ideal_c: float,
    k_per_hour: float,
    q10: float = DEFAULT_Q10,
    timestep_hours: float = DEFAULT_TIMESTEP_HOURS,
    report_at_hours: list[float] | None = None,
) -> dict:
    """ambient_samples: [(hours_elapsed, ambient_temp_c), ...] sorted by
    hours_elapsed, sampled along the route. Cargo starts at initial_temp_c
    (assumes proper pre-cooling) and exponentially relaxes toward the
    (linearly-interpolated) ambient temperature at each timestep. Shelf-life
    consumption accelerates above `ideal_c` per the Q10 rule. Returns
    {"max_cargo_temp_c", "effective_consumed_hours"} -- the latter is hours
    of *equivalent* ideal-temperature aging, not wall-clock hours. If
    report_at_hours is given, also returns "profile": the actual (not max)
    simulated cargo temp nearest each requested hour -- a single pass, so
    fluctuating ambient (e.g. cooling off at night) shows up correctly
    instead of a monotonic running-max."""
    if not ambient_samples or total_duration_hours <= 0:
        result = {"max_cargo_temp_c": initial_temp_c, "effective_consumed_hours": total_duration_hours}
        if report_at_hours is not None:
            result["profile"] = [{"hour": round(h, 2), "temp_c": round(initial_temp_c, 2)} for h in report_at_hours]
        return result

    def ambient_at(t: float) -> float:
        if t <= ambient_samples[0][0]:
            return ambient_samples[0][1]
        if t >= ambient_samples[-1][0]:
            return ambient_samples[-1][1]
        for (t0, v0), (t1, v1) in zip(ambient_samples, ambient_samples[1:]):
            if t0 <= t <= t1:
                frac = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
                return v0 + (v1 - v0) * frac
        return ambient_samples[-1][1]

    cargo_temp = initial_temp_c
    max_temp = initial_temp_c
    effective_consumed = 0.0

    steps = max(1, round(total_duration_hours / timestep_hours))
    dt_step = total_duration_hours / steps
    t = 0.0
    trajectory = [(0.0, initial_temp_c)]

    for _ in range(steps):
        ambient = ambient_at(t)
        cargo_temp = ambient + (cargo_temp - ambient) * math.exp(-k_per_hour * dt_step)
        max_temp = max(max_temp, cargo_temp)
        rate = q10 ** ((cargo_temp - ideal_c) / 10.0) if cargo_temp > ideal_c else 1.0
        effective_consumed += rate * dt_step
        t += dt_step
        trajectory.append((t, cargo_temp))

    result = {"max_cargo_temp_c": max_temp, "effective_consumed_hours": effective_consumed}
    if report_at_hours is not None:
        result["profile"] = [
            {"hour": round(h, 2), "temp_c": round(min(trajectory, key=lambda p: abs(p[0] - h))[1], 2)}
            for h in report_at_hours
        ]
    return result
