from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.schemas.shipment_schema import (
    CheckpointBatch,
    RouteSelection,
    ShipmentListResponse,
    ShipmentOutcomeUpdate,
    ShipmentRecord,
)
from app.services import shipment_service

router = APIRouter()


@router.get("/shipments", response_model=ShipmentListResponse)
async def list_shipments(
    commodity_type: str | None = None,
    transport_mode: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return await shipment_service.list_shipments(commodity_type, transport_mode, date_from, date_to, limit, offset)


@router.get("/shipments/{shipment_id}", response_model=ShipmentRecord)
async def get_shipment(shipment_id: str) -> dict:
    record = await shipment_service.get_shipment(shipment_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown shipment_id: {shipment_id}")
    return record


@router.patch("/shipments/{shipment_id}/outcome", response_model=ShipmentRecord)
async def report_outcome(shipment_id: str, body: ShipmentOutcomeUpdate) -> dict:
    record = await shipment_service.report_outcome(shipment_id, body)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown shipment_id: {shipment_id}")
    return record


@router.post("/shipments/{shipment_id}/select-route", response_model=ShipmentRecord)
async def select_route(shipment_id: str, body: RouteSelection) -> dict:
    try:
        record = await shipment_service.select_route(shipment_id, body.route_id)
    except shipment_service.RouteNotFoundInSnapshotError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown shipment_id: {shipment_id}")
    return record


@router.post("/shipments/{shipment_id}/checkpoints", status_code=202)
async def submit_checkpoint(shipment_id: str, body: CheckpointBatch) -> dict:
    record = await shipment_service.get_shipment(shipment_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown shipment_id: {shipment_id}")
    await shipment_service.record_checkpoints(shipment_id, body.points)
    return {"checkpoints_received": len(body.points)}
