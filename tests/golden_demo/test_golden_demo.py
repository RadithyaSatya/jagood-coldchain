"""Deterministic, offline proof of JaGOOD's core analytical demo flow."""

import json
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import requests
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "services/ai/route-planner"))
sys.path.insert(0, str(PROJECT_ROOT / "services/ai/ai-explain/src"))

from ai_explain.llm import LLMMessage
from ai_explain.llm.errors import LLMServiceError
from ai_explain.main import create_app as create_ai_explain_app
from app.main import app as route_planner_app
from app.services import enrichment_service, route_generator


class UnavailableORSClient:
    def directions(self, *args, **kwargs):
        raise requests.ConnectionError("ORS intentionally unavailable in golden demo")


class UnavailableLLM:
    model = "offline-golden-demo"

    async def is_ready(self) -> bool:
        return False

    async def complete(self, messages: list[LLMMessage], max_tokens: int) -> str:
        raise LLMServiceError("LLM intentionally unavailable in golden demo")

    async def stream(
        self, messages: list[LLMMessage], max_tokens: int
    ) -> AsyncIterator[str]:
        if False:  # pragma: no cover - keeps this an async generator for the protocol
            yield ""
        raise LLMServiceError("LLM intentionally unavailable in golden demo")


def _load_golden_case() -> dict:
    path = Path(__file__).with_name("golden_case.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _scenario_explain_context(route_request: dict, scenario: dict) -> dict:
    """Mirror the typed context sent by frontend/src/lib/aiExplain.ts."""
    simulated = scenario["simulated"]
    affected_factors = "; ".join(
        f"{item['factor']}: {item['baseline_value']} -> {item['simulated_value']}"
        for item in scenario["affected_factors"]
    )[:500]
    return {
        "shipment_id": route_request["shipment_id"],
        "source": "scenario_simulator",
        "product": route_request["commodity_type"],
        "risk_level": simulated["risk_level"].lower(),
        "recommendation": scenario["recommendation"],
        "facts": {
            "scenario_id": scenario["scenario_id"],
            "baseline_risk_level": scenario["baseline"]["risk_level"],
            "simulated_risk_level": simulated["risk_level"],
            "risk_delta": f"{scenario['risk_delta'] * 100:.2f} poin persentase",
            "expected_delay": f"{simulated['expected_delay_hours']:.1f} jam",
            "simulated_cold_chain_equipment": simulated["cold_chain_equipment"],
            "simulated_cargo_temp_excess": (
                f"{simulated['max_cargo_temp_excess_c']:.1f}°C"
            ),
            "affected_factors": affected_factors,
            "shap_summary": simulated["risk_explanation_summary"],
        },
    }


def test_offline_golden_demo(monkeypatch):
    golden = _load_golden_case()
    route_request = golden["route_request"]
    expected = golden["expected"]

    monkeypatch.setattr(route_generator, "_get_client", lambda: UnavailableORSClient())

    async def fixed_hot_ambient_temperature(*args, **kwargs):
        return 35.0

    monkeypatch.setattr(
        enrichment_service,
        "fetch_ambient_temp_c",
        fixed_hot_ambient_temperature,
    )

    with TestClient(route_planner_app) as route_client:
        route_response = route_client.post("/predict-route", json=route_request)
        assert route_response.status_code == 200
        route_plan = route_response.json()
        assert route_plan["shipment_id"] == route_request["shipment_id"]
        assert (
            route_plan["recommended_route"]["data_quality"]
            == expected["route_data_quality"]
        )
        assert route_plan["recommended_route"]["risk_explanation_factors"]

        scenario_response = route_client.post(
            "/simulate-scenario",
            json={
                "baseline": route_request,
                "changes": golden["scenario_changes"],
            },
        )

    assert scenario_response.status_code == 200
    scenario = scenario_response.json()
    assert scenario["baseline"]["risk_level"] == expected["baseline_risk_level"]
    assert scenario["simulated"]["risk_level"] in expected["simulated_risk_levels"]
    assert scenario["risk_delta"] >= expected["minimum_risk_delta"]
    assert (
        scenario["simulated"]["expected_delay_hours"]
        == expected["expected_delay_hours"]
    )
    assert scenario["simulated"]["max_cargo_temp_excess_c"] > 0
    assert scenario["simulated"]["risk_explanation_factors"]

    explain_context = _scenario_explain_context(route_request, scenario)
    explain_app = create_ai_explain_app(llm=UnavailableLLM())
    with TestClient(explain_app) as explain_client:
        readiness = explain_client.get("/ready")
        assert readiness.status_code == 503
        assert readiness.json()["fallback_available"] is True

        explanation_response = explain_client.post(
            "/v1/chat",
            json={
                "language": "id",
                "message": "Jelaskan hasil skenario pengiriman ini",
                "shipment_context": explain_context,
            },
        )

    assert explanation_response.status_code == 200
    explanation = explanation_response.json()
    assert explanation["intent"] == expected["ai_intent"]
    assert explanation["handled_by"] == expected["ai_handled_by"]
    assert explanation["model"] is None
    assert explain_context["facts"]["risk_delta"] in explanation["answer"]
    assert scenario["recommendation"] in explanation["answer"]
    assert "hasil terstruktur dari sistem analitik" in explanation["answer"]
