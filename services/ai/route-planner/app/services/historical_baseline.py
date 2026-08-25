"""Corridor-baseline estimator -- the live-serving counterpart to
backend/training/synthetic_corridors.py's Layer A. The base formula
(expected_base_delay_hours/expected_base_damage_rate) is the same mode+distance+
exposure-tier formula used to build training corridors, evaluated at its
noise-free expected value (rather than one noisy random draw) so a live
prediction is reproducible. Shared here (rather than duplicated in the
training script) so training and serving can never drift apart -- the
training generator imports these same functions and adds noise on top;
training never calls estimate_historical_baseline itself, so it stays
fully offline/DB-independent.

estimate_historical_baseline() additionally blends in real outcomes reported
via PATCH /shipments/{id}/outcome (app/services/shipment_service.py), once a
given (transport_mode, distance bucket) corridor has enough reports -- see
record_actual_outcome() and MIN_SAMPLES_FOR_BLEND below. This is the "learning"
step: as real shipment outcomes accumulate, the formula-only prior is
gradually replaced by the observed average for that corridor.
"""
import itertools
import logging

import httpx
import numpy as np

from app.core import db
from app.services.geo_utils import haversine_km
from app.services.port_selector import _load_ports
from app.services.temperature_service import fetch_weathercode
from app.services.weather_service import weathercode_to_condition

logger = logging.getLogger(__name__)

MODE_BASE_DELAY = {"darat": 2.0, "laut": 6.0, "kombinasi": 10.0}
MODE_RISK = {"darat": 0.0, "laut": 0.4, "kombinasi": 0.6}
EXPOSURE_BONUS = {"Low": 0.0, "Medium": 3.0, "High": 7.0, "None": 0.0}
EXPOSURE_SCORE = {"Low": 0.0, "Medium": 0.5, "High": 1.0, "None": 0.0}
EXPOSURE_TIERS = ["Low", "Medium", "High"]

# Real outcomes (from PATCH /shipments/{id}/outcome) blend into the formula-based
# baseline once a corridor has enough reports -- ramped, not a hard cutover, so a
# single noisy report can't swing the feature. See estimate_historical_baseline().
MIN_SAMPLES_FOR_BLEND = 3
FULL_TRUST_SAMPLES = 20
DISTANCE_BUCKET_KM = 100


def _distance_bucket_km(distance_km: float) -> int:
    return round(distance_km / DISTANCE_BUCKET_KM) * DISTANCE_BUCKET_KM


def _blend_weight(sample_count: int) -> float:
    if sample_count < MIN_SAMPLES_FOR_BLEND:
        return 0.0
    span = FULL_TRUST_SAMPLES - MIN_SAMPLES_FOR_BLEND
    return min(1.0, (sample_count - MIN_SAMPLES_FOR_BLEND) / span)


def record_actual_outcome(
    transport_mode: str, distance_km: float, actual_delay_hours: float, actual_damage_occurred: bool
) -> None:
    """Best-effort: called from shipment_service.report_outcome() -- a DB hiccup
    here must not fail the outcome-report response."""
    try:
        db.upsert_corridor_stats(
            transport_mode, _distance_bucket_km(distance_km), actual_delay_hours, actual_damage_occurred
        )
    except Exception:
        logger.warning(
            "Failed to update corridor_baseline_stats for %s/%skm", transport_mode, distance_km, exc_info=True
        )


# Weather-attributable delay (checklist FR: "Route Duration and Delay Estimation... lingkungan").
# Bootstrap defaults are illustrative MVP placeholders (not derived from any study), used until a
# given (transport_mode, weather_severity) bucket accumulates enough real checkpoint-derived
# observations (see process_trip_weather_delay/record_weather_delay_observation) to blend in --
# same MIN_SAMPLES/FULL_TRUST ramp pattern as record_actual_outcome, separate constants because
# this is a different, independently-maturing data source.
WEATHER_SEVERITY_MAP = {
    "Cerah": "normal", "Cerah Berawan": "normal", "Berawan": "normal",
    "Berawan Tebal": "hujan_ringan", "Hujan Ringan": "hujan_ringan",
    "Hujan Sedang": "hujan_lebat", "Hujan Lebat": "hujan_lebat",
    "Hujan Badai": "badai",
}
WEATHER_DELAY_BOOTSTRAP_HOURS = {"normal": 0.0, "hujan_ringan": 0.17, "hujan_lebat": 0.42, "badai": 1.0}
MIN_SAMPLES_FOR_WEATHER_BLEND = 3
FULL_TRUST_WEATHER_SAMPLES = 20

# Fallback only, used when a shipment's checkpoints are analyzed without a selected_route_id (no
# POST /shipments/{id}/select-route call) -- mirrors training/synthetic_corridors.py's DARAT_SPEED_KMH.
NOMINAL_SPEED_KMH_DARAT = 45.0


def _weather_severity(weather_condition: str) -> str:
    return WEATHER_SEVERITY_MAP.get(weather_condition, "normal")


def estimate_weather_delay_hours(transport_mode: str, weather_condition: str) -> tuple[float, str]:
    """Returns (hours, data_quality) where data_quality is 'bootstrap' or 'learned'.
    Best-effort: falls back to the bootstrap value on any DB error."""
    severity = _weather_severity(weather_condition)
    bootstrap = WEATHER_DELAY_BOOTSTRAP_HOURS[severity]
    try:
        stats = db.get_weather_delay_stats(transport_mode, severity)
    except Exception:
        stats = None
        logger.warning(
            "Weather delay stats lookup failed for %s/%s; using bootstrap default",
            transport_mode,
            severity,
            exc_info=True,
        )
    if stats and stats["sample_count"] >= MIN_SAMPLES_FOR_WEATHER_BLEND:
        span = FULL_TRUST_WEATHER_SAMPLES - MIN_SAMPLES_FOR_WEATHER_BLEND
        weight = min(1.0, (stats["sample_count"] - MIN_SAMPLES_FOR_WEATHER_BLEND) / span)
        real_avg = stats["delay_hours_sum"] / stats["sample_count"]
        return (1 - weight) * bootstrap + weight * real_avg, "learned"
    return bootstrap, "bootstrap"


def _nominal_speed_kmh(shipment: dict) -> float:
    """Prefer the specific selected route's own ORS-estimated speed (distance/duration, pulled
    from prediction_snapshot) over the flat fallback constant -- a highway route and a backroad
    route don't share one free-flow speed, and ORS already knows the difference. Falls back to
    NOMINAL_SPEED_KMH_DARAT if no route was ever selected or the route's duration is degenerate."""
    route_id = shipment.get("selected_route_id")
    if not route_id:
        return NOMINAL_SPEED_KMH_DARAT
    snapshot = shipment["prediction_snapshot"]
    candidates = [snapshot["recommended_route"], *snapshot["alternative_routes"]]
    route = next((r for r in candidates if r["route_id"] == route_id), None)
    if route is None or route["estimated_duration_hours"] <= 0:
        return NOMINAL_SPEED_KMH_DARAT
    return route["distance_km"] / route["estimated_duration_hours"]


async def process_trip_weather_delay(client: httpx.AsyncClient, shipment: dict) -> None:
    """Best-effort; called from shipment_service.report_outcome(). Only meaningful for darat
    shipments (segment analysis for laut/kombinasi would need land-vs-sea leg classification of
    checkpoints, not built yet). Walks consecutive checkpoints, derives per-segment delay against
    the selected route's own nominal speed, looks up the weather at each segment's midpoint/time,
    and feeds each (weather_severity, delay_hours) pair into weather_delay_stats."""
    if shipment["transport_mode"] != "darat":
        return

    try:
        points = db.select_checkpoints(shipment["shipment_id"])
    except Exception:
        logger.warning("Failed to load checkpoints for %s", shipment["shipment_id"], exc_info=True)
        return

    nominal_speed_kmh = _nominal_speed_kmh(shipment)
    for p1, p2 in zip(points, points[1:]):
        distance_km = haversine_km(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
        elapsed_hours = (p2["recorded_at"] - p1["recorded_at"]).total_seconds() / 3600
        if elapsed_hours <= 0 or distance_km <= 0:
            continue
        expected_hours = distance_km / nominal_speed_kmh
        delay_hours = max(0.0, elapsed_hours - expected_hours)
        if delay_hours <= 0:
            continue

        mid_lat = (p1["lat"] + p2["lat"]) / 2
        mid_lon = (p1["lon"] + p2["lon"]) / 2
        mid_time = p1["recorded_at"] + (p2["recorded_at"] - p1["recorded_at"]) / 2
        try:
            weathercode = await fetch_weathercode(client, mid_lat, mid_lon, mid_time)
        except Exception:
            # Broad on purpose: fetch_weathercode's response cache touches Postgres too.
            weathercode = None
        condition = weathercode_to_condition(weathercode)
        try:
            db.upsert_weather_delay_stats("darat", _weather_severity(condition), delay_hours)
        except Exception:
            logger.warning("Failed to update weather_delay_stats for darat/%s", condition, exc_info=True)


def expected_base_delay_hours(mode: str, distance_km: float, exposure_tier: str) -> float:
    exposure_bonus = EXPOSURE_BONUS.get(exposure_tier, 0.0)
    return max(0.0, MODE_BASE_DELAY[mode] + 0.01 * distance_km + exposure_bonus)


def expected_base_damage_rate(mode: str, distance_km: float, exposure_tier: str) -> float:
    dist_norm = min(1.0, distance_km / 1500.0)
    exposure_score = EXPOSURE_SCORE.get(exposure_tier, 0.0)
    logit = 1.5 * dist_norm + 1.2 * exposure_score + 1.0 * MODE_RISK[mode] - 2.0
    sigmoid = 1.0 / (1.0 + np.exp(-logit))
    return float(np.clip(0.5 * sigmoid, 0.0, 0.6))


def exposure_tier_weights(distance_percentile: float) -> dict[str, float]:
    """Mirrors synthetic_corridors._sample_exposure_tier's probabilities, used
    here as expectation weights instead of a random draw."""
    if distance_percentile < 0.33:
        weights = [0.5, 0.35, 0.15]
    elif distance_percentile < 0.66:
        weights = [0.3, 0.4, 0.3]
    else:
        weights = [0.15, 0.35, 0.5]
    return dict(zip(EXPOSURE_TIERS, weights))


_sea_distance_cache: list[float] | None = None


def _sea_distances() -> list[float]:
    global _sea_distance_cache
    if _sea_distance_cache is None:
        ports = _load_ports()
        _sea_distance_cache = sorted(
            haversine_km(a.lat, a.lon, b.lat, b.lon) for a, b in itertools.combinations(ports, 2)
        )
    return _sea_distance_cache


def sea_distance_percentile(distance_km: float) -> float:
    distances = _sea_distances()
    idx = np.searchsorted(distances, distance_km)
    return idx / len(distances)


def estimate_historical_baseline(transport_mode: str, distance_km: float) -> dict:
    if transport_mode == "darat":
        delay = expected_base_delay_hours("darat", distance_km, "None")
        damage = expected_base_damage_rate("darat", distance_km, "None")
    else:
        percentile = sea_distance_percentile(distance_km)
        weights = exposure_tier_weights(percentile)
        delay = sum(w * expected_base_delay_hours(transport_mode, distance_km, tier) for tier, w in weights.items())
        damage = sum(w * expected_base_damage_rate(transport_mode, distance_km, tier) for tier, w in weights.items())

    try:
        stats = db.get_corridor_stats(transport_mode, _distance_bucket_km(distance_km))
    except Exception:
        stats = None
        logger.warning(
            "Corridor stats lookup failed for %s/%skm; using formula-only baseline",
            transport_mode,
            distance_km,
            exc_info=True,
        )

    if stats and stats["sample_count"] >= MIN_SAMPLES_FOR_BLEND:
        weight = _blend_weight(stats["sample_count"])
        real_delay = stats["delay_hours_sum"] / stats["sample_count"]
        real_damage = stats["damage_occurred_count"] / stats["sample_count"]
        delay = (1 - weight) * delay + weight * real_delay
        damage = (1 - weight) * damage + weight * real_damage

    return {
        "historical_delay_avg_hours": round(delay, 2),
        "historical_damage_rate": round(damage, 4),
    }
