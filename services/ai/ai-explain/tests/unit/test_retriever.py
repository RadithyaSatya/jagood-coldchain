from ai_explain.chat.retriever import retrieve_knowledge


def test_retrieves_feature_section_from_markdown() -> None:
    results = retrieve_knowledge("Apa fungsi Smart Route Planner?")

    assert results
    assert results[0].citation == "ai-modules.md#smart-route-planner"
    assert "Best Route" in results[0].content


def test_retrieves_document_using_synonym() -> None:
    results = retrieve_knowledge("Bagaimana monitoring pengiriman?")

    assert any(result.heading == "Maritime Monitoring" for result in results)


def test_retrieves_jagood_overview() -> None:
    results = retrieve_knowledge("Apa itu Jagood?")

    assert results[0].citation == "overview.md#jagood"


def test_returns_no_results_for_unrelated_query() -> None:
    assert retrieve_knowledge("astronomi galaksi kuantum") == []


def test_uses_configured_markdown_directory(monkeypatch, tmp_path) -> None:
    document = tmp_path / "custom.md"
    document.write_text(
        "# Distribusi Ikan Segar\n\nJagood mendukung distribusi ikan segar berpendingin.",
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_EXPLAIN_KNOWLEDGE_DIR", str(tmp_path))

    results = retrieve_knowledge("distribusi ikan segar")

    assert results[0].citation == "custom.md#distribusi-ikan-segar"


def test_missing_configured_directory_returns_no_results(monkeypatch, tmp_path) -> None:
    missing_directory = tmp_path / "missing"
    monkeypatch.setenv("AI_EXPLAIN_KNOWLEDGE_DIR", str(missing_directory))

    assert retrieve_knowledge("Apa itu Jagood?") == []
