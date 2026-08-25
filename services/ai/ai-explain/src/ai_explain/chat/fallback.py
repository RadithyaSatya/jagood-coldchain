from ai_explain.schemas.chat import ChatRequest

_RISK_LABELS = {
    "low": {"id": "rendah", "en": "low"},
    "medium": {"id": "sedang", "en": "medium"},
    "high": {"id": "tinggi", "en": "high"},
    "critical": {"id": "kritis", "en": "critical"},
    "unknown": {"id": "tidak diketahui", "en": "unknown"},
}

_FACT_PRIORITY = (
    "risk_probability",
    "baseline_risk_probability",
    "simulated_risk_probability",
    "risk_delta",
    "expected_delay",
    "estimated_remaining_shelf_life",
    "estimated_remaining_shelf_life_percent",
    "quality_retention_proxy",
    "environmental_data_source",
    "cargo_temperature_source",
    "shap_summary",
)


def _select_facts(facts: dict, limit: int = 8) -> list[tuple[str, object]]:
    selected: list[tuple[str, object]] = []
    seen: set[str] = set()

    for key in _FACT_PRIORITY:
        if key in facts:
            selected.append((key, facts[key]))
            seen.add(key)
            if len(selected) == limit:
                return selected

    for key, value in facts.items():
        if key not in seen:
            selected.append((key, value))
            if len(selected) == limit:
                break
    return selected


def deterministic_fallback_answer(request: ChatRequest) -> str:
    language = request.language.value
    context = request.shipment_context
    if context is None:
        if language == "id":
            return (
                "Layanan AI generatif sedang tidak tersedia. Silakan coba kembali; "
                "hasil perhitungan analitik tidak berubah."
            )
        return (
            "The generative AI service is currently unavailable. Please try again; "
            "the analytical calculation results are unchanged."
        )

    facts = _select_facts(context.facts)
    fact_text = "; ".join(f"{key.replace('_', ' ')}: {value}" for key, value in facts)
    risk = _RISK_LABELS[context.risk_level.value][language]

    if language == "id":
        parts = [f"Ringkasan otomatis {context.product}: tingkat risiko {risk}."]
        if fact_text:
            parts.append(f"Data tersedia: {fact_text}.")
        if context.recommendation:
            parts.append(f"Rekomendasi: {context.recommendation}")
        parts.append(
            "Layanan AI generatif sedang tidak tersedia; ringkasan ini hanya memakai "
            "hasil terstruktur dari sistem analitik."
        )
        return " ".join(parts)

    parts = [f"Automatic summary for {context.product}: {risk} risk level."]
    if fact_text:
        parts.append(f"Available data: {fact_text}.")
    if context.recommendation:
        parts.append(f"Recommendation: {context.recommendation}")
    parts.append(
        "The generative AI service is unavailable; this summary only uses structured "
        "results from the analytical system."
    )
    return " ".join(parts)
