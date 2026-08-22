from app.services.weather_service import weathercode_to_condition


def test_weathercode_maps_each_severity_bucket():
    assert weathercode_to_condition(0) == "Cerah"
    assert weathercode_to_condition(2) == "Cerah Berawan"
    assert weathercode_to_condition(3) == "Berawan"
    assert weathercode_to_condition(45) == "Berawan Tebal"
    assert weathercode_to_condition(55) == "Hujan Ringan"
    assert weathercode_to_condition(61) == "Hujan Sedang"
    assert weathercode_to_condition(65) == "Hujan Lebat"
    assert weathercode_to_condition(95) == "Hujan Badai"


def test_weathercode_unknown_or_missing_falls_back_to_neutral_default():
    assert weathercode_to_condition(None) == "Berawan"
    assert weathercode_to_condition(9999) == "Berawan"
