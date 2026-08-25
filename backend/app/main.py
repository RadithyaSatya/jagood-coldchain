import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from app.config import Settings
from app.final_recommendation import build_final_recommendation


class FinalRecommendationRequest(BaseModel):
    shipment: dict[str, Any]
    scenario_changes: dict[str, Any] | None = None


def _forward_headers(request: Request) -> dict[str, str]:
    return {
        name: value
        for name, value in request.headers.items()
        if name.lower() in {"accept", "content-type"}
    }


def _response_headers(response: httpx.Response) -> dict[str, str]:
    return {
        name: value
        for name, value in response.headers.items()
        if name.lower() in {"content-type", "cache-control", "x-accel-buffering"}
    }


def create_app(
    *,
    settings: Settings | None = None,
    upstream_client: httpx.AsyncClient | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if upstream_client is None:
            application.state.upstream_client = httpx.AsyncClient(
                timeout=httpx.Timeout(resolved_settings.timeout_seconds)
            )
            application.state.owns_upstream_client = True
        yield
        if application.state.owns_upstream_client:
            await application.state.upstream_client.aclose()

    application = FastAPI(
        title="JaGOOD Platform API Gateway",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.upstream_client = upstream_client
    application.state.owns_upstream_client = False
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    async def proxy(
        request: Request,
        base_url: str,
        path: str,
        *,
        stream: bool = False,
    ) -> Response:
        client: httpx.AsyncClient = request.app.state.upstream_client
        try:
            upstream_request = client.build_request(
                request.method,
                f"{base_url}{path}",
                params=request.query_params,
                headers=_forward_headers(request),
                content=await request.body(),
            )
            upstream_response = await client.send(upstream_request, stream=stream)
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Layanan internal melewati batas waktu.",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Layanan internal tidak tersedia.",
            ) from exc

        headers = _response_headers(upstream_response)
        if stream:
            return StreamingResponse(
                upstream_response.aiter_raw(),
                status_code=upstream_response.status_code,
                headers=headers,
                background=BackgroundTask(upstream_response.aclose),
            )
        content = await upstream_response.aread()
        await upstream_response.aclose()
        return Response(content=content, status_code=upstream_response.status_code, headers=headers)

    async def request_json(
        request: Request, base_url: str, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        client: httpx.AsyncClient = request.app.state.upstream_client
        try:
            response = await client.post(f"{base_url}{path}", json=payload)
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504, detail="Layanan internal melewati batas waktu."
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail="Layanan internal tidak tersedia.") from exc
        if not response.is_success:
            try:
                detail = response.json().get("detail", "Permintaan layanan internal gagal.")
            except (ValueError, AttributeError):
                detail = "Permintaan layanan internal gagal."
            mapped_status = response.status_code if 400 <= response.status_code < 500 else 502
            raise HTTPException(status_code=mapped_status, detail=detail)
        try:
            return response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=502, detail="Respons layanan internal tidak valid."
            ) from exc

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "jagood-platform-gateway"}

    @application.get("/ready", tags=["health"])
    async def ready(request: Request) -> JSONResponse:
        client: httpx.AsyncClient = request.app.state.upstream_client

        async def check(name: str, url: str) -> tuple[str, bool]:
            try:
                response = await client.get(f"{url}/health")
                return name, response.is_success
            except httpx.HTTPError:
                return name, False

        checks = dict(
            await asyncio.gather(
                check("route_planner", resolved_settings.route_planner_base_url),
                check("ai_explain", resolved_settings.ai_explain_base_url),
            )
        )
        is_ready = all(checks.values())
        return JSONResponse(
            status_code=200 if is_ready else 503,
            content={
                "status": "ready" if is_ready else "degraded",
                "services": {
                    name: "ready" if available else "unavailable"
                    for name, available in checks.items()
                },
            },
        )

    @application.api_route("/commodities", methods=["GET"], tags=["route-planner"])
    async def commodities(request: Request) -> Response:
        return await proxy(request, resolved_settings.route_planner_base_url, "/commodities")

    @application.api_route("/commodities/provenance", methods=["GET"], tags=["route-planner"])
    async def commodities_provenance(request: Request) -> Response:
        return await proxy(
            request, resolved_settings.route_planner_base_url, "/commodities/provenance"
        )

    @application.api_route("/predict-route", methods=["POST"], tags=["route-planner"])
    async def predict_route(request: Request) -> Response:
        return await proxy(request, resolved_settings.route_planner_base_url, "/predict-route")

    @application.api_route("/simulate-scenario", methods=["POST"], tags=["route-planner"])
    async def simulate_scenario(request: Request) -> Response:
        return await proxy(request, resolved_settings.route_planner_base_url, "/simulate-scenario")

    @application.api_route("/shipments", methods=["GET"], tags=["shipments"])
    async def shipments(request: Request) -> Response:
        return await proxy(request, resolved_settings.route_planner_base_url, "/shipments")

    @application.api_route(
        "/shipments/{shipment_path:path}", methods=["GET", "POST", "PATCH"], tags=["shipments"]
    )
    async def shipment(request: Request, shipment_path: str) -> Response:
        return await proxy(
            request,
            resolved_settings.route_planner_base_url,
            f"/shipments/{shipment_path}",
        )

    @application.api_route("/v1/chat", methods=["POST"], tags=["ai-explain"])
    async def chat(request: Request) -> Response:
        return await proxy(request, resolved_settings.ai_explain_base_url, "/v1/chat")

    @application.api_route("/ai-explain/ready", methods=["GET"], tags=["ai-explain"])
    async def ai_explain_ready(request: Request) -> Response:
        return await proxy(request, resolved_settings.ai_explain_base_url, "/ready")

    @application.api_route("/v1/chat/stream", methods=["POST"], tags=["ai-explain"])
    async def chat_stream(request: Request) -> Response:
        return await proxy(
            request, resolved_settings.ai_explain_base_url, "/v1/chat/stream", stream=True
        )

    @application.api_route("/v1/explanations", methods=["POST"], tags=["ai-explain"])
    async def explanations(request: Request) -> Response:
        return await proxy(request, resolved_settings.ai_explain_base_url, "/v1/explanations")

    @application.api_route("/v1/explanations/stream", methods=["POST"], tags=["ai-explain"])
    async def explanations_stream(request: Request) -> Response:
        return await proxy(
            request,
            resolved_settings.ai_explain_base_url,
            "/v1/explanations/stream",
            stream=True,
        )

    @application.post("/final-recommendation", tags=["orchestration"])
    async def final_recommendation(
        payload: FinalRecommendationRequest, request: Request
    ) -> dict[str, Any]:
        route_plan = await request_json(
            request,
            resolved_settings.route_planner_base_url,
            "/predict-route",
            payload.shipment,
        )
        scenario = None
        if payload.scenario_changes is not None:
            scenario = await request_json(
                request,
                resolved_settings.route_planner_base_url,
                "/simulate-scenario",
                {
                    "baseline": {
                        **payload.shipment,
                        "shipment_id": route_plan["shipment_id"],
                    },
                    "changes": payload.scenario_changes,
                },
            )
        try:
            return build_final_recommendation(payload.shipment, route_plan, scenario)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail="Respons Route Planner tidak memenuhi kontrak Final Recommendation.",
            ) from exc

    return application


app = create_app()
