import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.services.geo_utils import haversine_km, tag_island_group

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "ports_reference.json"


@dataclass(frozen=True)
class Port:
    port_id: str
    port_name: str
    city: str
    lat: float
    lon: float
    island_group: str


@dataclass(frozen=True)
class PortPair:
    embark: Port
    disembark: Port
    sea_distance_km: float


@lru_cache(maxsize=1)
def _load_ports() -> list[Port]:
    with open(DATA_PATH, encoding="utf-8") as f:
        rows = json.load(f)
    return [Port(**row) for row in rows]


def _nearest_port_overall(lat: float, lon: float) -> Port:
    return min(_load_ports(), key=lambda p: haversine_km(lat, lon, p.lat, p.lon))


def resolve_island_group(lat: float, lon: float) -> str:
    """Bounding-box tag with a nearest-port fallback for coastal/edge coordinates
    that fall outside every box (e.g. small outlying islands)."""
    tagged = tag_island_group(lat, lon)
    if tagged is not None:
        return tagged
    return _nearest_port_overall(lat, lon).island_group


def nearest_ports_in_group(lat: float, lon: float, island_group: str, top_n: int = 2) -> list[Port]:
    candidates = [p for p in _load_ports() if p.island_group == island_group]
    if not candidates:
        candidates = _load_ports()
    return sorted(candidates, key=lambda p: haversine_km(lat, lon, p.lat, p.lon))[:top_n]


def select_port_pairs(
    origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float
) -> dict[str, PortPair | None]:
    """Returns a primary embark/disembark port pair plus one alternative
    (using the next-nearest port on either end), ranked by combined distance
    from origin/destination to each candidate port."""
    origin_island = resolve_island_group(origin_lat, origin_lon)
    dest_island = resolve_island_group(dest_lat, dest_lon)

    embark_candidates = nearest_ports_in_group(origin_lat, origin_lon, origin_island, top_n=2)
    disembark_candidates = nearest_ports_in_group(dest_lat, dest_lon, dest_island, top_n=2)

    combos = []
    for embark in embark_candidates:
        for disembark in disembark_candidates:
            sea_km = haversine_km(embark.lat, embark.lon, disembark.lat, disembark.lon)
            land_km = haversine_km(origin_lat, origin_lon, embark.lat, embark.lon) + haversine_km(
                dest_lat, dest_lon, disembark.lat, disembark.lon
            )
            combos.append((land_km + sea_km, PortPair(embark, disembark, sea_km)))

    combos.sort(key=lambda c: c[0])
    if not combos:
        return {"primary": None, "alternative": None}

    primary = combos[0][1]
    alternative = None
    for _, combo in combos[1:]:
        if combo.embark.port_id != primary.embark.port_id or combo.disembark.port_id != primary.disembark.port_id:
            alternative = combo
            break

    return {"primary": primary, "alternative": alternative}
