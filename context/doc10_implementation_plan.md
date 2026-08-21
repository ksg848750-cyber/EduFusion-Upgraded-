# EduFusion — Document 10: Implementation Plan
*Technical Design Phase. Complete & Finalized Document.*

---

## Governing Principle

> **We build EduFusion in feature-by-feature vertical slices, not horizontal layers.**
> We do NOT build "all backend first" or "all UI first".
> Every slice connects: **Backend Service $\longleftrightarrow$ Data Schema $\longleftrightarrow$ UI Component $\longleftrightarrow$ Integration Test**.
> A feature is only **DONE** when the code works, the API works, the database persists, the UI renders, errors are handled, and the AI outputs pass validation tests.

---

## Golden Development Loop

```
1. UNDERSTAND ──► 2. DESIGN ──► 3. IMPLEMENT ──► 4. TEST ──► 5. INTEGRATE
     (PRD/Doc)        (Schemas)     (API & UI)      (AI/DB)     (Milestone)
```

---

## 8 Incremental Build Milestones

```
MILESTONE 1: FOUNDATION & AUTH
  ├─ Git repo & directory structure (`frontend/` & `backend/`)
  ├─ Supabase Auth setup + JWT issuance
  ├─ FastAPI server + Supabase-JWT (JWKS) verification middleware
  └─ Supabase PostgreSQL connection + `users` / `profiles` table setup

MILESTONE 2: KNOWLEDGE INGESTION & GRAPH
  ├─ PDF extraction (PyMuPDF / pypdf) with page retention
  ├─ Structural cleaning & semantic document chunking
  ├─ pgvector Vector Search index setup (Supabase PostgreSQL)
  ├─ LLM Concept & Relationship Extraction (Pydantic validated)
  ├─ Deterministic Graph Validator (Cycle & edge checking)
  └─ Knowledge Graph UI Map (Stitch checkpoint #1)

MILESTONE 3: ADAPTIVE LEARNER MODEL & TOPIC UNDERSTANDING
  ├─ Concept-level Learner Model (`learner_models`, `misconceptions`)
  ├─ Concept study intent choice: [Understand this topic] vs [Test myself]
  ├─ Grounded adaptive explanation (Understand mode, RAG + graph position)
  ├─ Grounded question generation (Test mode, per-concept, source chunks)
  ├─ Answer + reasoning evaluation and evidence-signal extraction
  ├─ Deterministic Backend Mastery Engine (evidence-weighted, bounded)
  ├─ Misconception lifecycle (SUSPECTED → CONFIRMED, evidence-backed)
  └─ Immutable History Logger (`learning_events`; `questions`, `answers`,
     `diagnostic_sessions` evidence store)

  NOTE: The original M3 (Diagnostic Reasoning Engine with root-cause classifier and
  "Why We Think This" bundle) is RENUMBERED. The diagnostic-session/question/answer
  building blocks now live in M3; the root-cause classifier + prerequisite traversal +
  "Why We Think This" evidence bundle move to M4 (Diagnostic Reasoning), keeping the
  canonical 6 root causes and probe architecture from Doc 3. See doc13_m3_learner_model_spec.md.

MILESTONE 4: DIAGNOSTIC REASONING ENGINE
  ├─ Diagnostic Session Manager (`diagnostic_sessions` — sessions now start in M3)
  ├─ Scenario Question Generation with mandatory `diagnosticTargets`
  ├─ Response & Reasoning capture UI (question/answer primitives now in M3)
  ├─ LLM Evidence Signal Extraction (reuses M3 answer-evaluation signals)
  ├─ Root-Cause Classifier (6 categories) + Prerequisite Traversal
  └─ "Why We Think This" UI Evidence Bundle

MILESTONE 5: ADAPTIVE TEACHING ENGINE
  ├─ Dual-Decision Engine (WHAT to teach vs HOW to teach)
  ├─ Strategy Selector (`VISUAL_STEP_BY_STEP`, `WORKED_EXAMPLE`, etc.)
  ├─ RAG Grounding pipeline (retrieving source chunks; M3 establishes the pattern)
  └─ Contextual Interest Analogy engine (`cricket`, `anime`, `normal`)

MILESTONE 6: VISUALIZATION ENGINE ✅ BUILT
  ├─ Declarative `visualizationSpec` Pydantic validator (VisualizationSpec, ProcessFlowSpec, ConceptMapSpec)
  ├─ Visualization Registry implementation (PROCESS_FLOW, CONCEPT_MAP, GENERIC_PROCESS)
  ├─ ProcessFlowRenderer with animated SVG lanes, play/pause/step, speed control
  ├─ ConceptMapRenderer (auto-layout nodes/edges SVG)
  ├─ GenericProcessRenderer (static flow fallback)
  ├─ VisualizationHost entry point with normalizeToRenderable fail-safe
  ├─ LLM prompt generates visualizationSpec in lesson generation
  ├─ Backend persistence (lessons.visualization_spec jsonb)
  └─ Frontend wired into lesson.tsx between interest lens and explanation

MILESTONE 7: REASSESSMENT & LEARNER MODEL CLOSED LOOP ✅ BUILT (tests pending)
  ├─ reassessments table (migration 011)
  ├─ Reassessment question generation (AI prompt + Pydantic schema)
  ├─ 3 API endpoints: POST /reassess, POST /answer, GET /reassessment
  ├─ Mastery update (deterministic, reuses apply_evidence() + update_concept_state())
  ├─ Strategy outcome recording (writes to learner_models.strategy_profile)
  ├─ Misconception resolution (ACTIVE → RESOLVED after PASSED)
  ├─ Diagnosis resolution (OPEN → RESOLVED after PASSED)
  ├─ Max 3 attempt enforcement (UI shows "Back to concept" at attempt 3)
  ├─ Frontend: question card → PASSED/FAILED result screen
  └─ Frontend: retry → close lesson, passed → continue, failed → back to concept

MILESTONE 8: LEARNING HISTORY + DASHBOARD
  ├─ Subject-level progress overview (mastery % per subject)
  ├─ Knowledge Graph concept color-coding by status (UNKNOWN/WEAK/DEVELOPING/MASTERED)
  ├─ Learning history view (past diagnostics, lessons, reassessments)
  └─ Progress tracking across concepts

MILESTONE 9: UI/UX POLISH
  ├─ Consistent styling and color scheme
  ├─ Loading spinners and empty states
  ├─ Mobile responsive layout
  ├─ Smooth transitions and animations
  └─ Error state polish
```

---

## The 13-Step "Wow Moment" Demo Sequence

The hackathon presentation follows this exact end-to-end trace:

1. **Upload**: Student uploads `Computer_Architecture_Notes.pdf`.
2. **Extraction**: EduFusion extracts 37 concepts and builds the Knowledge Graph live (*"Reading material $\rightarrow$ Building graph"*).
3. **Knowledge Map**: Visual graph displays concepts (`data_dependency` $\rightarrow$ `data_hazard` $\rightarrow$ `forwarding`).
4. **Diagnostic**: Student takes a 5-question scenario diagnostic.
5. **Reasoning Submission**: Student answers Q2 incorrectly: *"Instruction B can execute because stages work independently."*
6. **Diagnosis**: EduFusion discovers root cause: `MISSING_PREREQUISITE` (`data_dependency`).
7. **"Why We Think This"**: UI displays exact reasoning quotes from Q2 & Q4 explaining the diagnosis.
8. **Adaptive Path**: System locks `forwarding` and routes student to repair `data_dependency` first.
9. **Lesson Delivery**: EduFusion presents a grounded explanation.
10. **Interest Lens Switch**: Student toggles to *"Cricket"* lens $\rightarrow$ Narrative updates to batting analogy; technical SVG animation remains 100% hardware-accurate.
11. **Visualization**: Interactive pipeline SVG animates register dependency step-by-step.
12. **Reassessment**: Novel scenario tests data dependency $\rightarrow$ Student answers correctly $\rightarrow$ Mastery updates ($21\% \rightarrow 67\%$).
13. **Unlocking**: `data_dependency` resolves $\rightarrow$ Learner Model unlocks `forwarding` as the next step.

---

## AI Output Evaluation & Testing Plan

Because AI outputs are probabilistic, we do NOT rely solely on "code compiles" unit tests.

### 1. Controlled Evaluation Dataset
- **Material**: `Computer_Architecture_Notes.pdf`.
- **Pre-labeled Knowledge Map**: 5 core concepts (`instruction_cycle`, `pipeline_stages`, `data_dependency`, `data_hazard`, `forwarding`).
- **Test Metric**: LLM concept extraction must identify all 5 core concepts with correct prerequisite directionality.

### 2. Predefined Learner Test Personas
- **Persona A (Missing Prerequisite)**: Fails timing questions $\rightarrow$ System MUST diagnose `MISSING_PREREQUISITE`.
- **Persona B (Misconception)**: Claims independent stages $\rightarrow$ System MUST diagnose `MISCONCEPTION`.
- **Persona C (Solid Understanding)**: Answers correctly $\rightarrow$ System MUST advance to next node without unnecessary intervention.

### 3. Golden End-to-End Test Case
A automated integration test executing the complete 13-step sequence from PDF upload to mastery mutation. Must pass cleanly before deployment.

---

## Definition of Done (Slice Completion Criteria)

A vertical slice is marked **DONE** only when:
- [x] Python/FastAPI business logic functions pass unit tests.
- [x] Pydantic schemas validate all incoming/outgoing payloads.
- [x] Supabase PostgreSQL tables persist records correctly.
- [x] Next.js UI component renders the feature cleanly.
- [x] Authorization checks prevent cross-user data leaks (`403`).
- [x] Application error envelopes handle AI failure edge cases cleanly.

---

## Master Architecture Phase Summary

All 10 fundamental design documents are complete, aligned, and locked:

| Doc # | Document Title | Status |
|---|---|---|
| **Doc 1** | Data Architecture (Schemas, Indexes, Tables) | ✅ LOCKED |
| **Doc 2** | LLM Knowledge Extraction Architecture (PDF $\rightarrow$ Graph) | ✅ LOCKED |
| **Doc 3** | Diagnostic Intelligence Architecture (Reasoning $\rightarrow$ Root Cause) | ✅ LOCKED |
| **Doc 4** | Adaptive Teaching Engine Architecture (WHAT & HOW Decisions) | ✅ LOCKED |
| **Doc 5** | Visualization Engine Architecture (Declarative Specs & Renderers) | ✅ LOCKED |
| **Doc 6** | Reassessment & Learner Model Architecture (Verification & Memory) | ✅ LOCKED |
| **Doc 7** | API Specification & Flow Architecture (FastAPI & Supabase Auth Contracts) | ✅ LOCKED |
| **Doc 8** | UX / Screen & Interaction Specification (Stitch MCP Design System) | ✅ LOCKED |
| **Doc 9** | Technology Architecture & Learning Guide (Stack & Defense Q&A) | ✅ LOCKED |
| **Doc 10** | Implementation Plan (Milestones, Slices, & Demo Sequence) | ✅ LOCKED |

---

*Document 10 complete. Technical Design Phase finished. Ready for Implementation!*
