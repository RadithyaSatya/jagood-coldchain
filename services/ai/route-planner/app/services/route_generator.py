"""Generates 2-3 route candidates per shipment (FR-2): a direct land route
(if OpenRouteService can find one -- Indonesian OSM driving data already
bakes in short ferry links like Merak-Bakauheni/Ketapang-Gilimanuk, so a
"land" route across a strait can succeed on its own) plus one or two
multimodal (land+sea+land) candidates stitched through curated ports via
port_selector.py + searoute-py.
"""
from concurrent.futures import ThreadPoolExecutor

import openrouteservice
import requests
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

ALT_ROUTES_PARAMS = {"target_count": 3, "weight_factor": 1.6, "share_factor": 0.6}
# ORS's native alternative_routes only works under ~100km real route distance
# on the public instance. For every distance, we additionally request a
# handful of routing-preference variants (recommended / shortest / avoid
# tollways) -- the same toll-vs-non-toll, fastest-vs-shortest choice Google
# Maps offers regardless of trip length. Near-duplicate results (no toll
# road on that path at all, etc.) are deduped by distance.
#
# IMPORTANT: passing preference="fastest" explicitly is ~5-20x slower on this
# ORS instance than omitting preference entirely or using "recommended" --
# measured 23-26s vs 1-6s for the exact same Jakarta-Surabaya route, even
# though "fastest" is supposedly the default. Cause unconfirmed (server-side
# quirk), but never pass preference="fastest" -- use None (omit the
# parameter) or "recommended" instead.
DARAT_VARIANT_SPECS: list[tuple[str | None, bool]] = [
    ("recommended", False),
    (None, True),  # avoid tollways -- omit preference, "fastest"+avoid_features is the slow combination
    ("shortest", False),
]
DEDUPE_DISTANCE_RATIO = 0.01
MAX_DARAT_VARIANTS = 4

# ORS's OSM-derived HGV graph tags some genuinely long inter-island ferry
# crossings (e.g. Java-Sulawesi via the Lesser Sunda chain, ~550km of ferry
# out of a ~2440km "route") as routable ways, so a "darat" query can
# silently return a route that's mostly a boat. A short bridging ferry
# (Merak-Bakauheni ~5.6km, Ketapang-Gilimanuk ~2.5km, Padangbai-Lembar
# ~35km) is legitimately part of a land route; anything past that is really
# an island-hopping sea route and should be represented by the properly
# modeled `kombinasi` candidates instead, not mislabeled as `darat`.
MAX_BRIDGING_FERRY_KM = 40.0
WAYTYPE_FERRY_VALUE = 9


def _get_client() -> openrouteservice.Client:
    return openrouteservice.Client(key=settings.ors_api_key)


def _is_plausible(distance_km: float, straight_line_km: float) -> bool:
    if straight_line_km < SHORT_HOP_KM:
        return distance_km <= straight_line_km * SHORT_HOP_MAX_RATIO + SHORT_HOP_ABSOLUTE_BUFFER_KM
    return distance_km <= straight_line_km * LONG_HOP_MAX_RATIO


def _fallback_leg(origin: tuple[float, float], destination: tuple[float, float], straight_line_km: float) -> dict:
    distance_km = straight_line_km * FALLBACK_ROAD_INFLATION
    return {
        "distance_km": distance_km,
        "duration_hours": distance_km / FALLBACK_ROAD_SPEED_KMH,
        "geometry": [list(origin), list(destination)],
        "source": "estimated_fallback",
        "ferry_km": 0.0,
    }


def _ferry_distance_km(feature: dict) -> float:
    waytype_summary = feature["properties"].get("extras", {}).get("waytype", {}).get("summary", [])
    ferry_meters = sum(entry["distance"] for entry in waytype_summary if entry["value"] == WAYTYPE_FERRY_VALUE)
    return ferry_meters / 1000.0


def _feature_to_leg(feature: dict) -> dict:
    summary = feature["properties"]["summary"]
    # ORS returns [lon, lat] pairs (GeoJSON order); flip to [lat, lon] so every
    # geometry in this module (and the API response) uses one consistent order.
    geometry_latlon = [[lat, lon] for lon, lat in feature["geometry"]["coordinates"]]
    return {
        "distance_km": summary["distance"] / 1000.0,
        "duration_hours": summary["duration"] / 3600.0,
        "geometry": geometry_latlon,
        "source": "ors",
        "ferry_km": _ferry_distance_km(feature),
    }


def _ors_leg(client: openrouteservice.Client, origin: tuple[float, float], destination: tuple[float, float]) -> dict:
    """origin/destination are (lat, lon). Always returns a leg -- if ORS can't
    find any route at all (e.g. the point is in open water/off the road
    network entirely, which is easy to hit by clicking the map at a
    country-wide zoom level) or returns something wildly implausible vs. the
    straight-line distance, falls back to a haversine-based estimate rather
    than giving up outright -- see the module-level comment above."""
    straight_line_km = haversine_km(origin[0], origin[1], destination[0], destination[1])
    try:
        result = client.directions(
            coordinates=[(origin[1], origin[0]), (destination[1], destination[0])],
            profile=HGV_PROFILE,
            format="geojson",
            extra_info=["waytype"],
        )
    except (ApiError, requests.RequestException):
        return _fallback_leg(origin, destination, straight_line_km)

    leg = _feature_to_leg(result["features"][0])
    if not _is_plausible(leg["distance_km"], straight_line_km):
        return _fallback_leg(origin, destination, straight_line_km)
    return leg


def _fetch_variant(
    client: openrouteservice.Client,
    origin: tuple[float, float],
    destination: tuple[float, float],
    preference: str | None,
    avoid_tollways: bool,
) -> dict | None:
    kwargs: dict = {}
    if preference is not None:
        kwargs["preference"] = preference
    if avoid_tollways:
        kwargs["options"] = {"avoid_features": ["tollways"]}
    try:
        result = client.directions(
            coordinates=[(origin[1], origin[0]), (destination[1], destination[0])],
            profile=HGV_PROFILE,
            format="geojson",
            extra_info=["waytype"],
            **kwargs,
        )
    except (ApiError, requests.RequestException):
        return None
    return _feature_to_leg(result["features"][0])


def _dedupe_by_distance(legs: list[dict]) -> list[dict]:
    """Keeps the first occurrence of each distinct distance -- e.g. "avoid
    tollways" often returns the exact same road when there's no toll option
    on that corridor at all, which shouldn't show up as a second candidate."""
    kept: list[dict] = []
    for leg in legs:
        if not any(
            abs(leg["distance_km"] - k["distance_km"]) / max(k["distance_km"], 1.0) < DEDUPE_DISTANCE_RATIO
            for k in kept
        ):
            kept.append(leg)
    return kept


def _ors_leg_alternatives(
    client: openrouteservice.Client, origin: tuple[float, float], destination: tuple[float, float]
) -> list[dict]:
    """Combines two sources of route variety: ORS's native alternative_routes
    (genuinely distinct road-network paths, but only available under ~100km
    real route distance on the public instance) and routing-preference
    variants (fastest / shortest / avoid tollways), which work at *any*
    distance -- the same toll-vs-non-toll choice Google Maps offers
    regardless of trip length. Falls back to a single haversine-based
    estimate only if every attempt fails outright."""
    straight_line_km = haversine_km(origin[0], origin[1], destination[0], destination[1])

    native_legs: list[dict] = []
    try:
        result = client.directions(
            coordinates=[(origin[1], origin[0]), (destination[1], destination[0])],
            profile=HGV_PROFILE,
            format="geojson",
            extra_info=["waytype"],
            alternative_routes=ALT_ROUTES_PARAMS,
        )
        native_legs = [_feature_to_leg(f) for f in result["features"]]
    except (ApiError, requests.RequestException):
        pass

    with ThreadPoolExecutor(max_workers=len(DARAT_VARIANT_SPECS)) as executor:
        futures = [
            executor.submit(_fetch_variant, client, origin, destination, preference, avoid_tollways)
            for preference, avoid_tollways in DARAT_VARIANT_SPECS
        ]
        results = [f.result() for f in futures]
        variant_legs = [leg for leg in results if leg is not None]

    all_legs = native_legs + variant_legs
    plausible = [leg for leg in all_legs if _is_plausible(leg["distance_km"], straight_line_km)]
    if not plausible:
        return [_fallback_leg(origin, destination, straight_line_km)]

    return _dedupe_by_distance(plausible)[:MAX_DARAT_VARIANTS]


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


def _assemble_land_candidate(leg: dict) -> dict | None:
    """None if ORS's "land" route is actually mostly a long ferry crossing
    (see MAX_BRIDGING_FERRY_KM) -- that's not a real darat option, and the
    properly-modeled kombinasi candidates already cover the genuine
    multimodal case for it."""
    if leg["ferry_km"] > MAX_BRIDGING_FERRY_KM:
        return None
    return {
        "transport_mode": "darat",
        "distance_km": round(leg["distance_km"], 1),
        "estimated_duration_hours": round(leg["duration_hours"], 2),
        "geometry": leg["geometry"],
        "sea_waypoints": [],
        "port_pair": None,
        "data_quality": "estimated" if leg["source"] == "estimated_fallback" else "live",
    }


def _assemble_multimodal_candidate(land_leg_1: dict, land_leg_2: dict, port_pair: PortPair) -> dict:
    embark, disembark = port_pair.embark, port_pair.disembark
    sea_leg = _sea_leg(embark, disembark)

    total_distance = land_leg_1["distance_km"] + sea_leg["distance_km"] + land_leg_2["distance_km"]
    total_duration = land_leg_1["duration_hours"] + sea_leg["duration_hours"] + land_leg_2["duration_hours"]

    sea_geometry = [list(p) for p in sea_leg["waypoints"]]
    full_geometry = land_leg_1["geometry"] + sea_geometry + land_leg_2["geometry"]

    any_estimated = land_leg_1["source"] == "estimated_fallback" or land_leg_2["source"] == "estimated_fallback"
    return {
        "transport_mode": "kombinasi",
        "distance_km": round(total_distance, 1),
        "estimated_duration_hours": round(total_duration, 2),
        "geometry": full_geometry,
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
        futures = {}
        for key, (o, d) in leg_requests.items():
            if key == "darat_direct":
                futures[key] = executor.submit(_ors_leg_alternatives, client, o, d)
            else:
                futures[key] = executor.submit(_ors_leg, client, o, d)
        legs = {key: future.result() for key, future in futures.items()}

    candidates: list[dict] = []

    if "darat_direct" in leg_requests:
        for leg in legs["darat_direct"]:
            land = _assemble_land_candidate(leg)
            if land is not None:
                candidates.append(land)

    if port_pairs is not None:
        for label, combo in (("primary", port_pairs["primary"]), ("alternative", port_pairs["alternative"])):
            if combo is None:
                continue
            candidates.append(_assemble_multimodal_candidate(legs[f"{label}_land1"], legs[f"{label}_land2"], combo))

    return candidates
