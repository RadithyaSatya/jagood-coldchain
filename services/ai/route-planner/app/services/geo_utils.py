import math

EARTH_RADIUS_KM = 6371.0088

# Ordered so overlapping boxes near strait crossings resolve to the more
# specific/common island group first.
ISLAND_BOUNDING_BOXES = [
    ("Sumatera", -6.5, 6.5, 94.5, 106.5),
    ("Jawa", -9.2, -5.5, 105.0, 114.6),
    ("Kalimantan", -4.5, 4.5, 108.5, 119.5),
    ("Sulawesi", -6.5, 2.0, 118.5, 125.7),
    ("Bali-Nusra", -11.5, -7.5, 114.6, 125.5),
    ("Maluku", -8.5, 3.5, 124.5, 135.0),
    ("Papua", -9.5, 0.5, 130.0, 141.5),
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def tag_island_group(lat: float, lon: float) -> str | None:
    for island_group, lat_min, lat_max, lon_min, lon_max in ISLAND_BOUNDING_BOXES:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return island_group
    return None
