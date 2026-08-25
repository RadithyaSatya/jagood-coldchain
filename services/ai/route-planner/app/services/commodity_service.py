import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "commodity_database.json"
PROVENANCE_PATH = Path(__file__).resolve().parent.parent / "data" / "commodity_provenance.json"

TEMP_SENSITIVITY_NUMERIC = {"Low": 0.0, "Medium": 0.5, "High": 1.0}
DATA_CLASSIFICATIONS = {"REAL", "REFERENCE", "DERIVED", "SYNTHETIC", "DEMO"}
REQUIRED_COMMODITY_FIELDS = {
    "commodity_type",
    "temp_ideal_min_c",
    "temp_ideal_max_c",
    "shelf_life_hours_at_ideal_temp",
    "delay_tolerance_hours",
    "temp_sensitivity_level",
}


class CommodityNotFoundError(KeyError):
    pass


class CommodityProvenanceError(ValueError):
    pass


def _read_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_catalog() -> tuple[dict[str, dict], dict]:
    rows = _read_json(DATA_PATH)
    provenance = _read_json(PROVENANCE_PATH)
    row_names = {row["commodity_type"] for row in rows}
    record_provenance = provenance.get("records", {})

    if len(row_names) != len(rows):
        raise CommodityProvenanceError("Commodity names must be unique")
    if row_names != set(record_provenance):
        missing = sorted(row_names - set(record_provenance))
        orphaned = sorted(set(record_provenance) - row_names)
        raise CommodityProvenanceError(
            f"Commodity provenance coverage mismatch; missing={missing}, orphaned={orphaned}"
        )

    sources = provenance.get("sources", [])
    source_ids = {source.get("source_id") for source in sources}
    if None in source_ids or len(source_ids) != len(sources):
        raise CommodityProvenanceError("Commodity source IDs must be present and unique")
    for source in sources:
        if source.get("classification") not in DATA_CLASSIFICATIONS:
            raise CommodityProvenanceError(
                f"Commodity source {source['source_id']!r} has an invalid classification"
            )

    dataset_classification = provenance.get("dataset", {}).get("classification")
    if dataset_classification not in DATA_CLASSIFICATIONS:
        raise CommodityProvenanceError("Commodity dataset has an invalid classification")

    field_provenance = provenance.get("field_provenance", {})
    if set(field_provenance) != REQUIRED_COMMODITY_FIELDS:
        raise CommodityProvenanceError(
            "Every commodity field must have exactly one provenance declaration"
        )

    for field_name, field_metadata in field_provenance.items():
        _validate_provenance_entry(field_metadata, source_ids, f"field {field_name}")

    catalog: dict[str, dict] = {}
    for row in rows:
        commodity_type = row["commodity_type"]
        if set(row) != REQUIRED_COMMODITY_FIELDS:
            raise CommodityProvenanceError(
                f"Commodity {commodity_type!r} fields do not match the provenance schema"
            )
        record_metadata = record_provenance[commodity_type]
        _validate_provenance_entry(record_metadata, source_ids, f"record {commodity_type}")
        catalog[commodity_type] = {
            **row,
            "provenance": {
                "record_classification": record_metadata["classification"],
                "source_ids": record_metadata["source_ids"],
                "fields": field_provenance,
            },
        }

    return catalog, provenance


def _validate_provenance_entry(entry: dict, source_ids: set[str], label: str) -> None:
    if entry.get("classification") not in DATA_CLASSIFICATIONS:
        raise CommodityProvenanceError(f"Invalid classification for {label}")
    referenced_sources = entry.get("source_ids")
    if not referenced_sources or not set(referenced_sources).issubset(source_ids):
        raise CommodityProvenanceError(f"Unknown or missing source ID for {label}")


def list_commodities() -> list[dict]:
    catalog, _ = _load_catalog()
    return list(catalog.values())


def get_dataset_provenance() -> dict:
    catalog, provenance = _load_catalog()
    return {
        "schema_version": provenance["schema_version"],
        "dataset": provenance["dataset"],
        "sources": provenance["sources"],
        "field_provenance": provenance["field_provenance"],
        "record_count": len(catalog),
    }


def get_commodity(commodity_type: str) -> dict:
    commodities, _ = _load_catalog()
    if commodity_type not in commodities:
        raise CommodityNotFoundError(commodity_type)
    return commodities[commodity_type]


def temp_sensitivity_numeric(commodity_type: str) -> float:
    return TEMP_SENSITIVITY_NUMERIC[get_commodity(commodity_type)["temp_sensitivity_level"]]
