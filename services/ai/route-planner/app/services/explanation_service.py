"""Per-route explainability (PRD FR-8): uses SHAP to attribute each route's
risk_probability (P(Medium)*0.5 + P(High)*1.0 -- the same metric ranking_service
sorts by) to the specific feature values of that route, then renders the top
contributors as short Indonesian sentences.

SHAP values here are computed in the model's raw margin (pre-softmax) space
and combined with the same 0.5/1.0 weights as risk_probability. That's an
approximation -- margin-space contributions don't sum linearly into a
probability-space metric the way they do in margin space itself -- but it is
the standard, practical way to rank *which* features drove a multi-class
tree model's prediction in which direction, which is what this is for
(qualitative explanation, not a rigorous probability decomposition)."""
from functools import lru_cache

import numpy as np
import pandas as pd
import shap

from app.ml.feature_pipeline import ALL_INPUT_COLUMNS, CATEGORICAL_FEATURES, CLASS_ORDER
from app.services.ranking_service import _load_model

MEDIUM_INDEX = CLASS_ORDER.index("Medium")
HIGH_INDEX = CLASS_ORDER.index("High")

TOP_N_FACTORS = 3

MODE_LABELS = {"darat": "darat", "laut": "laut", "kombinasi": "kombinasi (darat + laut)"}


def _describe(column: str, value) -> str:
    if column == "wave_category":
        return f'Kondisi gelombang laut "{value}"'
    if column == "weather_condition":
        return f'Kondisi cuaca "{value}"'
    if column == "transport_mode":
        return f"Moda transportasi {MODE_LABELS.get(value, value)}"
    if column == "commodity_type":
        return f"Komoditas {value}"
    if column == "port_status_flag":
        return "Status pelabuhan normal" if value == 1 else "Status pelabuhan berisiko tertutup"
    if column == "historical_damage_rate":
        return f"Riwayat tingkat kerusakan rute serupa ({value * 100:.0f}%)"
    if column == "historical_delay_avg_hours":
        return f"Estimasi keterlambatan tipikal rute ini ({value:.1f} jam)"
    if column == "distance_km":
        return f"Jarak tempuh ({value:.0f} km)"
    if column == "estimated_duration_hours":
        return f"Estimasi durasi perjalanan ({value:.1f} jam)"
    if column == "expected_delay_hours":
        return f"Perkiraan keterlambatan tambahan ({value:.1f} jam)"
    if column == "wave_height_m":
        return f"Tinggi gelombang ({value:.2f} m)"
    if column == "wind_speed_kmh":
        return f"Kecepatan angin ({value:.0f} km/j)"
    if column == "port_ambient_temp_c":
        return f"Suhu udara di pelabuhan ({value:.1f}°C)"
    if column == "commodity_temp_ideal_c":
        return f"Suhu ideal komoditas ({value:.1f}°C)"
    if column == "commodity_shelf_life_hours":
        return f"Umur simpan komoditas ({value:.0f} jam)"
    if column == "commodity_delay_tolerance_hours":
        return f"Toleransi keterlambatan komoditas ({value:.0f} jam)"
    if column == "departure_hour":
        return f"Jam keberangkatan ({int(value):02d}:00)"
    if column == "wave_temp_interaction":
        return "Kombinasi gelombang tinggi dengan komoditas sensitif suhu"
    if column == "port_temp_interaction":
        return "Kombinasi suhu pelabuhan panas dengan komoditas sensitif suhu"
    if column == "cold_chain_equipment":
        return "Pengiriman tanpa reefer (suhu kargo mengikuti suhu udara)" if value == "pasif" else "Pengiriman dengan reefer aktif"
    if column == "max_cargo_temp_excess_c":
        return f"Suhu kargo simulasi melebihi suhu ideal hingga {value:.1f}°C"
    if column == "cold_chain_temp_interaction":
        return "Kombinasi suhu kargo yang naik (tanpa reefer) dengan komoditas sensitif suhu"
    return column


def _column_for_transformed_feature(feature_name: str) -> str:
    """'cat__wave_category_Tinggi' -> 'wave_category'; 'num__distance_km' -> 'distance_km'."""
    if feature_name.startswith("cat__"):
        stripped = feature_name[len("cat__") :]
        for col in CATEGORICAL_FEATURES:
            if stripped.startswith(col + "_"):
                return col
        return stripped
    if feature_name.startswith("num__"):
        return feature_name[len("num__") :]
    return feature_name


@lru_cache(maxsize=1)
def _get_explainer_and_columns() -> tuple:
    pipeline, _ = _load_model()
    clf = pipeline.named_steps["clf"]
    transformed_columns = pipeline.named_steps["preprocess"].get_feature_names_out()
    original_columns = [_column_for_transformed_feature(f) for f in transformed_columns]
    return shap.TreeExplainer(clf), original_columns


def compute_explanations(df: pd.DataFrame) -> list[dict]:
    """df: the same enriched-candidate rows ranking_service scores (must
    contain ALL_INPUT_COLUMNS). Returns one explanation dict per row, in the
    same order, each {"summary": str, "factors": [{"factor", "effect", "impact"}]}."""
    pipeline, _ = _load_model()
    explainer, original_columns = _get_explainer_and_columns()

    X = df[ALL_INPUT_COLUMNS]
    X_interact = pipeline.named_steps["add_interaction"].transform(X)
    X_transformed = pipeline.named_steps["preprocess"].transform(X_interact)

    shap_values = explainer.shap_values(X_transformed)
    combined = 0.5 * shap_values[:, :, MEDIUM_INDEX] + 1.0 * shap_values[:, :, HIGH_INDEX]

    results = []
    for i in range(len(df)):
        row = X_interact.iloc[i]
        contributions: dict[str, float] = {}
        for col, val in zip(original_columns, combined[i]):
            contributions[col] = contributions.get(col, 0.0) + float(val)

        ranked = sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)[:TOP_N_FACTORS]
        factors = [
            {
                "factor": _describe(col, row.get(col)),
                "effect": "menaikkan" if impact > 0 else "menurunkan",
                "impact": round(abs(impact), 4),
            }
            for col, impact in ranked
            if abs(impact) > 1e-6
        ]

        risk_level = df["risk_level"].iloc[i]
        results.append({"summary": _build_summary(risk_level, factors), "factors": factors})

    return results


def _build_summary(risk_level: str, factors: list[dict]) -> str:
    """factors is already sorted by absolute impact, descending -- the lead
    sentence must follow that ordering (the single biggest contributor),
    not group by direction first, otherwise a merely-secondary "increases
    risk" factor could get billed as the main reason ahead of a
    larger-magnitude "decreases risk" one."""
    risk_label = {"Low": "Rendah", "Medium": "Sedang", "High": "Tinggi"}.get(risk_level, risk_level)
    if not factors:
        return f"Risiko {risk_label}."

    top = factors[0]
    if top["effect"] == "menaikkan":
        sentence = f"Risiko {risk_label} terutama karena {top['factor'].lower()}"
    else:
        sentence = f"Risiko {risk_label} lebih terkendali karena {top['factor'].lower()}"

    opposite = next((f for f in factors[1:] if f["effect"] != top["effect"]), None)
    if opposite:
        if opposite["effect"] == "menurunkan":
            sentence += f", meski {opposite['factor'].lower()} membantu menurunkannya"
        else:
            sentence += f", namun {opposite['factor'].lower()} tetap menaikkannya"

    return sentence + "."
