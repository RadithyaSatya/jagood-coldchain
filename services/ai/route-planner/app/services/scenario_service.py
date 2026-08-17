"""Analytical baseline-vs-counterfactual comparison using the route risk model."""
import uuid

from app.schemas.route_schema import RouteRequest, ScenarioRequest
from app.services.planning_service import evaluate_candidates, generate_candidates_for_request

MATERIAL_RISK_DELTA = 0.03
SIGNIFICANT_RISK_DELTA = 0.15


def _modified_request(request: ScenarioRequest) -> RouteRequest:
    changes = request.changes
    updates = {}
    if changes.transport_mode is not None:
        updates["transport_mode_preference"] = changes.transport_mode
    if changes.cold_chain_equipment is not None:
        updates["cold_chain_equipment"] = changes.cold_chain_equipment
    if changes.insulation_quality is not None:
        updates["insulation_quality"] = changes.insulation_quality
    return request.baseline.model_copy(update=updates)


def _factor_changes(request: ScenarioRequest, baseline: dict, simulated: dict) -> list[dict]:
    changes = request.changes
    factors: list[dict] = []

    def add(factor: str, baseline_value, simulated_value) -> None:
        if baseline_value != simulated_value:
            factors.append(
                {
                    "factor": factor,
                    "baseline_value": baseline_value,
                    "simulated_value": simulated_value,
                }
            )

    if changes.delay_hours > 0:
        add(
            "expected_delay_hours",
            baseline["expected_delay_hours"],
            simulated["expected_delay_hours"],
        )
    if changes.transport_mode is not None:
        add("transport_mode", baseline["transport_mode"], simulated["transport_mode"])
    if changes.cold_chain_equipment is not None:
        add(
            "cold_chain_equipment",
            request.baseline.cold_chain_equipment,
            changes.cold_chain_equipment,
        )
    if changes.insulation_quality is not None:
        add(
            "insulation_quality",
            request.baseline.insulation_quality,
            changes.insulation_quality,
        )

    add(
        "max_cargo_temp_excess_c",
        baseline["max_cargo_temp_excess_c"],
        simulated["max_cargo_temp_excess_c"],
    )
    add("distance_km", baseline["distance_km"], simulated["distance_km"])
    add("wave_height_m", baseline["wave_height_m"], simulated["wave_height_m"])
    add("weather_condition", baseline["weather_condition"], simulated["weather_condition"])
    return factors


def _recommendation(risk_delta: float, request: ScenarioRequest) -> str:
    if risk_delta >= SIGNIFICANT_RISK_DELTA:
        if request.changes.delay_hours > 0:
            return "Risiko meningkat signifikan; kurangi keterlambatan atau gunakan reefer aktif."
        return "Risiko meningkat signifikan; pertahankan konfigurasi baseline atau pilih alternatif berisiko lebih rendah."
    if risk_delta > MATERIAL_RISK_DELTA:
        return "Risiko meningkat; tinjau kembali perubahan skenario sebelum pengiriman."
    if risk_delta <= -MATERIAL_RISK_DELTA:
        return "Skenario ini menurunkan risiko dan layak dipertimbangkan untuk pengiriman."
    return "Perubahan risiko tidak material; keputusan dapat mempertimbangkan waktu dan biaya operasional."


async def simulate_scenario(request: ScenarioRequest) -> dict:
    scenario_id = f"scn-{uuid.uuid4().hex[:12]}"
    shipment_id = request.baseline.resolved_shipment_id()
    modified_request = _modified_request(request)

    baseline_candidates = await generate_candidates_for_request(request.baseline)
    if modified_request.transport_mode_preference == request.baseline.transport_mode_preference:
        modified_candidates = baseline_candidates
    else:
        modified_candidates = await generate_candidates_for_request(modified_request)

    baseline_ranked = await evaluate_candidates(
        baseline_candidates,
        request.baseline,
        shipment_id,
    )
    simulated_ranked = await evaluate_candidates(
        modified_candidates,
        modified_request,
        shipment_id,
        additional_delay_hours=request.changes.delay_hours,
    )

    baseline = baseline_ranked["recommended_route"]
    simulated = simulated_ranked["recommended_route"]
    risk_delta = round(simulated["risk_probability"] - baseline["risk_probability"], 6)
    return {
        "scenario_id": scenario_id,
        "baseline": baseline,
        "simulated": simulated,
        "risk_delta": risk_delta,
        "affected_factors": _factor_changes(request, baseline, simulated),
        "recommendation": _recommendation(risk_delta, request),
    }
