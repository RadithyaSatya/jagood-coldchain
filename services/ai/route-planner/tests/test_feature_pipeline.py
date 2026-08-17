"""Guards the train/serve column contract described in feature_pipeline.py's
module docstring: training and serving must agree on exactly which columns
the model expects, or predict_risk's rows[ALL_INPUT_COLUMNS] lookup breaks --
the same failure mode that broke scripts/validate_scenarios.py."""
import json
from pathlib import Path

import pandas as pd

from app.ml.feature_pipeline import (
    ALL_INPUT_COLUMNS,
    CATEGORICAL_FEATURES,
    ENGINEERED_FEATURES,
    NUMERIC_FEATURES,
    add_interaction_features,
)


def test_all_input_columns_is_categorical_plus_numeric():
    assert ALL_INPUT_COLUMNS == CATEGORICAL_FEATURES + NUMERIC_FEATURES


def test_no_duplicate_or_overlapping_columns():
    assert len(ALL_INPUT_COLUMNS) == len(set(ALL_INPUT_COLUMNS))
    assert set(CATEGORICAL_FEATURES).isdisjoint(NUMERIC_FEATURES)


def test_saved_model_metadata_matches_serving_columns():
    metadata_path = Path(__file__).resolve().parent.parent / "app" / "models" / "model_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["feature_columns"] == ALL_INPUT_COLUMNS


def test_add_interaction_features_produces_engineered_columns():
    df = pd.DataFrame(
        {
            "commodity_type": ["Salmon Segar"],
            "wave_height_m": [2.0],
            "port_ambient_temp_c": [35.0],
            "max_cargo_temp_excess_c": [1.5],
        }
    )
    result = add_interaction_features(df)
    for col in ENGINEERED_FEATURES:
        assert col in result.columns


def test_add_interaction_features_does_not_mutate_input():
    df = pd.DataFrame(
        {
            "commodity_type": ["Salmon Segar"],
            "wave_height_m": [2.0],
            "port_ambient_temp_c": [35.0],
            "max_cargo_temp_excess_c": [1.5],
        }
    )
    original_columns = list(df.columns)
    add_interaction_features(df)
    assert list(df.columns) == original_columns
