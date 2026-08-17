"use client";

import { useState } from "react";
import type { AIExplainContext } from "@/lib/aiExplain";

interface AIExplainResponse {
  answer: string;
  handled_by: "rule" | "llm";
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
    <section className="mt-4 rounded-lg border border-sky-200 bg-sky-50 p-4 dark:border-sky-900 dark:bg-sky-950/30">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">Jelaskan dengan AI Explain</h3>
          <p className="text-xs text-zinc-600 dark:text-zinc-400">
            AI hanya menjelaskan hasil model dan SHAP di atas; AI tidak menghitung skor risiko.
          </p>
        </div>
        <span className="rounded-full bg-sky-100 px-2 py-1 text-xs font-medium text-sky-800 dark:bg-sky-900 dark:text-sky-200">
          {context.source === "scenario_simulator" ? "Konteks skenario" : "Konteks rute"}
        </span>
      </div>

      <form onSubmit={handleExplain} className="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={1000}
          aria-label="Pertanyaan untuk AI Explain"
          className="min-w-0 flex-1 rounded border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="rounded bg-sky-700 px-4 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-50"
        >
          {loading ? "Menjelaskan..." : "Jelaskan"}
        </button>
      </form>

      {error && (
        <div className="mt-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {response && (
        <div className="mt-3 rounded border border-sky-200 bg-white px-4 py-3 dark:border-sky-900 dark:bg-zinc-950">
          <p className="whitespace-pre-wrap text-sm leading-6 text-zinc-800 dark:text-zinc-200">{response.answer}</p>
          <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
            {response.handled_by === "llm" ? `Dijelaskan oleh ${response.model ?? "AI Explain"}` : "Jawaban guardrail otomatis"}
          </p>
        </div>
      )}
    </section>
  );
}
