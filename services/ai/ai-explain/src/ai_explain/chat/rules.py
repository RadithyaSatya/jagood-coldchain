import re

from ai_explain.schemas.chat import ChatIntent, ChatRequest

_GREETINGS = {
    "halo",
    "hai",
    "hi",
    "hello",
    "pagi",
    "siang",
    "sore",
    "malam",
}

_BLOCKED_PATTERNS = (
    r"\b(presiden|politik|pemilu|partai)\b",
    r"\b(obat|vaksin|farmasi|medicine|vaccine|pharmaceutical)\b",
    r"\b(kode|coding|programming|javascript|python)\b",
    r"\b(puisi|cerita|novel|lagu|joke|lelucon)\b",
    r"\b(ignore|abaikan)\b.{0,40}\b(instruction|instruksi|prompt|aturan)\b",
)

_INTENT_KEYWORDS: tuple[tuple[ChatIntent, tuple[str, ...]], ...] = (
    (
        ChatIntent.RISK_EXPLANATION,
        ("risiko", "risk", "bahaya", "berisiko", "kenapa tinggi", "kenapa rendah"),
    ),
    (
        ChatIntent.ROUTE_EXPLANATION,
        ("rute", "route", "jalur", "perjalanan", "eta"),
    ),
    (
        ChatIntent.SCENARIO_EXPLANATION,
        ("skenario", "scenario", "simulasi", "what if", "jika terlambat"),
    ),
    (
        ChatIntent.RECOMMENDATION,
        ("rekomendasi", "recommendation", "saran", "tindakan", "harus apa", "next action"),
    ),
    (
        ChatIntent.SHIPMENT_STATUS,
        ("status", "kondisi", "pengiriman", "shipment", "kiriman", "monitoring", "suhu"),
    ),
    (
        ChatIntent.GENERAL_COLD_CHAIN,
        (
            "cold chain",
            "rantai dingin",
            "makanan beku",
            "frozen food",
            "pendingin",
            "refrigerasi",
            "refrigeration",
        ),
    ),
)


def classify_chat_intent(request: ChatRequest) -> ChatIntent:
    message = _normalize(request.message)

    if _matches_any(message, _BLOCKED_PATTERNS):
        return ChatIntent.UNSUPPORTED
    if message in _GREETINGS:
        return ChatIntent.GREETING

    knowledge_intent = _classify_knowledge_intent(message)
    if knowledge_intent is not None:
        return knowledge_intent

    for intent, keywords in _INTENT_KEYWORDS:
        if any(keyword in message for keyword in keywords):
            return intent

    # Short follow-up questions are useful when the application supplied shipment
    # data or the immediately preceding conversation was already in scope.
    if request.shipment_context is not None and len(message.split()) <= 8:
        return _intent_from_context(request)
    if request.history and _history_is_in_scope(request):
        if len(message.split()) <= 8:
            return ChatIntent.GENERAL_COLD_CHAIN

    return ChatIntent.UNSUPPORTED


def requires_shipment_context(intent: ChatIntent) -> bool:
    return intent in {
        ChatIntent.SHIPMENT_STATUS,
        ChatIntent.RISK_EXPLANATION,
        ChatIntent.RECOMMENDATION,
        ChatIntent.ROUTE_EXPLANATION,
        ChatIntent.SCENARIO_EXPLANATION,
    }


def uses_knowledge_base(intent: ChatIntent) -> bool:
    return intent in {
        ChatIntent.ABOUT_JAGOOD,
        ChatIntent.FEATURE_INFORMATION,
        ChatIntent.USAGE_GUIDE,
        ChatIntent.GENERAL_COLD_CHAIN,
    }


def rule_answer(request: ChatRequest, intent: ChatIntent) -> str | None:
    if intent is ChatIntent.GREETING:
        if request.language.value == "id":
            return (
                "Halo! Saya dapat membantu menjelaskan status, risiko, rute, dan skenario "
                "pengiriman cold-chain makanan."
            )
        return (
            "Hello! I can explain food cold-chain shipment status, risks, routes, and scenarios."
        )

    if intent is ChatIntent.UNSUPPORTED:
        if request.language.value == "id":
            return (
                "Maaf, saya hanya dapat membantu terkait cold-chain makanan dan data "
                "pengiriman yang tersedia di Jagood."
            )
        return (
            "Sorry, I can only help with food cold-chain topics and shipment data available "
            "in Jagood."
        )

    if requires_shipment_context(intent) and request.shipment_context is None:
        if request.language.value == "id":
            return (
                "Mohon pilih atau kirimkan konteks pengiriman terlebih dahulu agar saya "
                "dapat menjawab berdasarkan data yang tersedia."
            )
        return (
            "Please select or provide a shipment context first so I can answer from the "
            "available data."
        )

    if (
        intent is ChatIntent.SCENARIO_EXPLANATION
        and request.shipment_context is not None
        and request.shipment_context.source.value == "scenario_simulator"
    ):
        return _scenario_summary(request)

    return None


def _scenario_summary(request: ChatRequest) -> str:
    context = request.shipment_context
    assert context is not None
    facts = context.facts
    baseline_level = _risk_label(facts.get("baseline_risk_level"), request.language.value)
    simulated_level = _risk_label(facts.get("simulated_risk_level"), request.language.value)
    baseline_probability = facts.get("baseline_risk_probability", facts.get("baseline_risk", "-"))
    simulated_probability = facts.get(
        "simulated_risk_probability", facts.get("simulated_risk", "-")
    )
    risk_delta = facts.get("risk_delta")
    affected_factors = facts.get("affected_factors")
    environmental_data_source = facts.get("environmental_data_source")
    cargo_temperature_source = facts.get("cargo_temperature_source")

    if request.language.value == "id":
        parts = [
            f"Risiko berubah dari {baseline_level} ({baseline_probability}) menjadi "
            f"{simulated_level} ({simulated_probability})."
        ]
        if risk_delta is not None:
            parts.append(f"Selisih risiko: {risk_delta}.")
        if affected_factors:
            parts.append(f"Perubahan utama: {str(affected_factors).rstrip('.')}.")
        if environmental_data_source:
            parts.append(f"Sumber data lingkungan: {environmental_data_source}.")
        if cargo_temperature_source:
            parts.append(f"Sumber suhu kargo: {cargo_temperature_source}.")
        if context.recommendation:
            parts.append(f"Saran: {context.recommendation.rstrip('.')}.")
        parts.append("Ringkasan ini hanya memakai hasil terstruktur dari sistem analitik.")
        return "\n\n".join(parts)

    parts = [
        f"Risk changed from {baseline_level} ({baseline_probability}) to "
        f"{simulated_level} ({simulated_probability})."
    ]
    if risk_delta is not None:
        parts.append(f"Risk difference: {risk_delta}.")
    if affected_factors:
        parts.append(f"Main changes: {str(affected_factors).rstrip('.')}.")
    if environmental_data_source:
        parts.append(f"Environmental data source: {environmental_data_source}.")
    if cargo_temperature_source:
        parts.append(f"Cargo-temperature source: {cargo_temperature_source}.")
    if context.recommendation:
        parts.append(f"Suggested action: {context.recommendation.rstrip('.')}.")
    parts.append("This summary only uses structured results from the analytical system.")
    return "\n\n".join(parts)


def _risk_label(value: object, language: str) -> str:
    normalized = str(value or "unknown").casefold()
    labels = {
        "low": {"id": "rendah", "en": "low"},
        "medium": {"id": "sedang", "en": "medium"},
        "high": {"id": "tinggi", "en": "high"},
        "critical": {"id": "kritis", "en": "critical"},
        "unknown": {"id": "tidak diketahui", "en": "unknown"},
    }
    return labels.get(normalized, labels["unknown"])[language]


def missing_knowledge_answer(request: ChatRequest) -> str:
    if request.language.value == "id":
        return "Informasi tersebut belum tersedia dalam dokumentasi Jagood."
    return "That information is not currently available in the Jagood documentation."


def _normalize(value: str) -> str:
    return " ".join(value.casefold().strip().rstrip(".!?").split())


def _classify_knowledge_intent(message: str) -> ChatIntent | None:
    if any(phrase in message for phrase in ("cara menggunakan", "cara pakai", "how to use")):
        return ChatIntent.USAGE_GUIDE
    if any(
        phrase in message
        for phrase in (
            "fitur",
            "fungsi",
            "kegunaan",
            "bisa apa",
            "smart route planner",
            "ai scenario simulator",
            "ai explain",
        )
    ):
        return ChatIntent.FEATURE_INFORMATION
    if "jagood" in message:
        return ChatIntent.ABOUT_JAGOOD
    return None


def _matches_any(value: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, value) for pattern in patterns)


def _history_is_in_scope(request: ChatRequest) -> bool:
    recent = " ".join(message.content.casefold() for message in request.history[-2:])
    return any(keyword in recent for _, keywords in _INTENT_KEYWORDS for keyword in keywords)


def _intent_from_context(request: ChatRequest) -> ChatIntent:
    assert request.shipment_context is not None
    source = request.shipment_context.source.value
    if source == "smart_route_planner":
        return ChatIntent.ROUTE_EXPLANATION
    if source == "scenario_simulator":
        return ChatIntent.SCENARIO_EXPLANATION
    return ChatIntent.SHIPMENT_STATUS
