from fastapi import APIRouter, HTTPException

from app.schemas.route_schema import (
    CommodityDatasetProvenance,
    CommodityInfo,
    PredictRouteResponse,
    RouteRequest,
    ScenarioRequest,
    ScenarioResponse,
)
from app.services import commodity_service, shipment_service
from app.services.planning_service import NoRouteCandidatesError, build_route_plan
from app.services.scenario_service import simulate_scenario

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/commodities", response_model=list[CommodityInfo])
async def list_commodities() -> list[dict]:
    return commodity_service.list_commodities()


@router.get("/commodities/provenance", response_model=CommodityDatasetProvenance)
async def commodity_data_provenance() -> dict:
    return commodity_service.get_dataset_provenance()


@router.post("/predict-route", response_model=PredictRouteResponse)
async def predict_route(request: RouteRequest) -> dict:
    try:
        commodity_service.get_commodity(request.commodity_type)
    except commodity_service.CommodityNotFoundError:
        raise HTTPException(status_code=404, detail=f"Unknown commodity_type: {request.commodity_type}")

    try:
        plan = await build_route_plan(request)
    except NoRouteCandidatesError:
        raise HTTPException(
            status_code=422,
            detail="No route candidates could be generated between the given origin and destination.",
        )

    await shipment_service.record_prediction(request, plan)
    return plan


@router.post("/simulate-scenario", response_model=ScenarioResponse)
async def simulate(request: ScenarioRequest) -> dict:
    try:
        commodity_service.get_commodity(request.baseline.commodity_type)
    except commodity_service.CommodityNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown commodity_type: {request.baseline.commodity_type}",
        )

    try:
        return await simulate_scenario(request)
    except NoRouteCandidatesError:
        raise HTTPException(
            status_code=422,
            detail="No route candidates could be generated for the baseline or modified scenario.",
        )
