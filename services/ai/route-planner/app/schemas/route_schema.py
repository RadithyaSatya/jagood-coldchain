import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TransportModePreference = Literal["darat", "laut", "kombinasi", "semua"]


class Coordinate(BaseModel):
    lat: float
    lon: float


class RouteRequest(BaseModel):
    shipment_id: str | None = None
    origin: Coordinate
    destination: Coordinate
    commodity_type: str
    departure_time: datetime
    transport_mode_preference: TransportModePreference | None = None

    def resolved_shipment_id(self) -> str:
        return self.shipment_id or f"shp-{uuid.uuid4().hex[:12]}"


class RouteCandidate(BaseModel):
    route_id: str
    transport_mode: str
    distance_km: float
    estimated_duration_hours: float
    risk_level: str
    risk_probability: float
    confidence_score: float
    trigger_reason: str | None = None
    data_quality: str = "live"


class PredictRouteResponse(BaseModel):
    shipment_id: str
    recommended_route: RouteCandidate
    alternative_routes: list[RouteCandidate]


class CommodityInfo(BaseModel):
    commodity_type: str
    temp_ideal_min_c: float
    temp_ideal_max_c: float
    shelf_life_hours_at_ideal_temp: float
    delay_tolerance_hours: float
    temp_sensitivity_level: str
