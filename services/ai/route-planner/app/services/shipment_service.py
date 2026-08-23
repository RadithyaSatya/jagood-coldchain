"""Best-effort persistence of route predictions as shipment records, plus
read/outcome-reporting on top of app/core/db.py's shipment_records table.
A DB outage must never fail a prediction response -- record_prediction
catches everything and only logs a warning."""
import asyncio
import datetime as dt
import logging

import httpx

from app.core import db
from app.schemas.route_schema import PredictRouteResponse, RouteRequest
from app.schemas.shipment_schema import CheckpointReport, ShipmentOutcomeUpdate
from app.services import historical_baseline

logger = logging.getLogger(__name__)


class RouteNotFoundInSnapshotError(ValueError):
    """Raised by select_route() when route_id doesn't match this shipment's
    recommended_route_id or any of its alternative_routes."""


def _row_to_shipment_dict(row: dict) -> dict:
    return {
        **row,
        "origin": {"lat": row["origin_lat"], "lon": row["origin_lon"]},
        "destination": {"lat": row["destination_lat"], "lon": row["destination_lon"]},
    }


def _to_record(request: RouteRequest, plan: dict) -> dict:
    validated = PredictRouteResponse.model_validate(plan)
    snapshot = validated.model_dump(mode="json")
    recommended = validated.model_dump()["recommended_route"]

    return {
        "shipment_id": validated.shipment_id,
        "created_at": dt.datetime.now(dt.timezone.utc),
        "commodity_type": request.commodity_type,
        "origin_lat": request.origin.lat,
        "origin_lon": request.origin.lon,
        "destination_lat": request.destination.lat,
        "destination_lon": request.destination.lon,
        "departure_time": request.departure_time,
        "transport_mode_preference": request.transport_mode_preference,
        "cold_chain_equipment": request.cold_chain_equipment,
        "insulation_quality": request.insulation_quality,
        "ranking_preference": request.ranking_preference,
        "recommended_route_id": recommended["route_id"],
        "transport_mode": recommended["transport_mode"],
        "distance_km": recommended["distance_km"],
        "estimated_duration_hours": recommended["estimated_duration_hours"],
        "expected_delay_hours": recommended["expected_delay_hours"],
        "estimated_arrival": recommended["estimated_arrival"],
        "risk_level": recommended["risk_level"],
        "risk_probability": recommended["risk_probability"],
        "confidence_score": recommended["confidence_score"],
        "historical_delay_avg_hours": recommended["historical_delay_avg_hours"],
        "historical_damage_rate": recommended["historical_damage_rate"],
        "data_quality": recommended["data_quality"],
        "environmental_data_quality": recommended["environmental_data_quality"],
        "cargo_temperature_data_quality": recommended["cargo_temperature_data_quality"],
        "prediction_snapshot": snapshot,
        "outcome_status": "predicted_only",
        "actual_delay_hours": None,
        "actual_damage_occurred": None,
        "outcome_notes": None,
        "outcome_reported_at": None,
    }


async def record_prediction(request: RouteRequest, plan: dict) -> None:
    try:
        record = _to_record(request, plan)
        await asyncio.to_thread(db.insert_shipment_record, record)
    except Exception:
        logger.warning("Failed to persist shipment record for %s", plan.get("shipment_id"), exc_info=True)


async def get_shipment(shipment_id: str) -> dict | None:
    row = await asyncio.to_thread(db.select_shipment_by_id, shipment_id)
    return _row_to_shipment_dict(row) if row is not None else None


async def list_shipments(
    commodity_type: str | None,
    transport_mode: str | None,
    date_from: dt.datetime | None,
    date_to: dt.datetime | None,
    limit: int,
    offset: int,
) -> dict:
    rows, total = await asyncio.to_thread(
        db.select_shipments, commodity_type, transport_mode, date_from, date_to, limit, offset
    )
    return {
        "items": [_row_to_shipment_dict(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def report_outcome(shipment_id: str, body: ShipmentOutcomeUpdate) -> dict | None:
    outcome = {
        "actual_delay_hours": body.actual_delay_hours,
        "actual_damage_occurred": body.actual_damage_occurred,
        "outcome_notes": body.outcome_notes,
        "outcome_reported_at": dt.datetime.now(dt.timezone.utc),
        "outcome_status": "outcome_reported",
    }
    row = await asyncio.to_thread(db.update_shipment_outcome, shipment_id, outcome)
    if row is None:
        return None

    await asyncio.to_thread(
        historical_baseline.record_actual_outcome,
        row["transport_mode"],
        row["distance_km"],
        body.actual_delay_hours,
        body.actual_damage_occurred,
    )

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            await historical_baseline.process_trip_weather_delay(client, row)
    except Exception:
        logger.warning("Failed to process trip weather delay for %s", shipment_id, exc_info=True)

    return _row_to_shipment_dict(row)


def _route_ids_in_snapshot(snapshot: dict) -> set[str]:
    return {snapshot["recommended_route"]["route_id"]} | {
        route["route_id"] for route in snapshot["alternative_routes"]
    }


async def select_route(shipment_id: str, route_id: str) -> dict | None:
    row = await asyncio.to_thread(db.select_shipment_by_id, shipment_id)
    if row is None:
        return None
    if route_id not in _route_ids_in_snapshot(row["prediction_snapshot"]):
        raise RouteNotFoundInSnapshotError(
            f"route_id {route_id!r} is not this shipment's recommended or alternative route"
        )
    updated = await asyncio.to_thread(db.update_selected_route, shipment_id, route_id)
    return _row_to_shipment_dict(updated) if updated is not None else None


async def record_checkpoints(shipment_id: str, points: list[CheckpointReport]) -> None:
    """Best-effort: a DB outage must never fail the check-in response."""
    try:
        await asyncio.to_thread(
            db.insert_checkpoints,
            shipment_id,
            [point.model_dump() for point in points],
        )
    except Exception:
        logger.warning("Failed to persist checkpoints for %s", shipment_id, exc_info=True)
