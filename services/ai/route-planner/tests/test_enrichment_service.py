from app.services.enrichment_service import _quality_status


def test_quality_status_baik_at_and_above_70_percent():
    assert _quality_status(100.0) == "Baik"
    assert _quality_status(70.0) == "Baik"


def test_quality_status_menurun_between_30_and_70_percent():
    assert _quality_status(69.9) == "Menurun"
    assert _quality_status(30.0) == "Menurun"


def test_quality_status_kritis_below_30_percent():
    assert _quality_status(29.9) == "Kritis"
    assert _quality_status(0.0) == "Kritis"
