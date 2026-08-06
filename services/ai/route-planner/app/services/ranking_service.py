"""Runs the trained model over a shipment's enriched route candidates,
resolves FR-7's risk_probability/confidence_score fields, applies the
tau_high recall-guarantee override, flags extreme-condition candidates per
FR-6, and ranks + splits into recommended vs. alternative routes (FR-5)."""
import json
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.ml.feature_pipeline import ALL_INPUT_COLUMNS, CLASS_ORDER

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "model_pipeline.pkl"
METADATA_PATH = Path(__file__).resolve().parent.parent / "models" / "model_metadata.json"

HIGH_INDEX = CLASS_ORDER.index("High")
MEDIUM_INDEX = CLASS_ORDER.index("Medium")

EXTREME_WAVE_CATEGORIES = {"Tinggi", "Sangat Tinggi", "Ekstrem", "Sangat Ekstrem"}


@lru_cache(maxsize=1)
def _load_model() -> tuple:
    pipeline = joblib.load(MODEL_PATH)
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    return pipeline, metadata


def predict_risk(rows: pd.DataFrame) -> pd.DataFrame:
    pipeline, metadata = _load_model()
    tau_high = metadata["tau_high"]

    proba = pipeline.predict_proba(rows[ALL_INPUT_COLUMNS])
    argmax = proba.argmax(axis=1)
    overridden = np.where(proba[:, HIGH_INDEX] >= tau_high, HIGH_INDEX, argmax)

    return pd.DataFrame(
        {
            "risk_level": [CLASS_ORDER[i] for i in overridden],
            "risk_probability": proba[:, MEDIUM_INDEX] * 0.5 + proba[:, HIGH_INDEX] * 1.0,
            "confidence_score": proba.max(axis=1),
        }
    )


def _trigger_reason(row: pd.Series) -> str | None:
    is_extreme_wave = row["wave_category"] in EXTREME_WAVE_CATEGORIES
    is_port_at_risk = row["port_status_flag"] == 0
    if not (is_extreme_wave or is_port_at_risk):
        return None
    wave_slug = row["wave_category"].lower().replace(" ", "_")
    return f"gelombang_{wave_slug}_{row['route_id']}"


def rank_candidates(enriched_candidates: list[dict]) -> dict:
    """enriched_candidates: output of enrichment_service.enrich_all_candidates.
    Returns {"recommended_route": {...}, "alternative_routes": [{...}, ...]}
    matching PRD FR-7's response shape (plus a few extra internal fields the
    API layer can drop before serialization)."""
    df = pd.DataFrame(enriched_candidates)
    predictions = predict_risk(df)
    df = pd.concat([df.reset_index(drop=True), predictions.reset_index(drop=True)], axis=1)
    df["trigger_reason"] = df.apply(_trigger_reason, axis=1)

    # Ranked purely by estimated travel time -- risk_level/risk_probability and
    # trigger_reason are still computed and shown, but no longer affect
    # ordering (a deliberate product choice; this departs from PRD FR-5/FR-6's
    # risk-first ranking).
    df = df.sort_values(["estimated_duration_hours"]).reset_index(drop=True)

    from app.services.explanation_service import compute_explanations

    explanations = compute_explanations(df)
    df["risk_explanation_summary"] = [e["summary"] for e in explanations]
    df["risk_explanation_factors"] = [e["factors"] for e in explanations]

    records = df.to_dict("records")
    return {
        "recommended_route": records[0],
        "alternative_routes": records[1:],
    }
