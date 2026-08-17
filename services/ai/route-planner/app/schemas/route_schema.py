import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

TransportModePreference = Literal["darat", "laut", "kombinasi", "semua"]
ColdChainEquipment = Literal["reefer", "pasif"]
InsulationQuality = Literal["baik", "sedang", "buruk"]
RankingPreference = Literal["risiko", "kecepatan"]


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
    cold_chain_equipment: ColdChainEquipment = Field(
        default="reefer",
        description="'reefer' = actively refrigerated (cargo stays near ideal temp; default). "
        "'pasif' = no active cooling -- cargo temperature is simulated against real ambient "
        "conditions along the route (Open-Meteo) using an exponential heat-transfer model.",
    )
    insulation_quality: InsulationQuality = Field(
        default="sedang", description="Packaging insulation quality, only used when cold_chain_equipment='pasif'"
    )
    ranking_preference: RankingPreference = Field(
        default="risiko",
        description="'risiko' (default) = rank by predicted cargo-damage risk first, travel time only as a "
        "tiebreaker -- the product's core differentiator vs. a generic fastest-route planner (PRD FR-5). "
        "'kecepatan' = rank purely by travel time; risk is still predicted, explained and displayed, but "
        "does not affect ordering.",
    )

    def resolved_shipment_id(self) -> str:
        return self.shipment_id or f"shp-{uuid.uuid4().hex[:12]}"


class RiskHotspot(BaseModel):
    """Exact point along a sea leg with the worst forecast conditions --
    where a route-level risk actually comes from, for map annotation."""

    lat: float
    lon: float


class PortInfo(BaseModel):
    port_name: str
    lat: float
    lon: float


class PortPairInfo(BaseModel):
    embark: PortInfo
    disembark: PortInfo


class CargoTempPoint(BaseModel):
    hour: float = Field(description="Hours elapsed since departure")
    temp_c: float = Field(description="Simulated cargo temperature at this point (deg C)")


class RiskFactor(BaseModel):
    factor: str = Field(description="Human-readable description of the contributing condition")
    effect: str = Field(description="'menaikkan' (increases risk) or 'menurunkan' (decreases risk)")
    impact: float = Field(description="Relative magnitude of this factor's SHAP contribution (not a probability)")


class RouteCandidate(BaseModel):
    route_id: str
    transport_mode: str = Field(description="darat (land), laut/kombinasi (multimodal land+sea via port)")
    distance_km: float
    estimated_duration_hours: float
    expected_delay_hours: float = Field(
        default=0,
        description="Additional expected in-transit delay beyond the route's normal travel duration.",
    )
    estimated_arrival: datetime = Field(
        description="Projected arrival = departure_time + estimated_duration_hours + expected_delay_hours. Inherits that "
        "estimate's uncertainty (and is only as good as the underlying ORS/searoute legs); it does not model "
        "loading, customs or unscheduled stops."
    )

    risk_level: str = Field(description="Low / Medium / High -- the model's final classification")
    risk_probability: float = Field(description="P(Medium)*0.5 + P(High)*1.0 -- continuous risk score used for ranking (0-1)")
    confidence_score: float = Field(description="Model's confidence in its own top prediction (0-1)")
    trigger_reason: str | None = Field(default=None, description="Set when extreme wave/port conditions demoted this route (FR-6); null otherwise")
    data_quality: str = Field(default="live", description="'live' = real ORS/BMKG data; 'estimated' = a routing leg fell back to a straight-line estimate")

    wave_category: str = Field(description="BMKG wave severity: Tenang < Rendah < Sedang < Tinggi < Sangat Tinggi < Ekstrem < Sangat Ekstrem")
    wave_height_m: float = Field(description="Forecast wave height in meters along this route (0 for land routes)")
    wind_speed_kmh: float
    weather_condition: str = Field(description="BMKG weather description (e.g. Cerah, Berawan, Hujan Lebat, Hujan Badai)")
    port_status_flag: int = Field(description="1 = normal, 0 = port/sea leg at risk of closure due to extreme wave conditions")
    port_ambient_temp_c: float = Field(description="Real BMKG ambient air temperature (deg C) at the hotter of the embark/disembark port stops -- a proxy for reefer/equipment stress risk during port dwell time, not the cargo's own temperature. 30.0 default for land-only routes (no port stop).")
    historical_delay_avg_hours: float = Field(description="Estimated typical delay for this route's distance/mode/exposure profile (model feature, not this shipment's actual delay)")
    historical_damage_rate: float = Field(description="Estimated typical cargo damage rate for this route profile (0-1, model feature)")

    cold_chain_equipment: str = Field(description="'reefer' (actively refrigerated) or 'pasif' (no active cooling, cargo temp simulated against ambient)")
    commodity_temp_ideal_c: float = Field(description="Commodity's ideal storage temperature (deg C, midpoint of its ideal range) -- the reference threshold for max_cargo_temp_excess_c and the cargo_temp_profile chart")
    max_cargo_temp_excess_c: float = Field(description="Peak simulated cargo temperature above the commodity's ideal temp during the journey (deg C). Always 0 for reefer.")
    cargo_temp_profile: list[CargoTempPoint] = Field(default_factory=list, description="Simulated cargo temperature over the journey (empty for reefer)")

    geometry: list[list[float]] = Field(default_factory=list, description="Route path as [lat, lon] pairs, in travel order, for map rendering")
    risk_hotspot: RiskHotspot | None = Field(default=None, description="Where along the route the worst conditions were found, if any")
    port_pair: PortPairInfo | None = Field(default=None, description="Embark/disembark ports for kombinasi routes; null for darat")

    risk_explanation_summary: str = Field(description="One-sentence, SHAP-based explanation of why this route got this risk level (FR-8)")
    risk_explanation_factors: list[RiskFactor] = Field(default_factory=list, description="Top contributing factors behind risk_explanation_summary, ranked by impact")


class PredictRouteResponse(BaseModel):
    shipment_id: str
    recommended_route: RouteCandidate
    alternative_routes: list[RouteCandidate]


class ScenarioChanges(BaseModel):
    delay_hours: float = Field(
        default=0,
        ge=0,
        le=168,
        description="Additional in-transit delay applied to the estimated route duration (maximum 7 days).",
    )
    transport_mode: TransportModePreference | None = None
    cold_chain_equipment: ColdChainEquipment | None = None
    insulation_quality: InsulationQuality | None = None

    @model_validator(mode="after")
    def require_at_least_one_change(self):
        if (
            self.delay_hours == 0
            and self.transport_mode is None
            and self.cold_chain_equipment is None
            and self.insulation_quality is None
        ):
            raise ValueError("At least one scenario change must be provided")
        return self


class ScenarioRequest(BaseModel):
    baseline: RouteRequest
    changes: ScenarioChanges


class ScenarioFactorChange(BaseModel):
    factor: str
    baseline_value: float | str
    simulated_value: float | str


class ScenarioResponse(BaseModel):
    scenario_id: str
    baseline: RouteCandidate
    simulated: RouteCandidate
    risk_delta: float = Field(description="Simulated risk probability minus baseline risk probability")
    affected_factors: list[ScenarioFactorChange]
    recommendation: str


class CommodityInfo(BaseModel):
    commodity_type: str
    temp_ideal_min_c: float
    temp_ideal_max_c: float
    shelf_life_hours_at_ideal_temp: float
    delay_tolerance_hours: float
    temp_sensitivity_level: str
