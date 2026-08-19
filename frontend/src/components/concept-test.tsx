"use client";

import { useEffect, useState } from "react";

import type {
  Concept,
  DiagnosticStartResponse,
  EvidenceBundleResponse,
  ProbeStartResponse,
  TestQuestion,
} from "@/lib/api";
import {
  createFinalDiagnosis,
  getDiagnosticDecision,
  getEvidenceBundle,
  startDiagnostic,
  startDiagnosticProbe,
  submitDiagnosticAnswer,
} from "@/lib/api";
import Lesson from "@/components/lesson";

type Phase = "starting" | "questions" | "probe" | "done";

type AnswerResult = {
  answerId: string;
  correct: boolean;
  reasoningQuality: string;
  explanation: string;
  evidenceSignals: string[];
  misconception: { category: string; statement: string; confidence: number } | null;
};

type WhyWeThinkThis = {
  rootCause: string;
  confidence: number;
  statement: string;
  evidence: Array<{
    questionId: string;
    questionText: string;
    reasoning: string;
    correct: boolean;
    reasoningQuality: string | null;
    evidenceSignals: string[];
  }>;
};

export default function ConceptTest({
  subjectId,
  concept,
  onClose,
}: {
  subjectId: string;
  concept: Concept;
  onClose: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("starting");
  const [error, setError] = useState<string | null>(null);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<TestQuestion[]>([]);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [feedback, setFeedback] = useState<AnswerResult | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [probe, setProbe] = useState<ProbeStartResponse | null>(null);
  const [probeFeedback, setProbeFeedback] = useState<AnswerResult | null>(null);

  const [why, setWhy] = useState<WhyWeThinkThis | null>(null);
  const [showLesson, setShowLesson] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const res: DiagnosticStartResponse = await startDiagnostic(subjectId, concept.id);
        if (cancelled) return;
        if (res.status !== "TARGET_FOUND" || !res.sessionId) {
          const reason = res.error ?? "No diagnostic could be started for this concept.";
          setError(reason);
          setPhase("starting");
          return;
        }
        setSessionId(res.sessionId);
        setQuestions(res.questions ?? []);
        setPhase((res.questions?.length ?? 0) > 0 ? "questions" : "done");
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Test failed to start");
      }
    }
    init();
    return () => {
      cancelled = true;
    };
  }, [subjectId, concept.id]);

  const currentQuestion = questions[questionIndex];

  async function handleAnswer(response: string, reasoning: string, selectedOptionId?: string) {
    if (!sessionId || !currentQuestion) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await submitDiagnosticAnswer(
        subjectId,
        sessionId,
        currentQuestion.id,
        response,
        reasoning,
        selectedOptionId,
      );
      setFeedback(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit answer");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleNext() {
    setFeedback(null);
    if (questionIndex < questions.length - 1) {
      setQuestionIndex((i) => i + 1);
    } else {
      await analyze();
    }
  }

  async function analyze() {
    if (!sessionId) return;
    setError(null);
    try {
      const decision = await getDiagnosticDecision(subjectId, sessionId);
      if (decision.needsProbe) {
        await startProbe();
      } else {
        await finish();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not analyze your answers");
    }
  }

  async function startProbe() {
    if (!sessionId) return;
    try {
      const p = await startDiagnosticProbe(subjectId, sessionId);
      setProbe(p);
      setPhase("probe");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not prepare the next question");
      await finish();
    }
  }

  async function handleProbeAnswer(response: string, reasoning: string, selectedOptionId?: string) {
    if (!sessionId || !probe?.probeQuestion) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await submitDiagnosticAnswer(
        subjectId,
        sessionId,
        probe.probeQuestion.id,
        response,
        reasoning,
        selectedOptionId,
      );
      setProbeFeedback(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit answer");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleProbeDone() {
    setProbeFeedback(null);
    setPhase("done");
    await finish();
  }

  async function finish() {
    if (!sessionId) return;
    setError(null);
    try {
      const diagnosis = await createFinalDiagnosis(subjectId, sessionId);
      const bundle: EvidenceBundleResponse = await getEvidenceBundle(subjectId, sessionId);
      setWhy({
        rootCause: diagnosis.rootCause,
        confidence: diagnosis.confidence,
        statement:
          (diagnosis.investigation as { statement?: string })?.statement ??
          "Your answers were analysed against the expected understanding of this topic.",
        evidence: (bundle.evidence ?? []).map((e) => ({
          questionId: e.questionId,
          questionText: e.questionText,
          reasoning: e.reasoning,
          correct: e.correct,
          reasoningQuality: e.reasoningQuality,
          evidenceSignals: e.evidenceSignals,
        })),
      });
      setPhase("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not finalize the test");
    }
  }

  if (phase === "starting" && !error) {
    return (
      <div className="mt-10 flex flex-col items-center justify-center space-y-3 py-10 text-zinc-500">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-zinc-100" />
        <p className="text-sm">Preparing your questions…</p>
      </div>
    );
  }

  if (error && phase !== "questions" && phase !== "probe") {
    return (
      <div className="mt-6 space-y-4">
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        <button
          onClick={onClose}
          className="rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-black dark:hover:bg-zinc-300"
        >
          Close
        </button>
      </div>
    );
  }

  if (phase === "questions" && currentQuestion) {
    return (
      <div className="space-y-4">
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <div className="flex items-center justify-between">
          <p className="text-xs text-zinc-500">
            Question {questionIndex + 1} of {questions.length}
          </p>
          <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-[11px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
            {currentQuestion.questionType.replace(/_/g, " ").toLowerCase()} · difficulty{" "}
            {currentQuestion.difficulty}
          </span>
        </div>
        <QuestionForm
          key={currentQuestion.id}
          question={currentQuestion}
          submitting={submitting}
          onSubmit={handleAnswer}
        />
        {feedback && <FeedbackCard result={feedback} />}
        {feedback && (
          <div className="flex justify-end">
            <button
              onClick={handleNext}
              className="rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-black dark:hover:bg-zinc-300"
            >
              {questionIndex < questions.length - 1 ? "Next question →" : "Finish test"}
            </button>
          </div>
        )}
      </div>
    );
  }

  if (phase === "probe" && probe?.probeQuestion) {
    return (
      <div className="space-y-4">
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <div className="flex items-center justify-between">
          <p className="text-xs text-zinc-500">One more question</p>
          <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-[11px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
            {probe.probeQuestion.questionType.replace(/_/g, " ").toLowerCase()}
          </span>
        </div>
        <QuestionForm
          key={probe.probeQuestion.id}
          question={probe.probeQuestion}
          submitting={submitting}
          onSubmit={handleProbeAnswer}
        />
        {probeFeedback && <FeedbackCard result={probeFeedback} />}
        {probeFeedback && (
          <div className="flex justify-end">
            <button
              onClick={handleProbeDone}
              className="rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-black dark:hover:bg-zinc-300"
            >
              See your result
            </button>
          </div>
        )}
      </div>
    );
  }

  if (phase === "done" && why) {
    const quoted = why.evidence
      .filter((e) => e.reasoning && e.reasoning.trim().length > 0)
      .slice(0, 3);
    return (
      <div className="space-y-4">
        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            How you did
          </h4>
          <p className="mt-2 text-base font-semibold text-black dark:text-zinc-50">
            {why.statement}
          </p>

          <div className="mt-3 rounded-lg border border-teal-200 bg-teal-50 px-4 py-3 dark:border-teal-800 dark:bg-teal-950">
            <p className="text-xs font-semibold uppercase tracking-wide text-teal-700 dark:text-teal-300">
              What we think
            </p>
            <p className="mt-1 text-sm text-zinc-800 dark:text-zinc-100">
              {rootCauseLabel(why.rootCause)}
            </p>
          </div>

          {quoted.length > 0 && (
            <div className="mt-4 space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                What your answers showed us
              </p>
              {quoted.map((e) => (
                <blockquote
                  key={e.questionId}
                  className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-300"
                >
                  <span className="text-xs font-medium text-zinc-400">
                    You wrote:
                  </span>{" "}
                  “{e.reasoning}”
                </blockquote>
              ))}
            </div>
          )}

          <p className="mt-3 text-xs text-zinc-500">
            Based on {why.evidence.length} of your answer
            {why.evidence.length === 1 ? "" : "s"}.
          </p>
        </div>
        <div className="flex justify-end gap-2">
          {sessionId && (
            <button
              onClick={() => setShowLesson(true)}
              className="rounded-lg bg-purple-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-purple-500"
            >
              Start adaptive lesson
            </button>
          )}
          <button
            onClick={onClose}
            className="rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-black dark:hover:bg-zinc-300"
          >
            Done
          </button>
        </div>
      </div>
    );
  }

  return null;
}

function rootCauseLabel(rootCause: string): string {
  switch (rootCause) {
    case "INSUFFICIENT_EVIDENCE":
      return "We couldn't attribute a single clear cause from your answers. Explaining your reasoning on each question would help us pinpoint it.";
    case "MISCONCEPTION":
      return "A specific misunderstanding about how this topic works is behind your errors.";
    case "MISSING_PREREQUISITE":
      return "A foundational concept this topic builds on isn't solid yet — that's blocking this one.";
    case "PROCEDURAL_ERROR":
      return "Your approach was right in parts, but a step was applied incorrectly.";
    case "TERMINOLOGY_CONFUSION":
      return "Related terms were used interchangeably in a way that changes the meaning.";
    case "REPRESENTATION_PROBLEM":
      return "The way the idea was shown didn't line up with the intended meaning.";
    default:
      return "Your answers were analysed against the expected understanding of this topic.";
  }
}

function FeedbackCard({ result }: { result: AnswerResult }) {
  return (
    <div
      className={`rounded-xl border p-4 ${
        result.correct
          ? "border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950"
          : "border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950"
      }`}
    >
      <p
        className={`text-sm font-semibold ${
          result.correct
            ? "text-emerald-700 dark:text-emerald-200"
            : "text-amber-700 dark:text-amber-200"
        }`}
      >
        {result.correct ? "Correct" : "Not quite"}
        {result.reasoningQuality === "SOLID" && " — solid reasoning"}
        {result.reasoningQuality === "PARTIAL" && " — partial reasoning"}
        {result.reasoningQuality === "POOR" && " — weak reasoning"}
      </p>
      {result.explanation && (
        <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">{result.explanation}</p>
      )}
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
  const isMcq =
    (question.questionType === "MCQ" || question.questionType === "PROBE") &&
    question.options.length > 0;
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
            : "Explain your reasoning (helps EduFusion assess)"}
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