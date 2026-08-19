"use client";

import { useEffect, useState } from "react";

import type { Concept, ConceptLearner } from "@/lib/api";
import {
  explainConcept,
  fetchConceptLearner,
} from "@/lib/api";
import ConceptTest from "@/components/concept-test";

type Props = {
  subjectId: string;
  concept: Concept;
  mode: "understand" | "test";
  onClose: () => void;
  onModeChange: (mode: "understand" | "test") => void;
};

const STATUS_STYLE: Record<string, string> = {
  UNKNOWN: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
  WEAK: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-200",
  DEVELOPING: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-200",
  MASTERED: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-200",
};

export default function ConceptStudy({ subjectId, concept, mode, onClose, onModeChange }: Props) {
  const [learner, setLearner] = useState<ConceptLearner | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [explanation, setExplanation] = useState<Awaited<ReturnType<typeof explainConcept>>["explanation"] | null>(null);
  const [explaining, setExplaining] = useState(false);

  async function loadLearner() {
    try {
      const l = await fetchConceptLearner(subjectId, concept.id);
      setLearner(l);
    } catch {
      // learner state is best-effort; never block study flow on it
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const l = await fetchConceptLearner(subjectId, concept.id);
        if (!cancelled) setLearner(l);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load learner state");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    init();
    return () => {
      cancelled = true;
    };
  }, [subjectId, concept.id]);

  async function handleExplain() {
    setExplaining(true);
    setError(null);
    try {
      const res = await explainConcept(subjectId, concept.id);
      setExplanation(res.explanation);
      await loadLearner();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Explanation failed");
    } finally {
      setExplaining(false);
    }
  }

  return (
    <div className="pointer-events-auto fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-sm">
      <div className="my-4 w-full max-w-2xl rounded-2xl border border-zinc-200 bg-white p-6 shadow-2xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-xl font-bold text-black dark:text-zinc-50">{concept.name}</h3>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-1 rounded-lg bg-zinc-100 p-0.5 dark:bg-zinc-800">
                <button
                  onClick={() => onModeChange("understand")}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    mode === "understand"
                      ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-100"
                      : "text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                  }`}
                >
                  Understand
                </button>
                <button
                  onClick={() => onModeChange("test")}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    mode === "test"
                      ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-100"
                      : "text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                  }`}
                >
                  Test myself
                </button>
              </div>
              {learner && (
                <span
                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                    STATUS_STYLE[learner.state.status] ?? STATUS_STYLE.UNKNOWN
                  }`}
                >
                  {learner.state.status}
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
          >
            ✕
          </button>
        </div>

        {loading && <p className="mt-6 text-sm text-zinc-500">Loading learner state…</p>}

        {error && <p className="mt-6 text-sm text-red-600 dark:text-red-400">{error}</p>}

        {!loading && mode === "understand" && (
          <div className="mt-5 space-y-5">
            {learner && (
              <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  Your current state
                </h4>
                <div className="mt-2 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                  <div>
                    <p className="text-xs text-zinc-400">Mastery</p>
                    <p className="font-medium text-zinc-900 dark:text-zinc-100">
                      {Math.round(learner.state.mastery * 100)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-zinc-400">Confidence</p>
                    <p className="font-medium text-zinc-900 dark:text-zinc-100">
                      {Math.round(learner.state.confidence * 100)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-zinc-400">Interactions</p>
                    <p className="font-medium text-zinc-900 dark:text-zinc-100">
                      {learner.state.interactionCount}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-zinc-400">Correct</p>
                    <p className="font-medium text-zinc-900 dark:text-zinc-100">
                      {learner.state.correctCount}/{learner.state.interactionCount}
                    </p>
                  </div>
                </div>
                {learner.misconceptions.length > 0 && (
                  <div className="mt-3 space-y-2 border-t border-zinc-200 pt-3 dark:border-zinc-800">
                    <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                      Suspected misconceptions
                    </p>
                    {learner.misconceptions.map((m) => (
                      <div key={m.id} className="rounded-lg bg-white p-2.5 text-sm dark:bg-zinc-950">
                        <p className="font-medium text-zinc-800 dark:text-zinc-200">{m.statement}</p>
                        <p className="mt-0.5 text-[11px] text-zinc-400">
                          {m.status} Â· {m.category.replace(/_/g, " ").toLowerCase()} Â· confidence{" "}
                          {Math.round(m.confidence * 100)}%
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {!explanation ? (
              <div className="rounded-xl border border-dashed border-zinc-300 p-6 text-center dark:border-zinc-700">
                <p className="text-sm text-zinc-600 dark:text-zinc-300">
                  EduFusion will explain this topic grounded in your uploaded material and adapted to
                  what you already know.
                </p>
                <button
                  onClick={handleExplain}
                  disabled={explaining}
                  className="mt-4 rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-black dark:hover:bg-zinc-300"
                >
                  {explaining ? "Building explanation…" : "Explain this topic"}
                </button>
              </div>
            ) : (
              <>
                <div className="rounded-xl bg-zinc-900 p-4 text-white dark:bg-zinc-100 dark:text-black">
                  <p className="text-base leading-relaxed">{explanation.summary}</p>
                </div>
                <div className="space-y-4">
                  {explanation.sections.map((s, i) => (
                    <div key={i}>
                      <h4 className="mb-1 text-sm font-semibold text-black dark:text-zinc-100">
                        {s.heading}
                      </h4>
                      <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">{s.body}</p>
                      {s.sourceChunks.length > 0 && (
                        <p className="mt-1 text-[11px] text-zinc-400">
                          Source chunk{s.sourceChunks.length === 1 ? "" : "s"}: {s.sourceChunks.join(", ")}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
                {explanation.example && (
                  <div>
                    <h4 className="mb-1 text-sm font-semibold text-black dark:text-zinc-100">Example</h4>
                    <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
                      {explanation.example}
                    </p>
                  </div>
                )}
                {explanation.commonConfusion && (
                  <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
                    <span className="font-semibold">Watch out: </span>
                    {explanation.commonConfusion}
                  </div>
                )}
                {explanation.sourceChunks.length > 0 && (
                  <p className="text-[11px] text-zinc-400">
                    Grounded in {explanation.sourceChunks.length} source chunk
                    {explanation.sourceChunks.length === 1 ? "" : "s"}:{" "}
                    {explanation.sourceChunks.join(", ")}
                  </p>
                )}
                <button
                  onClick={() => onModeChange("test")}
                  className="w-full rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-black dark:hover:bg-zinc-300"
                >
                  Think you understand it? Test yourself →
                </button>
              </>
            )}
          </div>
        )}

        {!loading && mode === "test" && (
          <div className="mt-5">
            <ConceptTest subjectId={subjectId} concept={concept} onClose={onClose} />
          </div>
        )}
      </div>
    </div>
  );
}