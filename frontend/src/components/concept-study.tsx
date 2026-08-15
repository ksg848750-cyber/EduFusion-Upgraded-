"use client";

import { useEffect, useState } from "react";

import type { Concept, ConceptLearner } from "@/lib/api";
import {
  explainConcept,
  fetchConceptLearner,
  startConceptTest,
  submitAnswer,
  TestQuestion,
} from "@/lib/api";

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

  const [test, setTest] = useState<{ sessionId: string; questions: TestQuestion[] } | null>(null);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [startingTest, setStartingTest] = useState(false);
  const [feedback, setFeedback] = useState<Awaited<ReturnType<typeof submitAnswer>> | null>(null);
  const [submitting, setSubmitting] = useState(false);

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

  async function handleStartTest() {
    setStartingTest(true);
    setError(null);
    try {
      const res = await startConceptTest(subjectId, concept.id);
      setTest({ sessionId: res.sessionId, questions: res.questions });
      setQuestionIndex(0);
      setFeedback(null);
      await loadLearner();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the test");
    } finally {
      setStartingTest(false);
    }
  }

  async function handleSubmitAnswer(response: string, reasoning: string, selectedOptionId?: string) {
    if (!test) return;
    setSubmitting(true);
    setError(null);
    try {
      const q = test.questions[questionIndex];
      const res = await submitAnswer(subjectId, test.sessionId, q.id, response, reasoning, selectedOptionId);
      setFeedback(res);
      await loadLearner();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit answer");
    } finally {
      setSubmitting(false);
    }
  }

  const currentQuestion = test?.questions[questionIndex];

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
                          {m.status} · {m.category.replace(/_/g, " ").toLowerCase()} · confidence{" "}
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
          <div className="mt-5 space-y-5">
            {!test && (
              <div className="rounded-xl border border-dashed border-zinc-300 p-6 text-center dark:border-zinc-700">
                <p className="text-sm text-zinc-600 dark:text-zinc-300">
                  Answer questions about this topic. EduFusion evaluates your reasoning — not just
                  whether you are right — and updates your learner model.
                </p>
                <button
                  onClick={handleStartTest}
                  disabled={startingTest}
                  className="mt-4 rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-black dark:hover:bg-zinc-300"
                >
                  {startingTest ? "Preparing questions…" : "Start test"}
                </button>
              </div>
            )}

            {test && currentQuestion && !feedback && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-zinc-500">
                    Question {questionIndex + 1} of {test.questions.length}
                  </p>
                  <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-[11px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                    {currentQuestion.questionType.replace(/_/g, " ").toLowerCase()} · difficulty{" "}
                    {currentQuestion.difficulty}
                  </span>
                </div>
                <QuestionForm
                  question={currentQuestion}
                  submitting={submitting}
                  onSubmit={handleSubmitAnswer}
                />
              </div>
            )}

            {test && feedback && (
              <div className="space-y-4">
                <div
                  className={`rounded-xl border p-4 ${
                    feedback.correct
                      ? "border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950"
                      : "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950"
                  }`}
                >
                  <p
                    className={`text-sm font-semibold ${
                      feedback.correct
                        ? "text-emerald-700 dark:text-emerald-200"
                        : "text-red-700 dark:text-red-200"
                    }`}
                  >
                    {feedback.correct ? "Correct" : "Not quite"}
                    {feedback.reasoningQuality === "SOLID" && " — solid reasoning"}
                    {feedback.reasoningQuality === "PARTIAL" && " — partial reasoning"}
                    {feedback.reasoningQuality === "POOR" && " — weak reasoning"}
                  </p>
                  <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">{feedback.explanation}</p>
                </div>

                {feedback.misconception && (
                  <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
                    <p className="font-semibold">Suspected misconception</p>
                    <p className="mt-1">{feedback.misconception.statement}</p>
                    <p className="mt-0.5 text-[11px]">
                      {feedback.misconception.status} · confidence{" "}
                      {Math.round(feedback.misconception.confidence * 100)}%
                    </p>
                  </div>
                )}

                {learner && (
                  <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900">
                    <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                      Updated learner model
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-4 text-sm">
                      <span
                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                          STATUS_STYLE[learner.state.status] ?? STATUS_STYLE.UNKNOWN
                        }`}
                      >
                        {learner.state.status}
                      </span>
                      <span className="text-zinc-600 dark:text-zinc-300">
                        Mastery {Math.round(learner.state.mastery * 100)}%
                      </span>
                      <span className="text-zinc-600 dark:text-zinc-300">
                        Confidence {Math.round(learner.state.confidence * 100)}%
                      </span>
                      <span className="text-zinc-600 dark:text-zinc-300">
                        {learner.state.interactionCount} interaction
                        {learner.state.interactionCount === 1 ? "" : "s"}
                      </span>
                    </div>
                  </div>
                )}

                <div className="flex justify-end">
                  {questionIndex < test.questions.length - 1 ? (
                    <button
                      onClick={() => {
                        setQuestionIndex((i) => i + 1);
                        setFeedback(null);
                      }}
                      className="rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-black dark:hover:bg-zinc-300"
                    >
                      Next question →
                    </button>
                  ) : (
                    <button
                      onClick={onClose}
                      className="rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-black dark:hover:bg-zinc-300"
                    >
                      Done
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function QuestionForm({
  question,
  submitting,
  onSubmit,
}: {
  question: TestQuestion;
  submitting: boolean;
  onSubmit: (response: string, reasoning: string, selectedOptionId?: string) => void;
}) {
  const isMcq = question.questionType === "MCQ" && question.options.length > 0;
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [response, setResponse] = useState("");
  const [reasoning, setReasoning] = useState("");

  const canSubmit = isMcq ? selectedOptionId !== null : response.trim().length > 0;

  return (
    <div className="space-y-4">
      <p className="text-base font-medium text-black dark:text-zinc-50">{question.questionText}</p>

      {isMcq ? (
        <div role="radiogroup" aria-label="Choose one answer" className="space-y-2">
          {question.options.map((option) => {
            const isSelected = selectedOptionId === option.id;
            return (
              <button
                key={option.id}
                role="radio"
                aria-checked={isSelected}
                onClick={() => setSelectedOptionId(option.id)}
                className={`flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left text-sm transition-colors ${
                  isSelected
                    ? "border-teal-600 bg-teal-50 ring-2 ring-teal-500/30 dark:border-teal-400 dark:bg-teal-950"
                    : "border-zinc-300 bg-white hover:border-teal-500 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                }`}
              >
                <span
                  className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 ${
                    isSelected
                      ? "border-teal-600 bg-teal-600 dark:border-teal-400 dark:bg-teal-400"
                      : "border-zinc-400 dark:border-zinc-500"
                  }`}
                >
                  {isSelected && (
                    <span className="h-2 w-2 rounded-full bg-white dark:bg-black" />
                  )}
                </span>
                <span className="font-medium text-zinc-800 dark:text-zinc-100">
                  <span className="mr-1.5 inline-block w-4 text-zinc-400">{option.id}</span>
                  {option.text}
                </span>
              </button>
            );
          })}
        </div>
      ) : (
        <textarea
          value={response}
          onChange={(e) => setResponse(e.target.value)}
          rows={3}
          placeholder="Your answer…"
          className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/30 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        />
      )}

      <div>
        <label className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
          {isMcq
            ? "Why did you choose this answer?"
            : "Explain your reasoning (helps EduFusion diagnose)"}
        </label>
        <textarea
          value={reasoning}
          onChange={(e) => setReasoning(e.target.value)}
          rows={2}
          placeholder="Why did you answer that way?"
          className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/30 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        />
      </div>
      <div className="flex justify-end">
        <button
          onClick={() =>
            isMcq
              ? onSubmit("", reasoning, selectedOptionId ?? undefined)
              : onSubmit(response, reasoning)
          }
          disabled={submitting || !canSubmit}
          className="rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-100 dark:text-black dark:hover:bg-zinc-300"
        >
          {submitting ? "Evaluating…" : "Submit answer"}
        </button>
      </div>
    </div>
  );
}