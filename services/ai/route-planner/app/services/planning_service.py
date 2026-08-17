"""Shared route-planning orchestration for prediction and counterfactuals."""
import asyncio

from app.schemas.route_schema import RouteRequest
from app.services.enrichment_service import enrich_all_candidates
from app.services.ranking_service import rank_candidates
from app.services.route_generator import generate_candidates


class NoRouteCandidatesError(RuntimeError):
    pass


async def generate_candidates_for_request(request: RouteRequest) -> list[dict]:
    origin = (request.origin.lat, request.origin.lon)
    destination = (request.destination.lat, request.destination.lon)
    candidates = await asyncio.to_thread(
        generate_candidates,
        origin,
        destination,
        request.transport_mode_preference,
    )
    if not candidates:
        raise NoRouteCandidatesError
    return candidates


async def evaluate_candidates(
    candidates: list[dict],
    request: RouteRequest,
    shipment_id: str,
    additional_delay_hours: float = 0,
) -> dict:
    enriched = await enrich_all_candidates(
        candidates,
        request.commodity_type,
        request.departure_time,
        shipment_id,
        cold_chain_equipment=request.cold_chain_equipment,
        insulation_quality=request.insulation_quality,
        expected_delay_hours=additional_delay_hours,
    )
    return rank_candidates(enriched, request.ranking_preference)


async def build_route_plan(request: RouteRequest, shipment_id: str | None = None) -> dict:
    resolved_shipment_id = shipment_id or request.resolved_shipment_id()
    candidates = await generate_candidates_for_request(request)
    ranked = await evaluate_candidates(candidates, request, resolved_shipment_id)
    return {
        "shipment_id": resolved_shipment_id,
        "recommended_route": ranked["recommended_route"],
        "alternative_routes": ranked["alternative_routes"],
    }
