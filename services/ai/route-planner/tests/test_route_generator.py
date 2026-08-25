import requests

from app.services.route_generator import _ors_leg


class TimeoutORSClient:
    def directions(self, *args, **kwargs):
        raise requests.Timeout("ORS timed out during offline test")


def test_ors_leg_falls_back_on_transport_timeout():
    origin = (-6.2088, 106.8456)
    destination = (-7.2575, 112.7521)

    leg = _ors_leg(TimeoutORSClient(), origin, destination)

    assert leg["source"] == "estimated_fallback"
    assert leg["distance_km"] > 0
    assert leg["duration_hours"] > 0
    assert leg["geometry"] == [list(origin), list(destination)]
