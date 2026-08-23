from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.route_schema import Coordinate

OutcomeStatus = Literal["predicted_only", "outcome_reported"]


class ShipmentRecord(BaseModel):
    shipment_id: str
    created_at: datetime

    commodity_type: str
    origin: Coordinate
    destination: Coordinate
    departure_time: datetime
    transport_mode_preference: str | None
    cold_chain_equipment: str
    insulation_quality: str
    ranking_preference: str

    recommended_route_id: str
    transport_mode: str
    distance_km: float
    estimated_duration_hours: float
    expected_delay_hours: float
    estimated_arrival: datetime
    risk_level: str
    risk_probability: float
    confidence_score: float
    historical_delay_avg_hours: float = Field(
        description="Baseline predicted at prediction time -- frozen, not recomputed"
    )
    historical_damage_rate: float
    data_quality: str
    environmental_data_quality: str
    cargo_temperature_data_quality: str

    prediction_snapshot: dict = Field(
        description="Full PredictRouteResponse (recommended_route + alternative_routes) as served at prediction time"
    )

    outcome_status: OutcomeStatus = Field(
        description="'predicted_only' = model output only; 'outcome_reported' = actual "
        "real-world outcome has been recorded (the system's first REAL shipment data)."
    )
    actual_delay_hours: float | None
    actual_damage_occurred: bool | None
    outcome_notes: str | None
    outcome_reported_at: datetime | None
    selected_route_id: str | None = Field(
        default=None,
        description="Which of recommended_route_id / alternative_routes[].route_id was actually "
        "driven, set via POST /shipments/{id}/select-route. Used to compare checkpoint-derived "
        "travel speed against that specific route's own estimated speed rather than a flat default.",
    )


class ShipmentListResponse(BaseModel):
    items: list[ShipmentRecord]
    total: int
    limit: int
    offset: int


class ShipmentOutcomeUpdate(BaseModel):
    actual_delay_hours: float = Field(ge=0, description="Actual observed delay in hours, once known")
    actual_damage_occurred: bool
    outcome_notes: str | None = Field(default=None, max_length=1000)


class RouteSelection(BaseModel):
    route_id: str = Field(
        description="Must match this shipment's recommended_route_id or one of its "
        "alternative_routes[].route_id (from the stored prediction_snapshot)."
    )


class CheckpointReport(BaseModel):
    lat: float
    lon: float
    recorded_at: datetime
    checkpoint_label: str | None = Field(
        default=None, max_length=100, description="Free-text tag for readability, e.g. 'keberangkatan', 'rest_area_1', 'tiba' -- not used in delay calculations."
    )


class CheckpointBatch(BaseModel):
    points: list[CheckpointReport] = Field(min_length=1, max_length=20)
