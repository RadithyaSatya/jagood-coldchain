import pytest

from app.services import commodity_service


def test_list_commodities_returns_nonempty_list():
    commodities = commodity_service.list_commodities()
    assert len(commodities) > 0
    assert "commodity_type" in commodities[0]
    assert commodities[0]["provenance"]["record_classification"] == "REFERENCE"


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


def test_provenance_discloses_reference_sources_not_foodkeeper():
    """temp_ideal_*/shelf_life were cross-checked against public food-safety
    guidance (FDA/USDA/UC Davis/IDFA) and are REFERENCE-classified, but the
    dataset must still not claim FoodKeeper derivation, and the two fields with
    no public equivalent (delay_tolerance_hours, temp_sensitivity_level) must
    stay explicitly DEMO rather than being overclaimed as REFERENCE."""
    metadata = commodity_service.get_dataset_provenance()

    assert metadata["dataset"]["classification"] == "REFERENCE"
    assert metadata["dataset"]["foodkeeper_derived"] is False
    assert metadata["record_count"] == len(commodity_service.list_commodities())
    assert set(metadata["field_provenance"]) == commodity_service.REQUIRED_COMMODITY_FIELDS
    assert {source["classification"] for source in metadata["sources"]} == {"DEMO", "REFERENCE"}
    assert metadata["field_provenance"]["delay_tolerance_hours"]["classification"] == "DEMO"
    assert metadata["field_provenance"]["temp_sensitivity_level"]["classification"] == "DEMO"
    assert metadata["field_provenance"]["temp_ideal_min_c"]["classification"] == "REFERENCE"
    assert metadata["field_provenance"]["shelf_life_hours_at_ideal_temp"]["classification"] == "REFERENCE"


def test_every_commodity_and_field_has_resolvable_provenance():
    metadata = commodity_service.get_dataset_provenance()
    known_source_ids = {source["source_id"] for source in metadata["sources"]}

    for commodity in commodity_service.list_commodities():
        provenance = commodity["provenance"]
        assert set(provenance["source_ids"]).issubset(known_source_ids)
        assert set(provenance["fields"]) == commodity_service.REQUIRED_COMMODITY_FIELDS
        for field_metadata in provenance["fields"].values():
            assert field_metadata["classification"] in commodity_service.DATA_CLASSIFICATIONS
            assert set(field_metadata["source_ids"]).issubset(known_source_ids)
