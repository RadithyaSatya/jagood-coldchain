from app.schemas.route_schema import ScenarioRequest
from app.services.scenario_service import _modified_request, _recommendation


def _request(delay_hours: float = 0) -> ScenarioRequest:
    return ScenarioRequest.model_validate(
        {
            "baseline": {
                "origin": {"lat": -6.2088, "lon": 106.8456},
                "destination": {"lat": -7.2575, "lon": 112.7521},
                "commodity_type": "Salmon Segar",
                "departure_time": "2026-08-15T08:00:00Z",
            },
            "changes": {
                "delay_hours": delay_hours,
                "cold_chain_equipment": "pasif" if delay_hours == 0 else None,
            },
        }
    )


def test_recommendation_flags_significant_delay_risk_increase():
    recommendation = _recommendation(0.2, _request(delay_hours=12))
    assert "meningkat signifikan" in recommendation
    assert "keterlambatan" in recommendation


def test_recommendation_recognizes_risk_reduction():
    recommendation = _recommendation(-0.1, _request())
    assert "menurunkan risiko" in recommendation


def test_modified_request_applies_route_and_cold_chain_changes():
    request = ScenarioRequest.model_validate(
        {
            "baseline": {
                "origin": {"lat": -6.2088, "lon": 106.8456},
                "destination": {"lat": -7.2575, "lon": 112.7521},
                "commodity_type": "Salmon Segar",
                "departure_time": "2026-08-15T08:00:00Z",
                "transport_mode_preference": "darat",
                "cold_chain_equipment": "reefer",
                "insulation_quality": "sedang",
            },
            "changes": {
                "transport_mode": "kombinasi",
                "cold_chain_equipment": "pasif",
                "insulation_quality": "buruk",
            },
        }
    )

    modified = _modified_request(request)

    assert modified.transport_mode_preference == "kombinasi"
    assert modified.cold_chain_equipment == "pasif"
    assert modified.insulation_quality == "buruk"
    assert modified.commodity_type == request.baseline.commodity_type
