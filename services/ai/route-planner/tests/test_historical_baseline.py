import asyncio
import datetime as dt

from app.services import historical_baseline as hb


def test_weather_severity_mapping():
    assert hb._weather_severity("Cerah") == "normal"
    assert hb._weather_severity("Berawan Tebal") == "hujan_ringan"
    assert hb._weather_severity("Hujan Sedang") == "hujan_lebat"
    assert hb._weather_severity("Hujan Badai") == "badai"
    assert hb._weather_severity("Unknown Condition") == "normal"


def test_estimate_weather_delay_hours_uses_bootstrap_when_no_stats(monkeypatch):
    monkeypatch.setattr(hb.db, "get_weather_delay_stats", lambda mode, severity: None)
    hours, quality = hb.estimate_weather_delay_hours("darat", "Hujan Lebat")
    assert quality == "bootstrap"
    assert hours == hb.WEATHER_DELAY_BOOTSTRAP_HOURS["hujan_lebat"]


def test_estimate_weather_delay_hours_stays_bootstrap_below_min_samples(monkeypatch):
    monkeypatch.setattr(
        hb.db,
        "get_weather_delay_stats",
        lambda mode, severity: {"sample_count": hb.MIN_SAMPLES_FOR_WEATHER_BLEND - 1, "delay_hours_sum": 99.0},
    )
    hours, quality = hb.estimate_weather_delay_hours("darat", "Hujan Lebat")
    assert quality == "bootstrap"
    assert hours == hb.WEATHER_DELAY_BOOTSTRAP_HOURS["hujan_lebat"]


def test_estimate_weather_delay_hours_blends_toward_real_average_once_enough_samples(monkeypatch):
    monkeypatch.setattr(
        hb.db,
        "get_weather_delay_stats",
        lambda mode, severity: {"sample_count": hb.FULL_TRUST_WEATHER_SAMPLES, "delay_hours_sum": 20.0},
    )
    hours, quality = hb.estimate_weather_delay_hours("darat", "Hujan Lebat")
    assert quality == "learned"
    assert hours == 1.0  # full trust at FULL_TRUST_WEATHER_SAMPLES: real_avg = 20/20 = 1.0


def test_estimate_weather_delay_hours_falls_back_to_bootstrap_on_db_error(monkeypatch):
    def raise_error(mode, severity):
        raise RuntimeError("no db")

    monkeypatch.setattr(hb.db, "get_weather_delay_stats", raise_error)
    hours, quality = hb.estimate_weather_delay_hours("darat", "Cerah")
    assert quality == "bootstrap"
    assert hours == 0.0


def test_nominal_speed_kmh_uses_selected_route_estimate():
    shipment = {
        "selected_route_id": "darat-1",
        "prediction_snapshot": {
            "recommended_route": {"route_id": "darat-1", "distance_km": 90.0, "estimated_duration_hours": 3.0},
            "alternative_routes": [],
        },
    }
    assert hb._nominal_speed_kmh(shipment) == 30.0


def test_nominal_speed_kmh_falls_back_when_no_route_selected():
    shipment = {"selected_route_id": None, "prediction_snapshot": None}
    assert hb._nominal_speed_kmh(shipment) == hb.NOMINAL_SPEED_KMH_DARAT


def test_nominal_speed_kmh_falls_back_when_route_id_not_found():
    shipment = {
        "selected_route_id": "does-not-exist",
        "prediction_snapshot": {
            "recommended_route": {"route_id": "darat-1", "distance_km": 90.0, "estimated_duration_hours": 3.0},
            "alternative_routes": [],
        },
    }
    assert hb._nominal_speed_kmh(shipment) == hb.NOMINAL_SPEED_KMH_DARAT


def test_process_trip_weather_delay_computes_segment_delay_against_nominal_speed(monkeypatch):
    """2 checkpoints taking 3h to cover a distance the nominal (fallback 45km/h) speed
    would expect to take less time for -- the difference should be recorded as delay."""
    p1 = {"lat": -6.90, "lon": 107.60, "recorded_at": dt.datetime(2026, 8, 15, 8, 0, tzinfo=dt.timezone.utc)}
    p2 = {"lat": -6.20, "lon": 106.80, "recorded_at": dt.datetime(2026, 8, 15, 11, 0, tzinfo=dt.timezone.utc)}
    distance_km = hb.haversine_km(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
    elapsed_hours = (p2["recorded_at"] - p1["recorded_at"]).total_seconds() / 3600
    expected_delay_hours = max(0.0, elapsed_hours - distance_km / hb.NOMINAL_SPEED_KMH_DARAT)
    assert expected_delay_hours > 0, "test fixture must produce a positive delay to be meaningful"

    recorded = []
    monkeypatch.setattr(hb.db, "select_checkpoints", lambda shipment_id: [p1, p2])
    monkeypatch.setattr(hb, "fetch_weathercode", lambda client, lat, lon, t: _async_return(61))
    monkeypatch.setattr(
        hb.db, "upsert_weather_delay_stats", lambda mode, severity, delay_hours: recorded.append((mode, severity, delay_hours))
    )

    shipment = {"shipment_id": "shp-test", "transport_mode": "darat", "selected_route_id": None}
    asyncio.run(hb.process_trip_weather_delay(client=None, shipment=shipment))

    assert len(recorded) == 1
    mode, severity, delay_hours = recorded[0]
    assert mode == "darat"
    assert severity == "hujan_lebat"  # weathercode 61 -> "Hujan Sedang" -> severity "hujan_lebat"
    assert delay_hours == expected_delay_hours


def test_process_trip_weather_delay_skips_non_darat_shipments(monkeypatch):
    called = []
    monkeypatch.setattr(hb.db, "select_checkpoints", lambda shipment_id: called.append(shipment_id))
    shipment = {"shipment_id": "shp-test", "transport_mode": "laut", "selected_route_id": None}
    asyncio.run(hb.process_trip_weather_delay(client=None, shipment=shipment))
    assert called == []


async def _async_return(value):
    return value
