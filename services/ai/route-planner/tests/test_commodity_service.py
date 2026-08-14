import pytest

from app.services import commodity_service


def test_list_commodities_returns_nonempty_list():
    commodities = commodity_service.list_commodities()
    assert len(commodities) > 0
    assert "commodity_type" in commodities[0]


def test_get_commodity_returns_known_commodity():
    commodities = commodity_service.list_commodities()
    known_type = commodities[0]["commodity_type"]
    assert commodity_service.get_commodity(known_type)["commodity_type"] == known_type


def test_get_commodity_raises_for_unknown_commodity():
    with pytest.raises(commodity_service.CommodityNotFoundError):
        commodity_service.get_commodity("Definitely Not A Real Commodity")


def test_temp_sensitivity_numeric_matches_known_levels():
    commodities = commodity_service.list_commodities()
    sample = commodities[0]
    expected = {"Low": 0.0, "Medium": 0.5, "High": 1.0}[sample["temp_sensitivity_level"]]
    assert commodity_service.temp_sensitivity_numeric(sample["commodity_type"]) == expected
