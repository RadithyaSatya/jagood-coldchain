"use client";

import { useState } from "react";
import type { AIExplainContext } from "@/lib/aiExplain";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080";

interface AIExplainResponse {
  answer: string;
  handled_by: "rule" | "llm" | "fallback";
  model: string | null;
}

const DEFAULT_QUESTIONS = {
  smart_route_planner: "Jelaskan mengapa rute ini direkomendasikan dan faktor risiko utamanya.",
  scenario_simulator: "Jelaskan dampak skenario ini dibandingkan baseline dan tindakan yang disarankan.",
};

function presentAnswer(answer: string): string {
  return answer
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*[-*]\s+/gm, "• ")
    .trim();
}

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
      const result = await fetch(`${API_BASE}/v1/chat`, {
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
        throw new Error(body.detail ?? `Ringkasan tidak dapat dibuat (HTTP ${result.status})`);
      }
      setResponse((await result.json()) as AIExplainResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ringkasan tidak dapat dibuat karena terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className={`ai-panel ${context.source === "scenario_simulator" ? "ai-panel--scenario" : ""}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3>Ringkasan Keputusan</h3>
          <p>
            Membantu memahami hasil berdasarkan data rute di atas tanpa menghitung ulang skor risiko.
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
          aria-label="Pertanyaan tentang hasil keputusan"
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
          <span>Menyiapkan ringkasan keputusan...</span>
        </div>
      )}

      {error && (
        <div className="app-alert mt-3" role="alert">
          {error}
        </div>
      )}

      {response && (
        <div className="ui-card mt-3">
          <p className="whitespace-pre-wrap text-sm leading-6 text-slate-800">{presentAnswer(response.answer)}</p>
          <p className="mt-2 text-xs text-slate-500">
            {response.handled_by === "llm"
              ? "Ringkasan dibuat dari data hasil analisis"
              : response.handled_by === "fallback"
                ? "Ringkasan otomatis berdasarkan data yang tersedia"
                : "Jawaban otomatis berdasarkan batasan sistem"}
          </p>
        </div>
      )}
    </section>
  );
}
