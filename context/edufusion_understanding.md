# EduFusion — Final Aligned Understanding
*Supersedes all previous notes. Ground truth before technical design begins.*
*No implementation. No coding. This is the product definition.*

---

## ⚑ Governing Principle — What "MVP" Means For EduFusion

> **MVP = the smallest complete implementation of the actual EduFusion intelligence, restricted to a manageable content scope.**
> **MVP does NOT mean cutting the intelligence. It means building the complete intended intelligence on a controlled scope.**

### What we reduce for MVP
- Number of supported subjects (one: Computer Architecture / CPU Pipelining)
- Size of document libraries
- Number of concurrent users
- Number of visualization renderers (three: Pipeline, Hazard, Forwarding)
- Scope of gamification, voice, analytics, institutional dashboards

### What we do NOT cut or simulate
| Component | Rule |
|---|---|
| LLM concept extraction | Must actually run. Not pre-seeded, not hardcoded |
| Dynamic concept graph | Must be generated from uploaded material |
| Diagnostic reasoning | LLM must analyze actual student reasoning, not pattern-match |
| Root-cause analysis | Six categories, evidence-backed, not `if answer == X: misconception = Y` |
| Prerequisite tracing | Real graph traversal, not hardcoded chains |
| Learner model | Persistent, real, contains mastery + misconceptions + strategy history |
| Adaptive engine | Must actually decide WHAT and HOW based on learner state |
| Interest context | Both normal and interest-based paths must exist |
| Visualization | Mandatory for every intervention. Not optional, not decorative |
| Reassessment | Must target the same gap. Not a generic re-quiz |
| Mastery calculation | Deterministic formula. Not LLM-generated |
| Learner model update | Must persist to MongoDB after every session |

### The test for any proposed shortcut
Before cutting or simulating any component, ask:
> *"If we do this, are we still building EduFusion — or are we building a polished educational chatbot?"*

If the answer is "chatbot" — the shortcut is not allowed.

---

## What EduFusion Is

An adaptive AI learning system that:
1. **Extracts** a concept graph from the student's uploaded material
2. **Models** what the student understands (Learner Model)
3. **Diagnoses** *why* they struggle — not just *that* they struggle
4. **Teaches** the specific gap with explanation + mandatory visualization
5. **Verifies** whether understanding actually improved (Reassessment)
6. **Adapts** strategy when it fails, or repairs the prerequisite

### The Core Loop
```
ASSESS → DIAGNOSE → FIND WHY → DECIDE WHAT → DECIDE HOW
                                                    ↓
              REPEAT ← UPDATE LEARNER MODEL ← REASSESS ← EXPLAIN + VISUALIZE
```

---

## The Real Demo Story

```
Upload: Computer Architecture notes (PDF)
       ↓
EduFusion: "I found 37 concepts and 52 relationships in your material."
       ↓
Concept graph is built from the actual uploaded material
       ↓
Five-question diagnostic (questions chosen for mental-model discovery)
       ↓
EduFusion: "You aren't weak at pipeline hazards.
            You're weak at data dependencies,
            which is a prerequisite for understanding forwarding."
       ↓
Evidence shown: "Why we think this" — Q2 answer, Q4 answer, pattern
       ↓
Targeted explanation + mandatory visualization
       ↓
Adaptive decision visible to student/judge
       ↓
Reassessment of the same gap
       ↓
Mastery: 21% → 67% (calculated deterministically, not LLM-invented)
       ↓
Learner model updated and persisted
       ↓
If failed → different strategy or prerequisite repair
```

**This is the EduFusion demo. Every design decision must support this story.**

---

## Locked Decisions

| Decision | Locked To |
|---|---|
| Core loop | ASSESS → DIAGNOSE → FIND WHY → DECIDE WHAT → DECIDE HOW → EXPLAIN + VISUALIZE → REASSESS → UPDATE → REPEAT |
| Auth | Better Auth + JWT → FastAPI |
| Backend | FastAPI + Python |
| Database | MongoDB Atlas |
| Vector search | MongoDB Atlas Vector Search |
| AI | Groq — Llama 3.3 70B (complex reasoning) + Llama 3.1 8B (simple/fast) |
| Mastery calculation | Deterministic backend formula (formula itself = open decision, but the rule is locked) |
| Visualization delivery | LLM outputs spec → Pydantic validates → renderer renders. Never LLM-generated code |
| Interest context | Optional, not forced. Used when it improves clarity |
| Learning styles | Evidence-based strategy adaptation from outcomes, not fixed categories |
| Gamification/voice | Secondary — cut before diagnosis or visualization |
| LLM-generated frontend code | Never |

---

## Corrections to Antigravity's Earlier Analysis

### ✅ Correction 1: LLM extraction IS part of the MVP

**Antigravity said**: Pre-seed the CPU Pipelining graph. LLM extraction = post-MVP.

**Corrected position**:
- The CPU Pipelining **material** (a specific PDF or notes) can be controlled for demo reliability
- The **concept graph must still be LLM-generated from that material**, not hardcoded
- Architecture: general (supports any uploaded material)
- Demo dataset: controlled (specific CPU Pipelining notes)

**Why this matters**: If asked "is this actually adaptive to uploaded material?", the answer must be **yes**. We cannot demo a hardcoded graph and claim to be an adaptive system.

### ✅ Correction 2: Probe questions stay in the architecture

**Antigravity said**: Cut probe questions entirely. Five questions → diagnosis, full stop.

**Corrected position**:
- MVP demonstrates: five questions → diagnosis
- Architecture supports: five questions → ambiguous? → 1 probe question → diagnosis
- We simply don't need to demonstrate the probe path in the hackathon

### ✅ Correction 3: Diagnostic questions must optimize for mental-model discovery

Diagnostic questions are NOT:
> "What is a pipeline hazard?"

They ARE:
> "Instruction B needs the result produced by instruction A. A is in the EX stage. Can B continue normally? Explain why."

The student's **reasoning** is the signal. The answer exposes whether they understand dependency, timing, and forwarding — not just terminology. This must be an explicit requirement in the AI Architecture document.

### ✅ Correction 4: Mastery formula is NOT locked yet

**Antigravity suggested**: `correctness × difficulty − misconception_penalty + reassessment_bonus`

**Problem with this**: Wrong answer already reduces mastery. Applying a misconception penalty on top of that double-counts the same error. Also, "reasoning quality" needs a scoring rubric before it can be in any formula.

**Corrected position**: Design and justify the mastery model in the Data/AI Architecture documents. For MVP, prefer something simple, transparent, and defensible over something complex and fragile.

### ✅ Correction 5: Embedding model is an explicit open decision

RAG flow is: chunk → **embed** → store → retrieve. We've chosen Groq/Llama for generation, but **Groq is not an embedding provider**. We need to explicitly decide:
- Which model/provider creates the embeddings
- What embedding dimensions
- What similarity metric (cosine, dot product)

This is now added to the open decisions list.

### ✅ Correction 6: Document extraction strategy needs to be specified

Flow says "PDF → extract → chunk" but doesn't say how extraction works. For MVP:
- Text-based PDFs only (PyMuPDF or pypdf)
- Tables/images/scanned PDFs: post-MVP
- OCR: post-MVP

### ✅ Correction 7: "Event sourcing" is the wrong term

**Corrected position**: We want:
- `learner_models` = current state (overwritten on update)
- `learning_events` = immutable historical record

This is **current-state + event history**, not a full event-sourced architecture. No event replay, no projections.

### ✅ Correction 8: Visualization registry should be architecture-wide

The registry should be generic (PipelineRenderer, TreeRenderer, GraphRenderer, SortingRenderer, etc.). The hackathon implements only the three needed for CPU Pipelining (Pipeline, Hazard, Forwarding). Same rule as concept graph: architecture broad, implementation narrow.

### ✅ Correction 9: RAG is primarily for lesson generation, not diagnostic questions

Diagnostic questions test understanding — they're generated from the **concept model + expected correct reasoning**, not by first retrieving source chunks. RAG is valuable for:
- Lesson generation
- Explanation grounding
- Evidence backing

Not necessarily for generating diagnostic questions themselves.

### ✅ Correction 10: "Why we think this" must be a visible UI feature

The evidence layer — showing the judge exactly which answers triggered which diagnosis — is a product feature, not just backend data:

```
EduFusion Diagnosis
──────────────────────────────────
You may have a misconception about pipeline data dependencies.

Why we think this:
  Q2: You answered "Instruction B can execute immediately."
  Q4: You answered "The stages operate independently."

  Both answers suggest you treat pipeline stages as independent.

Confidence: High
```

This is what separates EduFusion from "ChatGPT said you're wrong."

### ✅ Correction 11: Adaptive decision must be visible

When EduFusion changes strategy or targets a prerequisite, the student/judge sees it:

```
"You understand the basic pipeline stages, but your answers suggest
confusion about data dependencies. We'll step back and visualize
how one instruction depends on another before continuing."
```

---

## Open Decisions (Must Be Resolved in Technical Design Phase)

### CRITICAL — blocks everything
| Decision | Description |
|---|---|
| Concept graph schema | Node structure, edge types, prerequisite model, difficulty metadata |
| Diagnosis JSON schema | The return type of the diagnostic endpoint — everything downstream consumes this |
| Learner model schema | Every service reads/writes this |
| Mastery formula | Deterministic, justified, simple for MVP |
| Embedding model + provider | Which model, what dimensions, what similarity metric |

### HIGH — blocks specific subsystems
| Decision | Blocks |
|---|---|
| Document extraction strategy | All of RAG and concept extraction |
| LLM concept/relationship extraction prompts + output schemas | Concept graph generation |
| Visualization registry (schema per type) | Intervention delivery |
| Better Auth ↔ FastAPI JWT verification | Every authenticated endpoint |
| Teaching-strategy taxonomy | Adaptive engine HOW decision |
| RAG chunk metadata schema | Retrieval and grounding |

### MEDIUM — can be documented as MVP assumptions
| Decision | Default assumption |
|---|---|
| Diagnostic question generation strategy | From concept node + expected reasoning |
| Reassessment/adaptation policy | Max 3 attempts → prerequisite repair |
| LLM model allocation | 70B for extraction/diagnosis/lesson, 8B for simpler calls |
| MongoDB indexes | Define during data architecture document |
| MVP screens/navigation | Define during UX document |
| Deployment + secrets | Vercel + Render, define during tech guide |

---

## The Six Root-Cause Categories

These are the only valid diagnostic outputs. The system must classify into one of:

1. **Missing prerequisite** — Student doesn't know something required
2. **Misconception** — Student has an incorrect mental model
3. **Procedural error** — Understands the idea but can't apply the steps
4. **Terminology confusion** — Knows the idea but confuses terms
5. **Representation problem** — Understands text but struggles with diagram/formula
6. **Insufficient evidence** — Not enough signal yet (may trigger probe question in full architecture)

---

## Technical Design Sequence (10 Documents Before Code)

```
1. DATA ARCHITECTURE
   └── Collections, schemas, indexes, vector fields, current-state + event-history model

2. LLM KNOWLEDGE EXTRACTION
   └── PDF → extract text → chunk → embed → store
   └── LLM concept extraction → LLM relationship extraction → graph validation → MongoDB

3. DIAGNOSTIC INTELLIGENCE
   └── Concept selection → question generation (diagnostic value, not topic coverage)
   └── Answer + reasoning analysis → root-cause determination → evidence structuring

4. ADAPTIVE TEACHING ENGINE
   └── WHAT to teach (prerequisite repair, concept, misconception correction, etc.)
   └── HOW to teach (explanation type, visualization type, interest context decision)
   └── Strategy history per learner

5. VISUALIZATION ENGINE
   └── Teaching decision → LLM explanation + visualization spec → Pydantic validation
   └── Renderer registry → animation → fallback path

6. REASSESSMENT + LEARNER MODEL
   └── Reassessment question targeting same gap
   └── Mastery formula application → learner model update → learning_events append
   └── Fail path: strategy change or prerequisite repair

7. API FLOW (FastAPI Endpoint Specification)
   └── Every endpoint: route, auth, input, business logic, DB ops, LLM call, output, errors

8. UX / SCREEN & INTERACTION SPECIFICATION (for Stitch)
   └── Login → Onboarding → Subject Upload → Concept Graph View
   └── Diagnostic → Diagnosis Reveal → Lesson → Visualization → Reassessment → Result → Learner Map

9. TECHNOLOGY LEARNING GUIDE
   └── FastAPI, MongoDB, Better Auth, Groq, MongoDB Vector Search, Framer Motion, SVG
   └── What it is, why we chose it, how it works, what we need to learn

10. IMPLEMENTATION PLAN
    └── Build order, vertical slices, milestones, risks
    └── THEN: CODE
```

---

## LLM Extraction Flow (Document 2)

This is the flow that must actually work in the MVP:

```
PDF / Notes (controlled CPU Pipelining material for demo)
      ↓
PyMuPDF / pypdf — text extraction (text-based PDFs only for MVP)
      ↓
Clean + structure text
      ↓
Chunking (size + overlap = open decision)
      ↓
Embedding model (provider = open decision)
      ↓
MongoDB Atlas Vector Search (chunks stored with embeddings)
      ↓
LLM (70B): Concept extraction
      ↓
[{ concept, description, difficulty, prerequisites: [] }]
      ↓
LLM (70B): Relationship extraction
      ↓
[{ from: concept_a, to: concept_b, type: "prerequisite" }]
      ↓
Pydantic validation of both outputs
      ↓
Concept Graph stored in MongoDB
      ↓
EduFusion is now ready to assess the student on this material
```

---

## Concept Graph Structure (Target Shape)

For CPU Pipelining, the extracted graph should produce something like:

```
Instruction Cycle
      ↓ (prerequisite)
Pipeline Stages (IF → ID → EX → MEM → WB)
      ↓ (prerequisite)
Pipeline Hazards
      ├── Data Hazard
      │     ↓
      │   Forwarding / Stalling
      ├── Control Hazard
      │     ↓
      │   Branch Prediction
      └── Structural Hazard

Dependency relationships:
  "Cannot understand Data Hazard without understanding Pipeline Stages"
  "Cannot understand Forwarding without understanding Data Hazard"
```

This structure comes from LLM extraction of the uploaded notes — not from hardcoding.

---

## MVP Scope (What The Demo Must Prove)

1. Upload CPU Pipelining notes → LLM builds concept graph
2. Five diagnostic questions (optimized for mental-model discovery)
3. Structured diagnosis with evidence ("Why we think this" visible in UI)
4. Targeted lesson (correct for the specific gap, not generic topic)
5. Mandatory visualization (one of: Pipeline, Hazard, Forwarding renderer)
6. Adaptive decision visible to student/judge
7. Reassessment targeting the same gap
8. Deterministic mastery update (e.g. 21% → 67%)
9. Failure → strategy change or prerequisite repair (demonstrable)
10. Learner state persisted in MongoDB

---

## What EduFusion Is NOT (Locked)

- Not a ChatGPT wrapper
- Not a PDF chatbot
- Not a quiz generator
- Not a course generator
- Not a hardcoded concept map with AI decoration
- Not a system where LLMs make authorization or mastery decisions
- Not dependent on copyrighted footage or invented historical events
- Not a fixed learning-style classifier
