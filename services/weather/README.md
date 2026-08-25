# weather

Not implemented as a standalone service yet.

BMKG maritime weather/wave integration currently lives inside
[`services/ai/route-planner/app/services/weather_service.py`](../ai/route-planner/app/services/weather_service.py).
If other services need weather data, extract it here as a shared service
rather than duplicating the BMKG integration.
