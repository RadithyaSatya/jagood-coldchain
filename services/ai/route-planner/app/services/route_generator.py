"""Generates 2-3 route candidates per shipment (FR-2): a direct land route
(if OpenRouteService can find one -- Indonesian OSM driving data already
bakes in short ferry links like Merak-Bakauheni/Ketapang-Gilimanuk, so a
"land" route across a strait can succeed on its own) plus one or two
multimodal (land+sea+land) candidates stitched through curated ports via
port_selector.py + searoute-py.
"""
from concurrent.futures import ThreadPoolExecutor

import openrouteservice
import searoute as sr
from openrouteservice.exceptions import ApiError

from app.core.config import settings
from app.services.geo_utils import haversine_km
from app.services.port_selector import Port, PortPair, select_port_pairs

LAUT_SPEED_KMH = 16 * 1.852  # ~16 knot cargo ferry
PORT_DWELL_HOURS = 6.0  # per port call
HGV_PROFILE = "driving-hgv"

VALID_PREFERENCES = {"darat", "laut", "kombinasi", "semua"}

# The public OpenRouteService instance occasionally has broken/sparse graph
# connectivity in parts of Indonesia (observed: a 13km Jakarta hop resolved to
# a >1500km detour through Sumatra). Rather than surface nonsense numbers, any
# result wildly disproportionate to the straight-line distance is treated as a
# routing failure and replaced with a haversine-based estimate.
FALLBACK_ROAD_SPEED_KMH = 40.0
FALLBACK_ROAD_INFLATION = 1.3  # typical road-vs-straight-line distance factor
SHORT_HOP_KM = 50.0
SHORT_HOP_MAX_RATIO = 3.0
SHORT_HOP_ABSOLUTE_BUFFER_KM = 40.0
LONG_HOP_MAX_RATIO = 6.0


def _get_client() -> openrouteservice.Client:
    return openrouteservice.Client(key=settings.ors_api_key)


def _is_plausible(distance_km: float, straight_line_km: float) -> bool:
    if straight_line_km < SHORT_HOP_KM:
        return distance_km <= straight_line_km * SHORT_HOP_MAX_RATIO + SHORT_HOP_ABSOLUTE_BUFFER_KM
    return distance_km <= straight_line_km * LONG_HOP_MAX_RATIO


def _fallback_leg(straight_line_km: float) -> dict:
    distance_km = straight_line_km * FALLBACK_ROAD_INFLATION
    return {
        "distance_km": distance_km,
        "duration_hours": distance_km / FALLBACK_ROAD_SPEED_KMH,
        "geometry": [],
        "source": "estimated_fallback",
    }


def _ors_leg(client: openrouteservice.Client, origin: tuple[float, float], destination: tuple[float, float]) -> dict | None:
    """origin/destination are (lat, lon). Returns None only if ORS can't find any
    route at all (e.g. no road/ferry connectivity between the two points). A
    result that comes back but is wildly implausible vs. the straight-line
    distance is replaced with a haversine-based estimate rather than trusted
    or dropped outright -- see the module-level comment above."""
    straight_line_km = haversine_km(origin[0], origin[1], destination[0], destination[1])
    try:
        result = client.directions(
            coordinates=[(origin[1], origin[0]), (destination[1], destination[0])],
            profile=HGV_PROFILE,
            format="geojson",
        )
    except ApiError:
        return None

    feature = result["features"][0]
    summary = feature["properties"]["summary"]
    distance_km = summary["distance"] / 1000.0
    if not _is_plausible(distance_km, straight_line_km):
        return _fallback_leg(straight_line_km)

    return {
        "distance_km": distance_km,
        "duration_hours": summary["duration"] / 3600.0,
        "geometry": feature["geometry"]["coordinates"],
        "source": "ors",
    }


def _sea_leg(embark: Port, disembark: Port) -> dict:
    route = sr.searoute([embark.lon, embark.lat], [disembark.lon, disembark.lat], units="km")
    distance_km = route["properties"]["length"]
    waypoints_lonlat = route["geometry"]["coordinates"]
    waypoints_latlon = [(lat, lon) for lon, lat in waypoints_lonlat]
    return {
        "distance_km": distance_km,
        "duration_hours": distance_km / LAUT_SPEED_KMH + PORT_DWELL_HOURS,
        "waypoints": waypoints_latlon,
    }


def _sample_waypoints(waypoints: list[tuple[float, float]], n: int = 4) -> list[tuple[float, float]]:
    if len(waypoints) <= n:
        return waypoints
    step = (len(waypoints) - 1) / (n - 1)
    return [waypoints[round(i * step)] for i in range(n)]


def _assemble_land_candidate(leg: dict | None) -> dict | None:
    if leg is None:
        return None
    return {
        "transport_mode": "darat",
        "distance_km": round(leg["distance_km"], 1),
        "estimated_duration_hours": round(leg["duration_hours"], 2),
        "sea_waypoints": [],
        "port_pair": None,
        "data_quality": "estimated" if leg["source"] == "estimated_fallback" else "live",
    }


def _assemble_multimodal_candidate(
    land_leg_1: dict | None, land_leg_2: dict | None, port_pair: PortPair
) -> dict | None:
    if land_leg_1 is None or land_leg_2 is None:
        return None

    embark, disembark = port_pair.embark, port_pair.disembark
    sea_leg = _sea_leg(embark, disembark)

    total_distance = land_leg_1["distance_km"] + sea_leg["distance_km"] + land_leg_2["distance_km"]
    total_duration = land_leg_1["duration_hours"] + sea_leg["duration_hours"] + land_leg_2["duration_hours"]

    any_estimated = land_leg_1["source"] == "estimated_fallback" or land_leg_2["source"] == "estimated_fallback"
    return {
        "transport_mode": "kombinasi",
        "distance_km": round(total_distance, 1),
        "estimated_duration_hours": round(total_duration, 2),
        "sea_waypoints": _sample_waypoints(sea_leg["waypoints"]),
        "port_pair": {"embark": embark, "disembark": disembark},
        "data_quality": "estimated" if any_estimated else "live",
    }


def generate_candidates(
    origin: tuple[float, float],
    destination: tuple[float, float],
    transport_mode_preference: str | None = None,
) -> list[dict]:
    """All ORS land-leg calls needed across every candidate are fired
    concurrently (a thread pool, since openrouteservice-py is a blocking
    client) rather than one after another -- sequentially this endpoint could
    take 5+ round trips and blow past the PRD's <5s latency target."""
    preference = (transport_mode_preference or "semua").lower()
    if preference not in VALID_PREFERENCES:
        preference = "semua"

    client = _get_client()

    port_pairs = None
    if preference in ("laut", "kombinasi", "semua"):
        port_pairs = select_port_pairs(origin[0], origin[1], destination[0], destination[1])

    leg_requests: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
    if preference in ("darat", "semua"):
        leg_requests["darat_direct"] = (origin, destination)
    if port_pairs is not None:
        for label, combo in (("primary", port_pairs["primary"]), ("alternative", port_pairs["alternative"])):
            if combo is None:
                continue
            leg_requests[f"{label}_land1"] = (origin, (combo.embark.lat, combo.embark.lon))
            leg_requests[f"{label}_land2"] = ((combo.disembark.lat, combo.disembark.lon), destination)

    with ThreadPoolExecutor(max_workers=max(1, len(leg_requests))) as executor:
        futures = {key: executor.submit(_ors_leg, client, o, d) for key, (o, d) in leg_requests.items()}
        legs = {key: future.result() for key, future in futures.items()}

    candidates: list[dict] = []

    if "darat_direct" in leg_requests:
        land = _assemble_land_candidate(legs["darat_direct"])
        if land is not None:
            candidates.append(land)

    if port_pairs is not None:
        for label, combo in (("primary", port_pairs["primary"]), ("alternative", port_pairs["alternative"])):
            if combo is None:
                continue
            candidate = _assemble_multimodal_candidate(legs[f"{label}_land1"], legs[f"{label}_land2"], combo)
            if candidate is not None:
                candidates.append(candidate)

    return candidates
