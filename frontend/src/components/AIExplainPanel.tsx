"use client";

import { useState } from "react";
import type { AIExplainContext } from "@/lib/aiExplain";

interface AIExplainResponse {
  answer: string;
  handled_by: "rule" | "llm" | "fallback";
  model: string | null;
}

const DEFAULT_QUESTIONS = {
  smart_route_planner: "Jelaskan mengapa rute ini direkomendasikan dan faktor risiko utamanya.",
  scenario_simulator: "Jelaskan dampak skenario ini dibandingkan baseline dan tindakan yang disarankan.",
};

export default function AIExplainPanel({ context }: { context: AIExplainContext }) {
  const [question, setQuestion] = useState(DEFAULT_QUESTIONS[context.source]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<AIExplainResponse | null>(null);

  async function handleExplain(e: React.FormEvent) {
    e.preventDefault();
    const message = question.trim();
    if (!message) return;

    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      const result = await fetch("/api/ai-explain/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          language: "id",
          message,
          shipment_context: context,
          max_output_tokens: 300,
        }),
      });
      if (!result.ok) {
        const body = await result.json().catch(() => ({}));
        throw new Error(body.detail ?? `AI Explain gagal (HTTP ${result.status})`);
      }
      setResponse((await result.json()) as AIExplainResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI Explain gagal karena kesalahan tak terduga.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className={`ai-panel ${context.source === "scenario_simulator" ? "ai-panel--scenario" : ""}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3>Jelaskan dengan AI Explain</h3>
          <p>
            AI hanya menjelaskan hasil model dan SHAP di atas; AI tidak menghitung skor risiko.
          </p>
        </div>
        <span className="context-chip">
          {context.source === "scenario_simulator" ? "Konteks skenario" : "Konteks rute"}
        </span>
      </div>

      <form onSubmit={handleExplain} className="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={1000}
          disabled={loading}
          aria-label="Pertanyaan untuk AI Explain"
          className="form-control min-w-0 flex-1"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="secondary-action"
        >
          {loading ? "Menjelaskan..." : "Jelaskan"}
        </button>
      </form>

      {loading && (
        <div className="operation-loading operation-loading--inline" role="status" aria-live="polite">
          <span className="loading-spinner" aria-hidden />
          <span>Menunggu penjelasan AI Explain...</span>
        </div>
      )}

      {error && (
        <div className="app-alert mt-3" role="alert">
          {error}
        </div>
      )}

      {response && (
        <div className="ui-card mt-3">
          <p className="whitespace-pre-wrap text-sm leading-6 text-slate-800">{response.answer}</p>
          <p className="mt-2 text-xs text-slate-500">
            {response.handled_by === "llm"
              ? `Dijelaskan oleh ${response.model ?? "AI Explain"}`
              : response.handled_by === "fallback"
                ? "Ringkasan fallback tanpa LLM"
                : "Jawaban guardrail otomatis"}
          </p>
        </div>
      )}
    </section>
  );
}
