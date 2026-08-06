"""Shared feature pipeline used identically by training (backend/training/train_model.py)
and serving (app/services/ranking_service.py) so the one-hot/interaction encoding can
never drift between the two -- the single biggest source of silent train/serve bugs
in a project like this."""
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder
from xgboost import XGBClassifier

from app.services.commodity_service import temp_sensitivity_numeric

CLASS_ORDER = ["Low", "Medium", "High"]
CLASS_TO_INDEX = {c: i for i, c in enumerate(CLASS_ORDER)}

CATEGORICAL_FEATURES = ["commodity_type", "transport_mode", "weather_condition", "wave_category", "cold_chain_equipment"]
NUMERIC_FEATURES = [
    "commodity_temp_ideal_c",
    "commodity_shelf_life_hours",
    "commodity_delay_tolerance_hours",
    "distance_km",
    "estimated_duration_hours",
    "wave_height_m",
    "wind_speed_kmh",
    "port_status_flag",
    "historical_delay_avg_hours",
    "historical_damage_rate",
    "departure_hour",
    "port_ambient_temp_c",
    "max_cargo_temp_excess_c",
]
ENGINEERED_FEATURES = ["wave_temp_interaction", "port_temp_interaction", "cold_chain_temp_interaction"]

# Ambient temp at a port only matters once it's unusually hot enough to start
# stressing reefer/equipment reliability -- not the commodity's own ideal
# setpoint (which would make frozen goods max out this term regardless of
# real conditions). See services/enrichment_service.py's PORT_AMBIENT_TEMP_DEFAULT_C.
PORT_HEAT_STRESS_THRESHOLD_C = 33.0

ALL_INPUT_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES

DEFAULT_XGB_PARAMS = dict(
    objective="multi:softprob",
    num_class=len(CLASS_ORDER),
    eval_metric="mlogloss",
    max_depth=5,
    n_estimators=300,
    learning_rate=0.08,
    subsample=0.9,
    colsample_bytree=0.9,
    random_state=42,
)


def add_interaction_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    sensitivity = df["commodity_type"].map(temp_sensitivity_numeric)
    df["wave_temp_interaction"] = df["wave_height_m"] * sensitivity
    port_heat_stress = (df["port_ambient_temp_c"] - PORT_HEAT_STRESS_THRESHOLD_C).clip(lower=0)
    df["port_temp_interaction"] = port_heat_stress * sensitivity
    df["cold_chain_temp_interaction"] = df["max_cargo_temp_excess_c"] * sensitivity
    return df


def build_pipeline(xgb_params: dict | None = None) -> Pipeline:
    column_transformer = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("num", "passthrough", NUMERIC_FEATURES + ENGINEERED_FEATURES),
        ]
    )
    return Pipeline(
        steps=[
            ("add_interaction", FunctionTransformer(add_interaction_features)),
            ("preprocess", column_transformer),
            ("clf", XGBClassifier(**(xgb_params or DEFAULT_XGB_PARAMS))),
        ]
    )


def encode_labels(risk_levels: pd.Series) -> pd.Series:
    return risk_levels.map(CLASS_TO_INDEX)
