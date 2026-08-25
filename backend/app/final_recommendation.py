from typing import Any

SCENARIO_FACTOR_LABELS = {
    "expected_delay_hours": "Keterlambatan tambahan",
    "transport_mode": "Moda transportasi",
    "cold_chain_equipment": "Peralatan cold chain",
    "insulation_quality": "Kualitas insulasi",
    "max_cargo_temp_excess_c": "Paparan suhu di atas batas ideal",
    "distance_km": "Jarak rute",
    "wave_height_m": "Tinggi gelombang",
    "weather_condition": "Kondisi cuaca",
}


def environmental_data_label(route: dict[str, Any]) -> str:
    quality = route.get("environmental_data_quality", "fallback")
    if route.get("transport_mode") == "darat":
        return {
            "forecast": "Open-Meteo cuaca darat",
            "partial": "Open-Meteo sebagian + fallback",
            "fallback": "Fallback cuaca darat",
            "configured": "Default darat terkonfigurasi",
        }.get(quality, str(quality))
    return {
        "forecast": "BMKG maritim & pelabuhan",
        "partial": "BMKG sebagian + fallback",
        "fallback": "Fallback netral (BMKG tidak tersedia)",
        "configured": "Default terkonfigurasi",
    }.get(quality, str(quality))


def cargo_temperature_data_label(route: dict[str, Any]) -> str:
    return {
        "assumed": "Asumsi reefer di suhu ideal",
        "forecast": "Open-Meteo sepanjang rute",
        "mixed": "Open-Meteo + fallback sintetis",
        "synthetic": "Fallback suhu sintetis",
        "unavailable": "Suhu ambient tidak tersedia",
    }.get(route.get("cargo_temperature_data_quality"), "Sumber tidak diketahui")


def _risk_level(value: Any) -> str:
    normalized = str(value or "unknown").lower()
    return normalized if normalized in {"low", "medium", "high", "critical"} else "unknown"


def _shap_factors(route: dict[str, Any]) -> str:
    factors = route.get("risk_explanation_factors") or []
    return "; ".join(
        f"{factor['factor']}: {factor['effect']} (impact {factor['impact']})"
        for factor in factors[:3]
    )[:500]


def _optional_quality_facts(route: dict[str, Any]) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    mappings = {
        "estimated_remaining_shelf_life_hours": ("estimated_remaining_shelf_life", "jam"),
        "estimated_remaining_shelf_life_percent": (
            "estimated_remaining_shelf_life_percent",
            "%",
        ),
        "quality_retention_proxy": ("quality_retention_proxy", "%"),
    }
    for source, (target, unit) in mappings.items():
        if route.get(source) is not None:
            facts[target] = f"{route[source]:.1f}{' ' if unit == 'jam' else ''}{unit}"
    if route.get("quality_estimation_data_quality"):
        facts["quality_estimation_data_quality"] = route["quality_estimation_data_quality"]
    return facts


def build_route_explanation_context(
    shipment_id: str, product: str, route: dict[str, Any]
) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "route_id": route["route_id"],
        "transport_mode": route["transport_mode"],
        "distance": f"{route['distance_km']:.1f} km",
        "travel_duration": f"{route['estimated_duration_hours']:.1f} jam",
        "expected_delay": f"{route['expected_delay_hours']:.1f} jam",
        "risk_probability": f"{route['risk_probability'] * 100:.2f}%",
        "model_confidence": f"{route['confidence_score'] * 100:.2f}%",
        "weather_condition": route["weather_condition"],
        "wave_condition": f"{route['wave_category']}, {route['wave_height_m']:.2f} m",
        "wind_speed": f"{route['wind_speed_kmh']:.1f} km/jam",
        "cargo_temp_excess": f"{route['max_cargo_temp_excess_c']:.1f}°C",
        "cold_chain_equipment": route["cold_chain_equipment"],
        "data_quality": route["data_quality"],
        "environmental_data_quality": route["environmental_data_quality"],
        "environmental_data_source": environmental_data_label(route),
        "cargo_temperature_data_quality": route["cargo_temperature_data_quality"],
        "cargo_temperature_source": cargo_temperature_data_label(route),
        "remaining_shelf_life": (
            f"{route['remaining_shelf_life_hours']:.1f} jam "
            f"({route['remaining_shelf_life_pct']:.0f}%)"
        ),
        "quality_status": route["quality_status"],
        "shap_summary": route["risk_explanation_summary"],
        **_optional_quality_facts(route),
    }
    if route.get("baseline_delay_hours") is not None:
        facts["baseline_delay"] = f"{route['baseline_delay_hours']:.1f} jam"
    if route.get("scenario_delay_hours") is not None:
        facts["scenario_delay"] = f"{route['scenario_delay_hours']:.1f} jam"
    if route.get("delay_data_quality"):
        facts["delay_data_quality"] = route["delay_data_quality"]
    if shap_factors := _shap_factors(route):
        facts["shap_factors"] = shap_factors
    return {
        "shipment_id": shipment_id,
        "source": "smart_route_planner",
        "product": product,
        "facts": facts,
        "risk_level": _risk_level(route["risk_level"]),
    }


def _format_factor_value(factor: str, value: Any) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return str(value)
    if factor.endswith("_hours"):
        return f"{value:.1f} jam"
    if factor.endswith("_km"):
        return f"{value:.1f} km"
    if factor.endswith("_c"):
        return f"{value:.1f}°C"
    if factor == "wave_height_m":
        return f"{value:.2f} m"
    return f"{value:.2f}"


def build_scenario_explanation_context(
    shipment_id: str, product: str, scenario: dict[str, Any]
) -> dict[str, Any]:
    baseline = scenario["baseline"]
    simulated = scenario["simulated"]
    affected_factors = "; ".join(
        f"{SCENARIO_FACTOR_LABELS.get(item['factor'], item['factor'])}: "
        f"{_format_factor_value(item['factor'], item['baseline_value'])} → "
        f"{_format_factor_value(item['factor'], item['simulated_value'])}"
        for item in scenario.get("affected_factors", [])
    )[:500]
    facts: dict[str, Any] = {
        "scenario_id": scenario["scenario_id"],
        "baseline_risk_level": baseline["risk_level"],
        "baseline_risk_probability": f"{baseline['risk_probability'] * 100:.2f}%",
        "simulated_risk_level": simulated["risk_level"],
        "simulated_risk_probability": f"{simulated['risk_probability'] * 100:.2f}%",
        "risk_delta": f"{scenario['risk_delta'] * 100:.2f} poin persentase",
        "expected_delay": f"{simulated['expected_delay_hours']:.1f} jam",
        "simulated_transport_mode": simulated["transport_mode"],
        "simulated_cold_chain_equipment": simulated["cold_chain_equipment"],
        "simulated_cargo_temp_excess": f"{simulated['max_cargo_temp_excess_c']:.1f}°C",
        "environmental_data_quality": simulated["environmental_data_quality"],
        "environmental_data_source": environmental_data_label(simulated),
        "cargo_temperature_data_quality": simulated["cargo_temperature_data_quality"],
        "cargo_temperature_source": cargo_temperature_data_label(simulated),
        "baseline_remaining_shelf_life": (
            f"{baseline['remaining_shelf_life_hours']:.1f} jam "
            f"({baseline['remaining_shelf_life_pct']:.0f}%)"
        ),
        "simulated_remaining_shelf_life": (
            f"{simulated['remaining_shelf_life_hours']:.1f} jam "
            f"({simulated['remaining_shelf_life_pct']:.0f}%)"
        ),
        "simulated_quality_status": simulated["quality_status"],
        "shap_summary": simulated["risk_explanation_summary"],
        **_optional_quality_facts(simulated),
    }
    if simulated.get("baseline_delay_hours") is not None:
        facts["baseline_delay"] = f"{simulated['baseline_delay_hours']:.1f} jam"
    if simulated.get("scenario_delay_hours") is not None:
        facts["scenario_delay"] = f"{simulated['scenario_delay_hours']:.1f} jam"
    if affected_factors:
        facts["affected_factors"] = affected_factors
    if shap_factors := _shap_factors(simulated):
        facts["shap_factors"] = shap_factors
    return {
        "shipment_id": shipment_id,
        "source": "scenario_simulator",
        "product": product,
        "facts": facts,
        "risk_level": _risk_level(simulated["risk_level"]),
        "recommendation": scenario["recommendation"],
    }


def build_final_recommendation(
    shipment: dict[str, Any], route_plan: dict[str, Any], scenario: dict[str, Any] | None
) -> dict[str, Any]:
    route = route_plan["recommended_route"]
    recommendation = (
        scenario["recommendation"]
        if scenario
        else (
            f"Gunakan rute {route['route_id']} berdasarkan preferensi "
            f"{shipment.get('ranking_preference', 'risiko')}."
        )
    )
    context = (
        build_scenario_explanation_context(
            route_plan["shipment_id"], shipment["commodity_type"], scenario
        )
        if scenario
        else build_route_explanation_context(
            route_plan["shipment_id"], shipment["commodity_type"], route
        )
    )
    return {
        "route_plan": route_plan,
        "scenario": scenario,
        "final_recommendation": {
            "route_id": route["route_id"],
            "risk_level": route["risk_level"],
            "risk_probability": route["risk_probability"],
            "recommendation": recommendation,
            "provenance": {
                "routing": route["data_quality"],
                "environment": environmental_data_label(route),
                "cargo_temperature": cargo_temperature_data_label(route),
            },
        },
        "explanation_context": context,
    }
