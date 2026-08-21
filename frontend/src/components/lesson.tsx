"use client";

import { useEffect, useState } from "react";

import type { Concept, LessonContent } from "@/lib/api";
import {
  INTERESTS,
  clarifyLessonDoubt,
  createTeachingDecision,
  generateLesson,
  startReassessment,
  submitReassessmentAnswer,
  type Interest,
  type Reassessment,
  type ReassessmentResult,
} from "@/lib/api";
import VisualizationHost from "@/components/visualization/VisualizationHost";

type Props = {
  subjectId: string;
  sessionId: string;
  concept: Concept;
  onClose: (result?: "passed" | "failed" | "retry") => void;
};

const INTEREST_LABEL: Record<Interest, string> = {
  normal: "Plain",
  cricket: "Cricket",
  movies: "Movies",
  f1: "F1",
  gaming: "Gaming",
  anime: "Anime",
  football: "Football",
  "web-series": "Web Series",
  music: "Music",
};

export default function Lesson({ subjectId, sessionId, concept, onClose }: Props) {
  const [lesson, setLesson] = useState<LessonContent | null>(null);
  const [interest, setInterest] = useState<Interest>("normal");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [question, setQuestion] = useState("");
  const [clarifying, setClarifying] = useState(false);
  const [clarify, setClarify] = useState<Awaited<ReturnType<typeof clarifyLessonDoubt>> | null>(null);
  const [clarifyError, setClarifyError] = useState<string | null>(null);

  // Reassessment state
  const [reassessment, setReassessment] = useState<Reassessment | null>(null);
  const [reassessLoading, setReassessLoading] = useState(false);
  const [reassessError, setReassessError] = useState<string | null>(null);
  const [selectedOption, setSelectedOption] = useState("");
  const [freeResponse, setFreeResponse] = useState("");
  const [freeReasoning, setFreeReasoning] = useState("");
  const [reassessResult, setReassessResult] = useState<ReassessmentResult | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function loadLesson(nextInterest: Interest) {
    setLoading(true);
    setError(null);
    try {
      const decision = await createTeachingDecision(subjectId, sessionId, nextInterest);
      if (!decision.lessonId) {
        throw new Error(decision.status);
      }
      const content = await generateLesson(subjectId, decision.lessonId, nextInterest);
      setLesson(content);
      setInterest(nextInterest);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to build the lesson");
    } finally {
      setLoading(false);
    }
  }

  async function handleInterest(next: Interest) {
    if (next === interest) return;
    await loadLesson(next);
  }

  useEffect(() => {
    loadLesson("normal");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleClarify() {
    if (!question.trim() || !lesson?.lessonId) return;
    setClarifying(true);
    setClarifyError(null);
    try {
      const res = await clarifyLessonDoubt(subjectId, lesson.lessonId, question);
      setClarify(res);
    } catch (err) {
      setClarifyError(err instanceof Error ? err.message : "Clarification failed");
    } finally {
      setClarifying(false);
    }
  }

  async function handleStartReassessment() {
    if (!lesson?.lessonId) return;
    setReassessLoading(true);
    setReassessError(null);
    try {
      const res = await startReassessment(subjectId, lesson.lessonId);
      if (res.status !== "OK" || !res.reassessmentId) {
        throw new Error(res.status);
      }
      setReassessment(res);
    } catch (err) {
      setReassessError(err instanceof Error ? err.message : "Failed to start reassessment");
    } finally {
      setReassessLoading(false);
    }
  }

  async function handleSubmitReassessment() {
    if (!reassessment?.reassessmentId) return;
    setSubmitting(true);
    try {
      const res = await submitReassessmentAnswer(
        subjectId,
        reassessment.reassessmentId,
        reassessment.questionType === "MCQ" ? selectedOption : freeResponse,
        freeReasoning,
        selectedOption,
      );
      setReassessResult(res);
    } catch (err) {
      setReassessError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  // --- Reassessment result screen ---
  if (reassessResult) {
    const passed = reassessResult.outcome === "PASSED";
    const failed = reassessResult.outcome === "FAILED";
    return (
      <div className="pointer-events-auto fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-sm">
        <div className="my-4 w-full max-w-lg rounded-2xl border border-zinc-200 bg-white p-6 shadow-2xl dark:border-zinc-800 dark:bg-zinc-950">
          <div className="text-center">
            <div className={`mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full text-2xl ${
              passed
                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300"
                : "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300"
            }`}>
              {passed ? "\u2713" : "\u2717"}
            </div>
            <h3 className="text-lg font-bold text-black dark:text-zinc-50">
              {passed ? "Great work!" : "Not quite there yet"}
            </h3>
            <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
              {passed
                ? "You demonstrated understanding of the concept."
                : "The lesson needs a different approach."}
            </p>
          </div>

          <div className="mt-4 rounded-lg bg-zinc-50 p-3 text-sm dark:bg-zinc-900">
            <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
              <span>Mastery</span>
              <span className="font-mono font-semibold text-black dark:text-zinc-100">
                {Math.round(reassessResult.mastery * 100)}%
              </span>
            </div>
            <div className="mt-1 flex justify-between text-zinc-600 dark:text-zinc-400">
              <span>Status</span>
              <span className={`font-semibold ${
                reassessResult.conceptStatus === "MASTERED"
                  ? "text-emerald-600 dark:text-emerald-400"
                  : reassessResult.conceptStatus === "DEVELOPING"
                  ? "text-amber-600 dark:text-amber-400"
                  : "text-zinc-600 dark:text-zinc-400"
              }`}>
                {reassessResult.conceptStatus}
              </span>
            </div>
            <div className="mt-1 flex justify-between text-zinc-600 dark:text-zinc-400">
              <span>Attempt</span>
              <span className="font-mono">{reassessResult.attempt} of 3</span>
            </div>
          </div>

          <div className="mt-5 flex gap-3">
            {passed && (
              <button
                onClick={() => onClose("passed")}
                className="flex-1 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-500"
              >
                Continue
              </button>
            )}
            {failed && reassessResult.attempt < 3 && (
              <button
                onClick={() => {
                  setReassessment(null);
                  setReassessResult(null);
                  setSelectedOption("");
                  setFreeResponse("");
                  setFreeReasoning("");
                  // Trigger a new teaching decision by closing with retry
                  onClose("retry");
                }}
                className="flex-1 rounded-lg bg-purple-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-purple-500"
              >
                Try different approach
              </button>
            )}
            {failed && reassessResult.attempt >= 3 && (
              <button
                onClick={() => onClose("failed")}
                className="flex-1 rounded-lg bg-zinc-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-500"
              >
                Back to concept
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // --- Reassessment question screen ---
  if (reassessment) {
    return (
      <div className="pointer-events-auto fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-sm">
        <div className="my-4 w-full max-w-lg rounded-2xl border border-zinc-200 bg-white p-6 shadow-2xl dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-lg font-bold text-black dark:text-zinc-50">Check your understanding</h3>
              <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                Attempt {reassessment.attempt} of 3 &middot; {concept.name}
              </p>
            </div>
            <button
              onClick={() => { setReassessment(null); setReassessError(null); }}
              className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
            >
              ✕
            </button>
          </div>

          <div className="mt-4 rounded-lg bg-zinc-50 p-4 dark:bg-zinc-900">
            <p className="text-sm font-medium text-black dark:text-zinc-100">{reassessment.questionText}</p>
          </div>

          {reassessment.questionType === "MCQ" && reassessment.options.length > 0 && (
            <div className="mt-3 space-y-2">
              {reassessment.options.map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => setSelectedOption(opt.id)}
                  className={`w-full rounded-lg border p-3 text-left text-sm transition-colors ${
                    selectedOption === opt.id
                      ? "border-purple-500 bg-purple-50 text-purple-900 dark:border-purple-400 dark:bg-purple-950 dark:text-purple-100"
                      : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                  }`}
                >
                  <span className="mr-2 font-semibold">{opt.id.toUpperCase()}.</span>
                  {opt.text}
                </button>
              ))}
            </div>
          )}

          {reassessment.questionType === "SHORT_ANSWER" && (
            <div className="mt-3 space-y-2">
              <textarea
                value={freeResponse}
                onChange={(e) => setFreeResponse(e.target.value)}
                placeholder="Your answer..."
                rows={3}
                className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:ring-2 focus:ring-purple-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
              />
              <textarea
                value={freeReasoning}
                onChange={(e) => setFreeReasoning(e.target.value)}
                placeholder="Explain your reasoning..."
                rows={2}
                className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:ring-2 focus:ring-purple-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
              />
            </div>
          )}

          {reassessError && <p className="mt-2 text-xs text-red-600 dark:text-red-400">{reassessError}</p>}

          <div className="mt-4">
            <button
              onClick={handleSubmitReassessment}
              disabled={submitting || (reassessment.questionType === "MCQ" ? !selectedOption : !freeResponse.trim())}
              className="w-full rounded-lg bg-purple-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-purple-500 disabled:opacity-50"
            >
              {submitting ? "Evaluating..." : "Submit answer"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // --- Main lesson screen ---
  return (
    <div className="pointer-events-auto fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-sm">
      <div className="my-4 w-full max-w-2xl rounded-2xl border border-zinc-200 bg-white p-6 shadow-2xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-xl font-bold text-black dark:text-zinc-50">{concept.name}</h3>
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              Adaptive lesson · {lesson ? lesson.teachingStrategy?.replace(/_/g, " ").toLowerCase() : "teaching"}
              {lesson?.rootCause ? ` · fixing ${lesson.rootCause.replace(/_/g, " ").toLowerCase()}` : ""}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <div className="flex flex-wrap items-center gap-1 rounded-lg bg-zinc-100 p-1 dark:bg-zinc-800">
                {INTERESTS.map((int) => (
                  <button
                    key={int}
                    onClick={() => handleInterest(int)}
                    disabled={loading}
                    className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-50 ${
                      interest === int
                        ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-100"
                        : "text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                    }`}
                  >
                    {INTEREST_LABEL[int]}
                  </button>
                ))}
              </div>
              <span className="rounded-full bg-purple-100 px-2.5 py-1 text-[11px] font-semibold text-purple-700 dark:bg-purple-900 dark:text-purple-200">
                {INTEREST_LABEL[interest]}
              </span>
            </div>
          </div>
          <button
            onClick={() => onClose()}
            aria-label="Close"
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
          >
            ✕
          </button>
        </div>

        {loading && <p className="mt-6 text-sm text-zinc-500">Building your lesson…</p>}
        {error && <p className="mt-6 text-sm text-red-600 dark:text-red-400">{error}</p>}

        {!loading && lesson && (
          <div className="mt-5 space-y-5">
            {lesson.analogy && (
              <div className="rounded-xl border border-purple-200 bg-purple-50 p-4 dark:border-purple-800 dark:bg-purple-950">
                <h4 className="text-sm font-bold text-purple-800 dark:text-purple-200">
                  {INTEREST_LABEL[interest]} lens
                </h4>
                <p className="mt-2 text-sm leading-relaxed text-purple-900 dark:text-purple-100">
                  {lesson.analogy.scene}
                </p>
                {lesson.analogy.mapping.length > 0 && (
                  <ul className="mt-3 space-y-1.5">
                    {lesson.analogy.mapping.map((m, i) => (
                      <li key={i} className="text-xs text-purple-800 dark:text-purple-200">
                        <span className="font-semibold">{m.element}</span> →{" "}
                        <span className="font-semibold">{m.mappedTo}</span>: {m.description}
                      </li>
                    ))}
                  </ul>
                )}
                <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
                  <div className="rounded-lg bg-emerald-100 p-2.5 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-100">
                    <span className="font-semibold">Where it works: </span>
                    {lesson.analogy.analogy_works}
                  </div>
                  <div className="rounded-lg bg-rose-100 p-2.5 text-rose-900 dark:bg-rose-950 dark:text-rose-100">
                    <span className="font-semibold">Where it breaks: </span>
                    {lesson.analogy.analogy_breaks}
                  </div>
                </div>
              </div>
            )}

            {lesson.visualizationSpec && Object.keys(lesson.visualizationSpec).length > 0 && (
              <VisualizationHost
                spec={lesson.visualizationSpec as never}
              />
            )}

            <div className="rounded-xl bg-zinc-900 p-4 text-white dark:bg-zinc-100 dark:text-black">
              <p className="text-base leading-relaxed">{lesson.explanation}</p>
            </div>

            {lesson.keyPoints.length > 0 && (
              <div>
                <h4 className="mb-1 text-sm font-semibold text-black dark:text-zinc-100">Key points</h4>
                <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-700 dark:text-zinc-300">
                  {lesson.keyPoints.map((pt, i) => (
                    <li key={i}>{pt}</li>
                  ))}
                </ul>
              </div>
            )}

            {lesson.sourceChunks.length > 0 && (
              <p className="text-[11px] text-zinc-400">
                Grounded in {lesson.sourceChunks.length} source chunk
                {lesson.sourceChunks.length === 1 ? "" : "s"}: {lesson.sourceChunks.join(", ")}
              </p>
            )}

            <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
              <h4 className="text-sm font-semibold text-black dark:text-zinc-100">
                Still confused? Ask a doubt
              </h4>
              <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                Answered strictly from your uploaded material.
              </p>
              <div className="mt-3 flex gap-2">
                <input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleClarify()}
                  placeholder="e.g. What exactly does forwarding pass between stages?"
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:ring-2 focus:ring-purple-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
                />
                <button
                  onClick={handleClarify}
                  disabled={clarifying || !question.trim()}
                  className="shrink-0 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-purple-500 disabled:opacity-50"
                >
                  {clarifying ? "…" : "Ask"}
                </button>
              </div>
              {clarifyError && <p className="mt-2 text-xs text-red-600 dark:text-red-400">{clarifyError}</p>}
              {clarify && (
                <div
                  className={`mt-3 rounded-lg p-3 text-sm ${
                    clarify.covered
                      ? "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-100"
                      : "bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-100"
                  }`}
                >
                  <p className="leading-relaxed">{clarify.answer}</p>
                  {clarify.disclaimer && (
                    <p className="mt-1.5 text-xs font-medium">{clarify.disclaimer}</p>
                  )}
                  {clarify.sourceChunks.length > 0 && (
                    <p className="mt-1.5 text-[11px] opacity-70">
                      From chunk{clarify.sourceChunks.length === 1 ? "" : "s"}:{" "}
                      {clarify.sourceChunks.join(", ")}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Check your understanding button */}
            <button
              onClick={handleStartReassessment}
              disabled={reassessLoading}
              className="w-full rounded-xl border-2 border-purple-300 bg-purple-50 px-4 py-3 text-sm font-semibold text-purple-700 transition-colors hover:bg-purple-100 disabled:opacity-50 dark:border-purple-700 dark:bg-purple-950 dark:text-purple-200 dark:hover:bg-purple-900"
            >
              {reassessLoading ? "Generating question..." : "Check your understanding"}
            </button>
            {reassessError && <p className="mt-2 text-xs text-red-600 dark:text-red-400">{reassessError}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
