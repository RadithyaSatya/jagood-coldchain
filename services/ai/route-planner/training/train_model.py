"""Trains the XGBoost route-risk classifier on synthetic_historical.csv using
a chronological (not random) split, since the PRD requires evaluating on the
"most recent" slice to simulate a real production deployment cadence.

Recall on the "High" class is the headline metric (false negatives on High
are the costly error for cold-chain risk) -- sample weights upweight High,
and a decision threshold tau_high is tuned on a validation slice (carved from
inside the training period) to guarantee recall_High >= 0.80 before ever
touching the held-out test set.
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve
from sklearn.utils.class_weight import compute_sample_weight

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.feature_pipeline import ALL_INPUT_COLUMNS, CLASS_ORDER, build_pipeline, encode_labels  # noqa: E402

DATA_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "synthetic_historical.csv"
MODEL_PATH = Path(__file__).resolve().parent.parent / "app" / "models" / "model_pipeline.pkl"
METADATA_PATH = Path(__file__).resolve().parent.parent / "app" / "models" / "model_metadata.json"

HIGH_CLASS_INDEX = CLASS_ORDER.index("High")
HIGH_UPWEIGHT = 1.75
TARGET_RECALL_HIGH = 0.80

TRAIN_FRACTION = 0.80
VALIDATION_FRACTION_OF_TRAIN = 0.15


def load_and_split(csv_path: Path = DATA_PATH) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(csv_path, parse_dates=["synthetic_shipment_date"])
    df = df.sort_values("synthetic_shipment_date").reset_index(drop=True)

    n = len(df)
    train_end = int(n * TRAIN_FRACTION)
    train_full = df.iloc[:train_end]
    test = df.iloc[train_end:]

    val_start = int(len(train_full) * (1 - VALIDATION_FRACTION_OF_TRAIN))
    train = train_full.iloc[:val_start]
    val = train_full.iloc[val_start:]

    return train, val, test


def compute_sample_weights(y_encoded: np.ndarray) -> np.ndarray:
    balanced = compute_sample_weight("balanced", y_encoded)
    upweight = np.where(y_encoded == HIGH_CLASS_INDEX, HIGH_UPWEIGHT, 1.0)
    return balanced * upweight


def tune_tau_high(y_true_encoded: np.ndarray, proba_high: np.ndarray, target_recall: float = TARGET_RECALL_HIGH) -> float:
    y_is_high = (y_true_encoded == HIGH_CLASS_INDEX).astype(int)
    precision, recall, thresholds = precision_recall_curve(y_is_high, proba_high)
    # precision/recall have one more element than thresholds; align them.
    precision, recall = precision[:-1], recall[:-1]
    eligible = [(t, p) for t, r, p in zip(thresholds, recall, precision) if r >= target_recall]
    if not eligible:
        return 0.0  # can't hit target recall even at threshold 0 -- fall back to argmax only
    # pick the highest threshold (best precision) among those still satisfying recall target
    return max(eligible, key=lambda tp: tp[0])[0]


def predict_with_override(pipeline, X: pd.DataFrame, tau_high: float) -> np.ndarray:
    proba = pipeline.predict_proba(X)
    argmax = proba.argmax(axis=1)
    proba_high = proba[:, HIGH_CLASS_INDEX]
    overridden = np.where(proba_high >= tau_high, HIGH_CLASS_INDEX, argmax)
    return overridden


def main() -> None:
    train, val, test = load_and_split()
    print(f"train={len(train)} val={len(val)} test={len(test)}")

    X_train, y_train = train[ALL_INPUT_COLUMNS], encode_labels(train["risk_level"]).to_numpy()
    X_val, y_val = val[ALL_INPUT_COLUMNS], encode_labels(val["risk_level"]).to_numpy()

    sample_weight = compute_sample_weights(y_train)

    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train, clf__sample_weight=sample_weight)

    val_proba = pipeline.predict_proba(X_val)
    tau_high = tune_tau_high(y_val, val_proba[:, HIGH_CLASS_INDEX])
    print(f"tuned tau_high = {tau_high:.4f}")

    val_pred = predict_with_override(pipeline, X_val, tau_high)
    val_recall_high = ((val_pred == HIGH_CLASS_INDEX) & (y_val == HIGH_CLASS_INDEX)).sum() / max(
        1, (y_val == HIGH_CLASS_INDEX).sum()
    )
    print(f"validation recall_High (with override) = {val_recall_high:.3f}")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)

    metadata = {
        "feature_columns": ALL_INPUT_COLUMNS,
        "class_order": CLASS_ORDER,
        "tau_high": float(tau_high),
        "high_upweight": HIGH_UPWEIGHT,
        "target_recall_high": TARGET_RECALL_HIGH,
        "validation_recall_high": float(val_recall_high),
        "train_rows": len(train),
        "val_rows": len(val),
        "test_rows": len(test),
        "train_date_range": [str(train["synthetic_shipment_date"].min()), str(train["synthetic_shipment_date"].max())],
        "test_date_range": [str(test["synthetic_shipment_date"].min()), str(test["synthetic_shipment_date"].max())],
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved model to {MODEL_PATH}")
    print(f"Saved metadata to {METADATA_PATH}")


if __name__ == "__main__":
    main()
