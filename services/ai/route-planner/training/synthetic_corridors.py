"""Layer A of the synthetic data pipeline: builds a set of route "corridors"
(transport_mode, distance_km, wave_exposure_tier) with a fixed baseline
delay/damage prior each. Distances are grounded in real haversine distances
between the curated Indonesian ports in app/data/ports_reference.json, so the
resulting training distribution matches what live ORS/searoute-py calls
produce at inference time (see backend/app/services/port_selector.py).

Corridor baselines (base_delay_hours, base_damage_rate) become the
`historical_delay_avg_hours` / `historical_damage_rate` FEATURE columns at
training time -- a stable, corridor-level prior. Layer B
(generate_synthetic_data.py) samples individual dated shipments on top of
each corridor and combines the baseline with that shipment's own dynamic
conditions to produce the risk LABEL, keeping features and label from
leaking into each other.
"""
import itertools
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from app.services.geo_utils import haversine_km
from app.services.historical_baseline import expected_base_damage_rate, expected_base_delay_hours
from app.services.port_selector import _load_ports

RNG_SEED = 42

N_DARAT = 70
N_LAUT = 80
N_KOMBINASI = 50

DARAT_SPEED_KMH = 45.0
LAUT_SPEED_KMH = 16 * 1.852  # ~16 knot cargo ferry
PORT_DWELL_HOURS = 6.0  # per port call

OUTPUT_PATH = Path(__file__).resolve().parent / "synthetic_corridors.json"


@dataclass
class Corridor:
    corridor_id: str
    transport_mode: str
    distance_km: float
    wave_exposure_tier: str  # "None" for darat
    baseline_transit_hours: float
    base_delay_hours: float
    base_damage_rate: float


def _sample_exposure_tier(rng: np.random.Generator, distance_percentile: float) -> str:
    """Longer sea legs skew towards higher exposure tiers (more open-ocean
    crossing), but retain randomness so distance alone doesn't fully
    determine risk."""
    if distance_percentile < 0.33:
        weights = [0.5, 0.35, 0.15]
    elif distance_percentile < 0.66:
        weights = [0.3, 0.4, 0.3]
    else:
        weights = [0.15, 0.35, 0.5]
    return rng.choice(["Low", "Medium", "High"], p=weights)


def _base_delay_hours(rng: np.random.Generator, mode: str, distance_km: float, exposure_tier: str) -> float:
    noise = rng.normal(0, 2)
    return max(0.0, expected_base_delay_hours(mode, distance_km, exposure_tier) + noise)


def _base_damage_rate(rng: np.random.Generator, mode: str, distance_km: float, exposure_tier: str) -> float:
    noise = rng.beta(2, 20) * 0.1
    return float(np.clip(expected_base_damage_rate(mode, distance_km, exposure_tier) + noise, 0.0, 0.6))


def _build_sea_corridor(rng: np.random.Generator, corridor_id: str, sea_km: float, land_km: float, mode: str, percentile: float) -> Corridor:
    exposure_tier = _sample_exposure_tier(rng, percentile)
    distance_km = sea_km + land_km
    baseline_transit = land_km / DARAT_SPEED_KMH + sea_km / LAUT_SPEED_KMH + 2 * PORT_DWELL_HOURS
    return Corridor(
        corridor_id=corridor_id,
        transport_mode=mode,
        distance_km=round(distance_km, 1),
        wave_exposure_tier=exposure_tier,
        baseline_transit_hours=round(baseline_transit, 2),
        base_delay_hours=round(_base_delay_hours(rng, mode, distance_km, exposure_tier), 2),
        base_damage_rate=round(_base_damage_rate(rng, mode, distance_km, exposure_tier), 4),
    )


def build_corridors() -> list[Corridor]:
    rng = np.random.default_rng(RNG_SEED)
    ports = _load_ports()

    port_pairs = []
    for a, b in itertools.combinations(ports, 2):
        sea_km = haversine_km(a.lat, a.lon, b.lat, b.lon)
        port_pairs.append((a, b, sea_km))

    sea_kms_sorted = sorted(p[2] for p in port_pairs)

    def percentile_of(km: float) -> float:
        idx = np.searchsorted(sea_kms_sorted, km)
        return idx / len(sea_kms_sorted)

    corridors: list[Corridor] = []

    # --- darat corridors: lognormal distances, no sea exposure ---
    darat_distances = rng.lognormal(mean=np.log(250), sigma=0.7, size=N_DARAT)
    darat_distances = np.clip(darat_distances, 50, 1500)
    for i, dist in enumerate(darat_distances):
        baseline_transit = dist / DARAT_SPEED_KMH
        corridors.append(
            Corridor(
                corridor_id=f"darat-{i:03d}",
                transport_mode="darat",
                distance_km=round(float(dist), 1),
                wave_exposure_tier="None",
                baseline_transit_hours=round(baseline_transit, 2),
                base_delay_hours=round(_base_delay_hours(rng, "darat", dist, "None"), 2),
                base_damage_rate=round(_base_damage_rate(rng, "darat", dist, "None"), 4),
            )
        )

    # --- laut corridors: real port-pair sea distances (cross-island preferred) ---
    cross_group_pairs = [p for p in port_pairs if p[0].island_group != p[1].island_group]
    pool = cross_group_pairs if len(cross_group_pairs) >= N_LAUT else port_pairs
    chosen_idx = rng.choice(len(pool), size=min(N_LAUT, len(pool)), replace=False)
    for i, idx in enumerate(chosen_idx):
        a, b, sea_km = pool[idx]
        corridors.append(
            _build_sea_corridor(rng, f"laut-{i:03d}", sea_km, land_km=0.0, mode="laut", percentile=percentile_of(sea_km))
        )

    # --- kombinasi corridors: sea leg + small hinterland land legs on each end ---
    chosen_idx2 = rng.choice(len(pool), size=min(N_KOMBINASI, len(pool)), replace=False)
    for i, idx in enumerate(chosen_idx2):
        a, b, sea_km = pool[idx]
        land_km = float(rng.uniform(20, 180)) + float(rng.uniform(20, 180))
        corridors.append(
            _build_sea_corridor(
                rng, f"kombinasi-{i:03d}", sea_km, land_km=land_km, mode="kombinasi", percentile=percentile_of(sea_km)
            )
        )

    return corridors


def main() -> None:
    corridors = build_corridors()
    OUTPUT_PATH.write_text(json.dumps([asdict(c) for c in corridors], indent=2), encoding="utf-8")
    print(f"Wrote {len(corridors)} corridors to {OUTPUT_PATH}")
    modes = {}
    for c in corridors:
        modes[c.transport_mode] = modes.get(c.transport_mode, 0) + 1
    print("Mode breakdown:", modes)


if __name__ == "__main__":
    main()
