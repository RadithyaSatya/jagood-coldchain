import asyncio

from fastapi import APIRouter, HTTPException

from app.schemas.route_schema import CommodityInfo, PredictRouteResponse, RouteRequest
from app.services import commodity_service
from app.services.enrichment_service import enrich_all_candidates
from app.services.ranking_service import rank_candidates
from app.services.route_generator import generate_candidates

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/commodities", response_model=list[CommodityInfo])
async def list_commodities() -> list[dict]:
    return commodity_service.list_commodities()


@router.post("/predict-route", response_model=PredictRouteResponse)
async def predict_route(request: RouteRequest) -> dict:
    try:
        commodity_service.get_commodity(request.commodity_type)
    except commodity_service.CommodityNotFoundError:
        raise HTTPException(status_code=404, detail=f"Unknown commodity_type: {request.commodity_type}")

    origin = (request.origin.lat, request.origin.lon)
    destination = (request.destination.lat, request.destination.lon)

    candidates = await asyncio.to_thread(
        generate_candidates, origin, destination, request.transport_mode_preference
    )
    if not candidates:
        raise HTTPException(
            status_code=422,
            detail="No route candidates could be generated between the given origin and destination.",
        )

    shipment_id = request.resolved_shipment_id()
    enriched = await enrich_all_candidates(
        candidates,
        request.commodity_type,
        request.departure_time,
        shipment_id,
        cold_chain_equipment=request.cold_chain_equipment,
        insulation_quality=request.insulation_quality,
    )
    ranked = rank_candidates(enriched, request.ranking_preference)

    return {
        "shipment_id": shipment_id,
        "recommended_route": ranked["recommended_route"],
        "alternative_routes": ranked["alternative_routes"],
    }
