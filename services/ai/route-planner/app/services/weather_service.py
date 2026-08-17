import datetime as dt
import json
import re
from pathlib import Path

import httpx
from shapely.geometry import Point, shape

from app.core.config import settings
from app.core.db import get_cached, set_cached
from app.services.port_selector import Port

GEOJSON_CACHE_TTL_SECONDS = 24 * 3600
LOCAL_GEOJSON_PATH = Path(__file__).resolve().parent.parent / "data" / "bmkg_perairan_areas.geojson"

WAVE_CATEGORY_ORDER = ["Tenang", "Rendah", "Sedang", "Tinggi", "Sangat Tinggi", "Ekstrem", "Sangat Ekstrem"]
EXTREME_WAVE_CATEGORIES = {"Tinggi", "Sangat Tinggi", "Ekstrem", "Sangat Ekstrem"}

KNOTS_TO_KMH = 1.852


def knots_to_kmh(knots: float) -> float:
    return knots * KNOTS_TO_KMH


def parse_wave_height_m(wave_desc: str) -> float:
    """'0.5 - 1.25 m' -> 0.875 (midpoint). Falls back to the single number found,
    or 0.0 if the string can't be parsed."""
    numbers = [float(n) for n in re.findall(r"\d+\.?\d*", wave_desc or "")]
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)


def worst_wave_category(categories: list[str]) -> str:
    ranked = [c for c in categories if c in WAVE_CATEGORY_ORDER]
    if not ranked:
        return "Tenang"
    return max(ranked, key=WAVE_CATEGORY_ORDER.index)


def derive_port_status_flag(wave_category: str) -> int:
    return 0 if wave_category in EXTREME_WAVE_CATEGORIES else 1


async def _fetch_json_cached(client: httpx.AsyncClient, path: str, cache_key: str, ttl_seconds: int) -> dict:
    cached = get_cached(cache_key, ttl_seconds)
    if cached is not None:
        return json.loads(cached)
    resp = await client.get(f"{settings.bmkg_base_url}{path}")
    resp.raise_for_status()
    data = resp.json()
    set_cached(cache_key, json.dumps(data))
    return data


async def get_perairan_regions_geojson(client: httpx.AsyncClient) -> dict:
    data = await _fetch_json_cached(
        client, "/static/wilayah_perairan.json", "geojson:wilayah_perairan", GEOJSON_CACHE_TTL_SECONDS
    )
    LOCAL_GEOJSON_PATH.write_text(json.dumps(data), encoding="utf-8")
    return data


async def get_perairan_file_index(client: httpx.AsyncClient) -> dict[str, str]:
    """code -> filename, e.g. 'I.07' -> 'I.07_Perairan Gresik - Surabaya.json'"""
    listing = await _fetch_json_cached(client, "/perairan_list", "index:perairan_list", GEOJSON_CACHE_TTL_SECONDS)
    return {f["name"].split("_")[0]: f["name"] for f in listing["files"]}


async def get_pelabuhan_file_index(client: httpx.AsyncClient) -> list[dict]:
    """[{coor: [lat, lon], name: filename, portname: str}, ...]"""
    listing = await _fetch_json_cached(client, "/pelabuhan_list", "index:pelabuhan_list", GEOJSON_CACHE_TTL_SECONDS)
    return listing["files"]


def find_region_code_for_point(lat: float, lon: float, regions_geojson: dict) -> str | None:
    point = Point(lon, lat)
    for feature in regions_geojson["features"]:
        if shape(feature["geometry"]).contains(point):
            return feature["properties"]["WP_1"]
    return None


def find_nearest_pelabuhan_file(lat: float, lon: float, pelabuhan_index: list[dict]) -> str:
    from app.services.geo_utils import haversine_km

    nearest = min(pelabuhan_index, key=lambda p: haversine_km(lat, lon, p["coor"][0], p["coor"][1]))
    return nearest["name"]


def select_forecast_entry(data_entries: list[dict], target_time: dt.datetime) -> dict:
    """Pick the entry whose [valid_from, valid_to) window contains target_time.
    BMKG only forecasts ~4 days ahead (Hari ini/Besok/H+2/H+3): if target_time is
    outside that window, fall back to the nearest edge entry (first or last)."""
    if target_time.tzinfo is not None:
        target_time = target_time.astimezone(dt.timezone.utc).replace(tzinfo=None)
    parsed = [
        (
            dt.datetime.strptime(e["valid_from"], "%Y-%m-%d %H:%M UTC"),
            dt.datetime.strptime(e["valid_to"], "%Y-%m-%d %H:%M UTC"),
            e,
        )
        for e in data_entries
    ]
    parsed.sort(key=lambda t: t[0])
    for valid_from, valid_to, entry in parsed:
        if valid_from <= target_time < valid_to:
            return entry
    if target_time < parsed[0][0]:
        return parsed[0][2]
    return parsed[-1][2]


def _entry_to_conditions(entry: dict) -> dict:
    wave_cat = entry.get("wave_cat", "Tenang")
    return {
        "weather_condition": entry.get("weather", "Cerah"),
        "wave_category": wave_cat,
        "wave_height_m": parse_wave_height_m(entry.get("wave_desc", "")),
        "wind_speed_kmh": knots_to_kmh(entry.get("wind_speed_max", 0)),
        "port_status_flag": derive_port_status_flag(wave_cat),
    }


def _entry_to_ambient_temp(entry: dict) -> float | None:
    """Only the pelabuhan (port) endpoint carries temp_min/temp_max -- perairan
    (open water) entries don't, so this returns None there."""
    temp_min, temp_max = entry.get("temp_min"), entry.get("temp_max")
    if temp_min is None or temp_max is None:
        return None
    return (temp_min + temp_max) / 2


async def get_port_conditions(client: httpx.AsyncClient, port: Port, target_time: dt.datetime) -> dict:
    pelabuhan_index = await get_pelabuhan_file_index(client)
    filename = find_nearest_pelabuhan_file(port.lat, port.lon, pelabuhan_index)
    data = await _fetch_json_cached(client, f"/pelabuhan/{filename}", f"pelabuhan:{filename}", settings.bmkg_cache_ttl_seconds)
    entry = select_forecast_entry(data["data"], target_time)
    conditions = _entry_to_conditions(entry)
    conditions["ambient_temp_c"] = _entry_to_ambient_temp(entry)
    return conditions


_DEFAULT_SEA_CONDITIONS = {
    "weather_condition": "Cerah",
    "wave_category": "Tenang",
    "wave_height_m": 0.0,
    "wind_speed_kmh": 0.0,
    "port_status_flag": 1,
    "hotspot_lat": None,
    "hotspot_lon": None,
    "weather_data_quality": "fallback",
}


def fallback_sea_conditions() -> dict:
    """Neutral, explicitly labelled conditions for an unavailable BMKG boundary."""
    return dict(_DEFAULT_SEA_CONDITIONS)


async def get_sea_leg_conditions(
    client: httpx.AsyncClient, waypoints: list[tuple[float, float]], target_time: dt.datetime
) -> dict:
    """Worst-case aggregation across every maritime region a sea leg's sampled
    waypoints (lat, lon) fall into. Also pinpoints the (lat, lon) of whichever
    sampled waypoint carried the worst wave category, so the frontend can plot
    exactly where along the route the risk is, not just report a route-level
    number."""
    regions_geojson = await get_perairan_regions_geojson(client)
    file_index = await get_perairan_file_index(client)

    code_cache: dict[str, dict] = {}
    point_conditions: list[tuple[float, float, dict]] = []

    for lat, lon in waypoints:
        code = find_region_code_for_point(lat, lon, regions_geojson)
        if code is None:
            continue
        if code not in code_cache:
            filename = file_index.get(code)
            if filename is None:
                continue
            data = await _fetch_json_cached(
                client, f"/perairan/{filename}", f"perairan:{filename}", settings.bmkg_cache_ttl_seconds
            )
            entry = select_forecast_entry(data["data"], target_time)
            code_cache[code] = _entry_to_conditions(entry)
        point_conditions.append((lat, lon, code_cache[code]))

    if not point_conditions:
        return dict(_DEFAULT_SEA_CONDITIONS)

    worst_lat, worst_lon, worst_cond = max(
        point_conditions, key=lambda p: WAVE_CATEGORY_ORDER.index(p[2]["wave_category"])
    )
    return {
        "weather_condition": worst_cond["weather_condition"],
        "wave_category": worst_cond["wave_category"],
        "wave_height_m": max(c["wave_height_m"] for _, _, c in point_conditions),
        "wind_speed_kmh": max(c["wind_speed_kmh"] for _, _, c in point_conditions),
        "port_status_flag": derive_port_status_flag(worst_cond["wave_category"]),
        "hotspot_lat": worst_lat,
        "hotspot_lon": worst_lon,
        "weather_data_quality": "forecast",
    }
