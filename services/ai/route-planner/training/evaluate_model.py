"""Independent evaluation of the saved model_pipeline.pkl on the held-out
chronological test split. This is the true out-of-sample gate: recall_High
must be >= the target stored in model_metadata.json (tuned only on the
validation slice in train_model.py, never touched during training)."""
import json
import sys
from pathlib import Path

import joblib
from sklearn.metrics import classification_report, confusion_matrix

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.feature_pipeline import ALL_INPUT_COLUMNS, CLASS_ORDER, encode_labels  # noqa: E402
from training.train_model import HIGH_CLASS_INDEX, load_and_split, predict_with_override  # noqa: E402

MODEL_PATH = Path(__file__).resolve().parent.parent / "app" / "models" / "model_pipeline.pkl"
METADATA_PATH = Path(__file__).resolve().parent.parent / "app" / "models" / "model_metadata.json"


def main() -> None:
    pipeline = joblib.load(MODEL_PATH)
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    tau_high = metadata["tau_high"]
    target_recall_high = metadata["target_recall_high"]

    _, _, test = load_and_split()
    X_test = test[ALL_INPUT_COLUMNS]
    y_test = encode_labels(test["risk_level"]).to_numpy()

    y_pred = predict_with_override(pipeline, X_test, tau_high)

    print(f"Test set size: {len(test)}  (date range {test['synthetic_shipment_date'].min()} .. {test['synthetic_shipment_date'].max()})")
    print(f"tau_high = {tau_high:.4f}\n")

    print("Classification report (rows=true, with tau_high override applied):")
    print(classification_report(y_test, y_pred, target_names=CLASS_ORDER, digits=3))

    cm = confusion_matrix(y_test, y_pred)
    print("Confusion matrix (rows=true, cols=predicted), order =", CLASS_ORDER)
    print(cm)

    recall_high = ((y_pred == HIGH_CLASS_INDEX) & (y_test == HIGH_CLASS_INDEX)).sum() / max(
        1, (y_test == HIGH_CLASS_INDEX).sum()
    )
    print(f"\nrecall_High on held-out test set = {recall_high:.3f} (target >= {target_recall_high})")
    if recall_high >= target_recall_high:
        print("PASS: recall_High target met.")
    else:
        print("FAIL: recall_High below target -- revisit risk_score weights/noise in generate_synthetic_data.py.")
        sys.exit(1)


if __name__ == "__main__":
    main()
