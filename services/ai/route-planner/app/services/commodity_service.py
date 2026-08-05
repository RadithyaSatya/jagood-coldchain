import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "commodity_database.json"

TEMP_SENSITIVITY_NUMERIC = {"Low": 0.0, "Medium": 0.5, "High": 1.0}


class CommodityNotFoundError(KeyError):
    pass


@lru_cache(maxsize=1)
def _load_commodities() -> dict[str, dict]:
    with open(DATA_PATH, encoding="utf-8") as f:
        rows = json.load(f)
    return {row["commodity_type"]: row for row in rows}


def list_commodities() -> list[dict]:
    return list(_load_commodities().values())


def get_commodity(commodity_type: str) -> dict:
    commodities = _load_commodities()
    if commodity_type not in commodities:
        raise CommodityNotFoundError(commodity_type)
    return commodities[commodity_type]


def temp_sensitivity_numeric(commodity_type: str) -> float:
    return TEMP_SENSITIVITY_NUMERIC[get_commodity(commodity_type)["temp_sensitivity_level"]]
