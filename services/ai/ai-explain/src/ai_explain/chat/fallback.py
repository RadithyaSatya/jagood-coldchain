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
    "remaining_shelf_life",
    "cold_chain_equipment",
    "weather_condition",
    "wave_condition",
    "environmental_data_source",
    "cargo_temperature_source",
    "primary_risk_factor",
    "shap_summary",
)

_FACT_LABELS_ID = {
    "risk_probability": "Perkiraan risiko",
    "baseline_risk_probability": "Risiko awal",
    "simulated_risk_probability": "Risiko setelah skenario",
    "risk_delta": "Perubahan risiko",
    "expected_delay": "Perkiraan keterlambatan",
    "estimated_remaining_shelf_life": "Perkiraan sisa umur simpan",
    "estimated_remaining_shelf_life_percent": "Persentase sisa umur simpan",
    "quality_retention_proxy": "Perkiraan kualitas yang tersisa",
    "remaining_shelf_life": "Sisa umur simpan",
    "cold_chain_equipment": "Sistem pendingin",
    "weather_condition": "Kondisi cuaca",
    "wave_condition": "Kondisi gelombang",
    "environmental_data_source": "Sumber informasi lingkungan",
    "cargo_temperature_source": "Sumber informasi suhu kargo",
    "shap_summary": "Faktor yang memengaruhi risiko",
    "primary_risk_factor": "Faktor risiko utama",
}

_FACT_LABELS_EN = {
    "risk_probability": "Estimated risk",
    "baseline_risk_probability": "Baseline risk",
    "simulated_risk_probability": "Risk after the scenario",
    "risk_delta": "Risk change",
    "expected_delay": "Estimated delay",
    "estimated_remaining_shelf_life": "Estimated remaining shelf life",
    "estimated_remaining_shelf_life_percent": "Remaining shelf-life percentage",
    "quality_retention_proxy": "Estimated retained quality",
    "remaining_shelf_life": "Remaining shelf life",
    "cold_chain_equipment": "Cooling system",
    "weather_condition": "Weather condition",
    "wave_condition": "Wave condition",
    "environmental_data_source": "Environmental information source",
    "cargo_temperature_source": "Cargo-temperature information source",
    "shap_summary": "Factors affecting risk",
    "primary_risk_factor": "Primary risk factor",
}


def _select_facts(facts: dict, limit: int = 10) -> list[tuple[str, object]]:
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
    risk = _RISK_LABELS[context.risk_level.value][language]

    if language == "id":
        parts = [f"Pengiriman {context.product} berada pada risiko {risk}."]
        parts.extend(_friendly_fact_sentences(facts, _FACT_LABELS_ID))
        if context.recommendation:
            parts.append(f"Rekomendasi: {context.recommendation}")
        parts.append(
            "Ringkasan ini dibuat langsung dari hasil analisis sistem tanpa mengubah "
            "angka yang tersedia."
        )
        return " ".join(parts)

    parts = [f"The {context.product} shipment is at {risk} risk."]
    parts.extend(_friendly_fact_sentences(facts, _FACT_LABELS_EN))
    if context.recommendation:
        parts.append(f"Recommendation: {context.recommendation}")
    parts.append(
        "This summary comes directly from the analytical results and preserves the "
        "available figures."
    )
    return " ".join(parts)


def _friendly_fact_sentences(
    facts: list[tuple[str, object]], labels: dict[str, str]
) -> list[str]:
    sentences: list[str] = []
    for key, raw_value in facts:
        label = labels.get(key)
        if label is None:
            continue
        value = str(raw_value).strip().rstrip(".")
        if key == "cold_chain_equipment":
            if value.casefold() == "reefer":
                value = "pendingin aktif (reefer)"
            elif value.casefold() == "pasif":
                value = "pendingin pasif"
        sentences.append(f"{label}: {value}.")
    return sentences
