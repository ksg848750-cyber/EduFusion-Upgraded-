# EduFusion — Document 13: M3 Specification — Adaptive Learner Model & Topic Understanding
*Milestone Specification. Authoritative for M3 implementation.*

---

## 1. Goal

M2 answers: *"What does the document/subject contain?"*

M3 answers: *"What does THIS student understand, misunderstand, and need help with?"*

M3 turns the M2 knowledge graph into a **concept-focused learning experience**. When a
student selects a concept/topic from the Learning Map they control their own intent and
choose between two explicit modes:

1. **Understand this topic** — a grounded, student-friendly, adaptive explanation.
2. **Test myself** — grounded questions, answer evaluation, misconception detection, and a
   persistent, evidence-based learner model update.

The learner must NOT have to complete a full quiz before EduFusion offers anything. The
learner's current understanding of each concept is tracked persistently and every mastery
or diagnosis conclusion is backed by explainable evidence.

---

## 2. Student-Controlled Understand / Test Modes

```
M2 Knowledge Graph
        ↓
Selected Concept
        ↓
┌─────────────────────────────┐
│ Understand   │ Test Myself   │
└──────┬────────┴──────┬──────┘
       ↓               ↓
   Grounded        Assessment
   Explanation     + Evaluation
       │               │
       └───────┬───────┘
               ↓
        Learner Model
               ↓
        Diagnosis / Evidence
               ↓
       Future M4 / M5
```

### 2.1 Mode 1 — Understand this topic

- Explains the selected concept progressively (what it is → why it matters → how it works →
  relationship to its parent concept → example → common confusion).
- Uses the concept's position in the M2 knowledge graph (parent/prerequisite context).
- Uses the concept's source chunks and RAG retrieval so the explanation stays grounded in
  the student's uploaded material.
- Never dumps the source document verbatim.
- Adjusts to learner state when evidence exists (e.g. if a misconception is already
  CONFIRMED, the explanation emphasizes the relevant counterexample).
- Ends with a natural transition: *"Think you understand it? Test yourself."*

### 2.2 Mode 2 — Test myself

- Generates a small set of grounded questions about the selected concept
  (definitional, applied/scenario, and misconception-targeted variety).
- Evaluates each answer **and** the student's stated reasoning.
- Does NOT treat the result as a mere score: it analyzes answer patterns, detects possible
  misconceptions, and updates the learner model with the interaction evidence.
- Surfaces evidence-backed hypotheses such as:
  *"Possible misconception: you appear to be confusing SSTF's shortest-seek-time selection
  with FCFS's arrival-order selection."*

---

## 3. Learner Model

Persistent, concept-level, per (user, subject):

- `mastery` — bounded deterministic estimate in [0, 1].
- `status` — canonical concept state: `UNKNOWN`, `WEAK`, `DEVELOPING`, `MASTERED`.
- `confidence` — how much evidence supports the mastery estimate.
- `interactionCount`, `correctCount`, `incorrectCount` — evidence counts.
- `lastAssessedAt` — last interaction timestamp.
- `overallMastery` — subject-level aggregate.
- `version` — optimistic-concurrency counter.

Current-state + event-history model (per AGENTS.md §5):
- `learner_models` = current state.
- `misconceptions` = current misconception state.
- `answers`, `diagnostic_sessions`, `questions`, `learning_events` = historical evidence.

---

## 4. Mastery / Evidence Model

**The LLM never chooses a mastery percentage.** Mastery updates are computed deterministically
by the backend engine.

For each evaluated answer:

```
ΔM = OutcomeWeight × ReasoningWeight × DifficultyModifier × IndependenceFactor
mastery = clamp(mastery + ΔM, 0, 1)
```

- **OutcomeWeight**: `correct` = +0.35, `incorrect` = −0.20.
- **ReasoningWeight**: `SOLID` = 1.0, `PARTIAL` = 0.7, `POOR` = 0.5
  (reasoning quality is LLM-evaluated but then applied deterministically).
- **DifficultyModifier** (concept difficulty 1–5): 1→0.85, 2→0.9, 3→1.0, 4→1.1, 5→1.2.
- **IndependenceFactor**: `0.85 ^ n` where `n` = number of prior answers for this concept
  within the same diagnostic session (avoids double-counting repeated near-identical items).

Status mapping (deterministic):

| Condition | Status |
|---|---|
| no interaction yet | `UNKNOWN` |
| mastery < 0.50 | `WEAK` |
| 0.50 ≤ mastery < 0.85 | `DEVELOPING` |
| mastery ≥ 0.85 and correctCount ≥ 2 | `MASTERED` |
| mastery ≥ 0.85 but insufficient repeated evidence | `DEVELOPING` |

Confidence: `min(0.95, 0.4 + 0.12 × interactionCount)` — rises with accumulated evidence.

---

## 5. Misconception Detection

**Rule 1 (locked, doc3): a wrong answer is NEVER automatically a misconception.**

The LLM proposes a structured `MisconceptionHypothesis` (category + statement + confidence)
ONLY when the answer/reasoning evidence supports one. The backend applies deterministic
lifecycle rules:

- Hypothesis with confidence ≥ 0.60 → persisted as `SUSPECTED` (one signal).
- Same category + same concept already `SUSPECTED` → promoted to `CONFIRMED` (second signal).
- Each row stores `evidenceReferences` (questionId + answerId + signal text) so every
  conclusion is explainable.

Allowed hypothesis categories: `MISCONCEPTION`, `MISSING_PREREQUISITE`, `PROCEDURAL_ERROR`,
`TERMINOLOGY_CONFUSION`, `REPRESENTATION_PROBLEM`. `INSUFFICIENT_EVIDENCE` is reserved for
the probe flow (doc3) and is not auto-created by M3 answer evaluation.

---

## 6. Topic-Level Diagnosis

M3 establishes the foundation for classifying concepts into strong / developing / weak and
for flagging misconceptions and learning gaps **in the context of the graph** — never as an
isolated quiz score.

- A weak `SSTF` is understood relative to `Disk Scheduling Algorithms` and its
  `CONTRASTS_WITH`/`INSTANCE_OF` edges.
- Learner state retrieval is per-concept and per-subject, so later milestones can traverse
  prerequisites and build recovery plans.
- No over-engineered recovery-plan/ranking system in M3.

---

## 7. Grounding Requirements

- **Understand**: the LLM context includes the concept's own `sourceReferences` chunks
  (exact) plus vector retrieval on the concept name when needed. Sections must reference
  actual source chunk indices; the backend validates that referenced chunks were actually
  provided (no hallucinated sources).
- **Test**: question generation is grounded in the concept's source chunks, expected
  understanding, and common misconceptions from the M2 concept row.
- **Evaluation**: the evaluator sees the question's `expectedAnswer`, `expectedReasoning`,
  the concept's `expectedUnderstanding`/`commonMisconceptions`, and the student's response +
  reasoning.
- All LLM output passes Pydantic validation before persistence (locked rule).

---

## 8. How M3 Consumes the M2 Knowledge Graph

- Selected concept (name, description, difficulty, expectedUnderstanding,
  commonMisconceptions, sourceReferences) from `concepts`.
- Parent / child / related context from `concept_relationships`
  (`PART_OF`, `INSTANCE_OF`, `PREREQUISITE_OF`, `DEPENDS_ON`, `CONTRASTS_WITH`, `RELATED_TO`).
- Source chunks referenced by the concept and by its relationships.
- The graph's structural position is injected into both explain and question prompts.

---

## 9. Inputs for M4 / M5

- **M4 (Adaptive Teaching)**: learner model concept states, confirmed misconceptions,
  `learning_events`, and strategy-affecting evidence (correct/incorrect + reasoning quality).
- **M5 (Visualization)**: M3 explanation/lesson text targets and the concept context that the
  visualization registry will illustrate; M3 does NOT build visualization specs.
- **M6 (Reassessment)**: `answers`, `diagnostic_sessions`, `questions`, and the deterministic
  mastery engine are the direct building blocks for targeted reassessment.

---

## 10. Out of Scope for M3

- Probes / 2-stage investigation loop UI (doc3) — architecture preserved, not built.
- Root-cause diagnosis pipeline (`diagnoses` table, "Why We Think This" bundle).
- Adaptive teaching strategy selection (M4), lessons table.
- Visualization registry / renderers (M5).
- Targeted reassessment with PASSED/FAILED/INCONCLUSIVE (M6).
- Gamification, analytics dashboards, interest-context lenses.
- Re-ranking / recovery-plan engine.

---

## 11. Acceptance Criteria

1. Existing M2 knowledge graph loads unchanged.
2. Student selects a concept and sees **[Understand] [Test Myself]**.
3. Understand mode produces a grounded explanation with visible source evidence.
4. Test mode produces grounded questions.
5. Student answers (response + reasoning).
6. Answers are evaluated (correctness + reasoning quality).
7. Learner model updates deterministically from evidence.
8. Evidence is persisted (`answers`, `questions`, `diagnostic_sessions`, `learner_models`,
   `learning_events`, `misconceptions`).
9. Possible misconceptions are surfaced only when supported by evidence.
10. A concept's learner state can be retrieved again later.
11. M2 functionality remains intact (no regression).
12. Backend tests pass; frontend typecheck/lint pass.
13. End-to-end verification against a real uploaded subject.

---

## 12. Tests Required

- Mastery engine unit tests (bounds, transitions, status mapping, independence factor).
- Misconception lifecycle tests (SUSPECTED → CONFIRMED, evidence accumulation).
- AI prompt/validation tests (explanation, question set, evaluation — with fake provider,
  including retry-on-invalid behavior).
- Endpoint tests (auth enforced, explain/test/answer flows with mocked services,
  deterministic learner update).
- Regression: full existing suite must stay green.