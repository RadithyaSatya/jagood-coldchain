"""Layer B of the synthetic data pipeline: samples dated shipments on top of
each corridor from synthetic_corridors.py. Feature columns
(historical_delay_avg_hours/historical_damage_rate) copy the corridor's
stable Layer-A baseline; the risk_level LABEL combines that baseline with
each shipment's own dynamic conditions (wave height, weather, commodity
sensitivity vs. this shipment's delay). Noise is injected into the
continuous drivers upstream (wave sampling, delay noise, damage-rate beta
noise) rather than by flipping final labels, so the model has a real,
non-trivial decision boundary to learn instead of a lookup table.
"""
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.feature_pipeline import PORT_HEAT_STRESS_THRESHOLD_C  # noqa: E402
from app.services.commodity_service import list_commodities, temp_sensitivity_numeric  # noqa: E402
from app.services.enrichment_service import PORT_AMBIENT_TEMP_DEFAULT_C  # noqa: E402
from app.services.temperature_service import (  # noqa: E402
    INSULATION_K_PER_HOUR,
    simulate_cargo_temperature,
    synthetic_ambient_temp_c,
)

COLD_CHAIN_EQUIPMENT_OPTIONS = ["reefer", "pasif"]
COLD_CHAIN_EQUIPMENT_WEIGHTS = [0.7, 0.3]
INSULATION_QUALITY_OPTIONS = ["baik", "sedang", "buruk"]
CARGO_TEMP_SAMPLE_POINTS = 6

CORRIDORS_PATH = Path(__file__).resolve().parent / "synthetic_corridors.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "synthetic_historical.csv"

RNG_SEED = 7
MIN_SHIPMENTS_PER_CORRIDOR = 40
MAX_SHIPMENTS_PER_CORRIDOR = 100
TIMELINE_MONTHS = 24
TIMELINE_END = pd.Timestamp("2026-08-05")

WAVE_CATEGORY_BUCKETS = [
    (0.5, "Tenang"),
    (1.25, "Rendah"),
    (2.5, "Sedang"),
    (4.0, "Tinggi"),
    (6.0, "Sangat Tinggi"),
    (9.0, "Ekstrem"),
    (float("inf"), "Sangat Ekstrem"),
]
WAVE_CATEGORY_ORDER = ["Tenang", "Rendah", "Sedang", "Tinggi", "Sangat Tinggi", "Ekstrem", "Sangat Ekstrem"]
EXTREME_WAVE_CATEGORIES = {"Tinggi", "Sangat Tinggi", "Ekstrem", "Sangat Ekstrem"}

WAVE_GAMMA_PARAMS = {
    "Low": (2.0, 0.4),
    "Medium": (2.0, 0.9),
    "High": (2.2, 1.6),
}

SEA_WEATHER_BY_WAVE_CAT = {
    "Tenang": {"Cerah": 0.4, "Cerah Berawan": 0.3, "Berawan": 0.3},
    "Rendah": {"Cerah": 0.35, "Cerah Berawan": 0.35, "Berawan": 0.3},
    "Sedang": {"Berawan": 0.4, "Cerah Berawan": 0.3, "Hujan Ringan": 0.3},
    "Tinggi": {"Hujan Sedang": 0.35, "Berawan Tebal": 0.35, "Hujan Lebat": 0.3},
    "Sangat Tinggi": {"Hujan Lebat": 0.4, "Hujan Badai": 0.3, "Berawan Tebal": 0.3},
    "Ekstrem": {"Hujan Badai": 0.5, "Hujan Lebat": 0.5},
    "Sangat Ekstrem": {"Hujan Badai": 0.6, "Hujan Lebat": 0.4},
}
LAND_WEATHER_DIST = {"Cerah": 0.35, "Cerah Berawan": 0.3, "Berawan": 0.2, "Hujan Ringan": 0.1, "Hujan Sedang": 0.05}

CONDITION_DELAY_BONUS = {
    "Tenang": 0.0,
    "Rendah": 0.0,
    "Sedang": 1.0,
    "Tinggi": 4.0,
    "Sangat Tinggi": 9.0,
    "Ekstrem": 16.0,
    "Sangat Ekstrem": 16.0,
}


def monsoon_factor(month: int) -> float:
    if month in (12, 1, 2):
        return 1.3
    if month in (6, 7, 8):
        return 1.15
    return 1.0


def bucket_wave_height(height_m: float) -> str:
    for threshold, category in WAVE_CATEGORY_BUCKETS:
        if height_m < threshold:
            return category
    return "Sangat Ekstrem"


def sample_weather(rng: np.random.Generator, dist: dict[str, float]) -> str:
    options = list(dist.keys())
    weights = list(dist.values())
    return rng.choice(options, p=np.array(weights) / sum(weights))


@dataclass
class Corridor:
    corridor_id: str
    transport_mode: str
    distance_km: float
    wave_exposure_tier: str
    baseline_transit_hours: float
    base_delay_hours: float
    base_damage_rate: float


def load_corridors() -> list[Corridor]:
    rows = json.loads(CORRIDORS_PATH.read_text(encoding="utf-8"))
    return [Corridor(**row) for row in rows]


def generate_rows(rng: np.random.Generator, corridors: list[Corridor], commodities: list[dict]) -> list[dict]:
    rows = []
    shipment_seq = 0
    start = TIMELINE_END - pd.DateOffset(months=TIMELINE_MONTHS)

    for corridor in corridors:
        n_shipments = rng.integers(MIN_SHIPMENTS_PER_CORRIDOR, MAX_SHIPMENTS_PER_CORRIDOR + 1)
        is_sea_exposed = corridor.transport_mode in ("laut", "kombinasi")

        for _ in range(n_shipments):
            shipment_seq += 1
            commodity = commodities[rng.integers(0, len(commodities))]
            temp_sensitivity = commodity["temp_sensitivity_level"]
            temp_sensitivity_weight = temp_sensitivity_numeric(commodity["commodity_type"])
            commodity_temp_ideal_c = (commodity["temp_ideal_min_c"] + commodity["temp_ideal_max_c"]) / 2

            offset_days = int(rng.integers(0, TIMELINE_MONTHS * 30))
            shipment_date = start + pd.Timedelta(days=offset_days)
            departure_hour = int(rng.integers(0, 24))

            cold_chain_equipment = rng.choice(COLD_CHAIN_EQUIPMENT_OPTIONS, p=COLD_CHAIN_EQUIPMENT_WEIGHTS)
            insulation_quality = (
                rng.choice(INSULATION_QUALITY_OPTIONS) if cold_chain_equipment == "pasif" else "sedang"
            )

            if is_sea_exposed:
                shape, scale = WAVE_GAMMA_PARAMS[corridor.wave_exposure_tier]
                wave_height_m = rng.gamma(shape, scale) * monsoon_factor(shipment_date.month)
                wave_category = bucket_wave_height(wave_height_m)
                weather_condition = sample_weather(rng, SEA_WEATHER_BY_WAVE_CAT[wave_category])
                wind_speed_kmh = float(np.clip(wave_height_m * 10 + rng.normal(0, 5), 5, 110))
                port_status_flag = 0 if wave_category in EXTREME_WAVE_CATEGORIES else 1
                # Port stop -- worst-case (hottest) of embark/disembark, mirroring
                # enrichment_service._resolve_port_ambient_temp_c at serving time.
                port_ambient_temp_c = float(np.clip(rng.normal(29, 3), 22, 38))
            else:
                wave_height_m = 0.0
                wave_category = "Tenang"
                weather_condition = sample_weather(rng, LAND_WEATHER_DIST)
                wind_speed_kmh = float(np.clip(rng.normal(15, 8), 5, 60))
                port_status_flag = 1
                port_ambient_temp_c = PORT_AMBIENT_TEMP_DEFAULT_C

            estimated_duration_hours = max(
                0.5, corridor.baseline_transit_hours * (1 + rng.normal(0, 0.05))
            )

            shipment_delay_hours = max(
                0.0,
                corridor.base_delay_hours
                + CONDITION_DELAY_BONUS[wave_category]
                + (3.0 if "Badai" in weather_condition else 0.0)
                + rng.normal(0, 1.5),
            )

            wave_severity_score = WAVE_CATEGORY_ORDER.index(wave_category) / (len(WAVE_CATEGORY_ORDER) - 1)
            port_heat_stress = max(0.0, port_ambient_temp_c - PORT_HEAT_STRESS_THRESHOLD_C) / 10.0

            if cold_chain_equipment == "pasif":
                # Without active refrigeration, cargo is exposed to ambient heat for
                # the *whole* transit (not just the delayed portion) -- simulate the
                # same physics enrichment_service._resolve_cargo_temperature uses at
                # serving time, over a synthetic ambient profile (no live API calls
                # for 14k+ synthetic rows).
                total_transit_hours = estimated_duration_hours + shipment_delay_hours
                n = CARGO_TEMP_SAMPLE_POINTS
                ambient_samples = [
                    (
                        total_transit_hours * i / max(1, n - 1),
                        synthetic_ambient_temp_c(
                            shipment_date.month, (departure_hour + total_transit_hours * i / max(1, n - 1)) % 24
                        ),
                    )
                    for i in range(n)
                ]
                sim = simulate_cargo_temperature(
                    initial_temp_c=commodity_temp_ideal_c,
                    ambient_samples=ambient_samples,
                    total_duration_hours=total_transit_hours,
                    ideal_c=commodity_temp_ideal_c,
                    k_per_hour=INSULATION_K_PER_HOUR[insulation_quality],
                )
                max_cargo_temp_c = sim["max_cargo_temp_c"]
                effective_consumed_hours = sim["effective_consumed_hours"]
            else:
                max_cargo_temp_c = commodity_temp_ideal_c
                effective_consumed_hours = shipment_delay_hours

            max_cargo_temp_excess_c = round(max(0.0, max_cargo_temp_c - commodity_temp_ideal_c), 2)
            shelf_life_ratio = min(1.0, effective_consumed_hours / commodity["shelf_life_hours_at_ideal_temp"])
            temp_excess_score = min(1.0, max_cargo_temp_excess_c / 20.0)

            shipment_damage_rate = float(
                np.clip(
                    corridor.base_damage_rate
                    + 0.15 * temp_sensitivity_weight * shelf_life_ratio
                    + 0.10 * wave_severity_score
                    + 0.08 * temp_sensitivity_weight * port_heat_stress
                    + 0.25 * temp_sensitivity_weight * temp_excess_score
                    + rng.beta(2, 20) * 0.3,
                    0.0,
                    0.95,
                )
            )

            delay_tolerance_ratio = min(1.0, shipment_delay_hours / commodity["delay_tolerance_hours"])
            risk_score = (
                40 * min(1.0, shipment_damage_rate / 0.5)
                + 30 * delay_tolerance_ratio
                + 20 * wave_severity_score
                + 10 * (1 - port_status_flag)
            )

            rows.append(
                {
                    "shipment_id": f"synthetic-{shipment_seq:06d}",
                    "route_id": corridor.corridor_id,
                    "synthetic_shipment_date": shipment_date.strftime("%Y-%m-%d"),
                    "commodity_type": commodity["commodity_type"],
                    "commodity_temp_ideal_c": commodity_temp_ideal_c,
                    "commodity_shelf_life_hours": commodity["shelf_life_hours_at_ideal_temp"],
                    "commodity_delay_tolerance_hours": commodity["delay_tolerance_hours"],
                    "transport_mode": corridor.transport_mode,
                    "distance_km": corridor.distance_km,
                    "estimated_duration_hours": round(estimated_duration_hours, 2),
                    "expected_delay_hours": round(shipment_delay_hours, 2),
                    "wave_height_m": round(wave_height_m, 3),
                    "wave_category": wave_category,
                    "wind_speed_kmh": round(wind_speed_kmh, 2),
                    "weather_condition": weather_condition,
                    "port_status_flag": port_status_flag,
                    "port_ambient_temp_c": round(port_ambient_temp_c, 2),
                    "cold_chain_equipment": cold_chain_equipment,
                    "max_cargo_temp_excess_c": max_cargo_temp_excess_c,
                    "historical_delay_avg_hours": corridor.base_delay_hours,
                    "historical_damage_rate": corridor.base_damage_rate,
                    "departure_hour": departure_hour,
                    "risk_score": round(risk_score, 2),
                }
            )

    return rows


def assign_risk_level(df: pd.DataFrame, low_threshold: float = 62.1, high_threshold: float = 77.2) -> pd.DataFrame:
    def label(score: float) -> str:
        if score < low_threshold:
            return "Low"
        if score < high_threshold:
            return "Medium"
        return "High"

    df["risk_level"] = df["risk_score"].apply(label)
    return df


def main() -> None:
    rng = np.random.default_rng(RNG_SEED)
    corridors = load_corridors()
    commodities = list_commodities()

    rows = generate_rows(rng, corridors, commodities)
    df = pd.DataFrame(rows)
    df = assign_risk_level(df)
    df = df.sort_values("synthetic_shipment_date").reset_index(drop=True)

    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Wrote {len(df)} synthetic shipments to {OUTPUT_PATH}")
    print("Class balance:\n", df["risk_level"].value_counts(normalize=True).round(3))
    print("Date range:", df["synthetic_shipment_date"].min(), "to", df["synthetic_shipment_date"].max())


if __name__ == "__main__":
    main()
