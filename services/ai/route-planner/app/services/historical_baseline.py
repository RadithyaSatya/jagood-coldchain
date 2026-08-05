"""Deterministic corridor-baseline estimator -- the live-serving counterpart
to backend/training/synthetic_corridors.py's Layer A. No real shipment
history exists yet, so this pure function *is* the `historical_delay_avg_hours`
/ `historical_damage_rate` feature at inference time: the same mode+distance+
exposure-tier formula used to build training corridors, evaluated at its
noise-free expected value (rather than one noisy random draw) so a live
prediction is reproducible. Shared here (rather than duplicated in the
training script) so training and serving can never drift apart -- the
training generator imports these same functions and adds noise on top.
"""
import itertools

import numpy as np

from app.services.geo_utils import haversine_km
from app.services.port_selector import _load_ports

MODE_BASE_DELAY = {"darat": 2.0, "laut": 6.0, "kombinasi": 10.0}
MODE_RISK = {"darat": 0.0, "laut": 0.4, "kombinasi": 0.6}
EXPOSURE_BONUS = {"Low": 0.0, "Medium": 3.0, "High": 7.0, "None": 0.0}
EXPOSURE_SCORE = {"Low": 0.0, "Medium": 0.5, "High": 1.0, "None": 0.0}
EXPOSURE_TIERS = ["Low", "Medium", "High"]


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
        return {
            "historical_delay_avg_hours": round(expected_base_delay_hours("darat", distance_km, "None"), 2),
            "historical_damage_rate": round(expected_base_damage_rate("darat", distance_km, "None"), 4),
        }

    percentile = sea_distance_percentile(distance_km)
    weights = exposure_tier_weights(percentile)
    delay = sum(w * expected_base_delay_hours(transport_mode, distance_km, tier) for tier, w in weights.items())
    damage = sum(w * expected_base_damage_rate(transport_mode, distance_km, tier) for tier, w in weights.items())
    return {
        "historical_delay_avg_hours": round(delay, 2),
        "historical_damage_rate": round(damage, 4),
    }
