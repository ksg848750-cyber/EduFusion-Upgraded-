# EduFusion — Document 4: Adaptive Teaching Engine Architecture
*Technical Design Phase. Complete & Finalized Document.*

---

## Governing Principle

> The diagnosis controls the lesson.
> EduFusion does not generate generic re-explanations. Instead, it executes two distinct decisions: **WHAT to teach** (targeting the root cause/prerequisite) and **HOW to teach** (selecting a strategy and context based on the learner's evidence history).
> Every intervention combines a grounded explanation with a mandatory, declarative visualization specification.

---

## Adaptive Teaching Pipeline

```
                        DIAGNOSIS (Document 3 Output)
                                    │
                                    ▼
                      ┌───────────────────────────┐
                      │  ADAPTIVE TEACHING ENGINE │
                      └─────────────┬─────────────┘
                                    │
             ┌──────────────────────┴──────────────────────┐
             ▼                                             ▼
    DECISION A: WHAT TO TEACH                    DECISION B: HOW TO TEACH
    (Root-Cause Action Mapping)                  (Strategy & Context Selection)
             │                                             │
             ├─ MISSING_PREREQUISITE ──► Repair Prereq     ├─ Strategy Profile Check
             ├─ MISCONCEPTION ───────► Counterexample      ├─ Context Preference (Interest)
             ├─ PROCEDURAL_ERROR ────► Guided Practice     └─ Historical Outcome Check
             ├─ TERMINOLOGY_CONFUSION ► Contrast Terms
             ├─ REPRESENTATION_PROB ─► Change Visual
             └─ INSUFFICIENT_EVID ───► Probe
             │                                             │
             └──────────────────────┬──────────────────────┘
                                    │
                                    ▼
                      Grounded RAG Retrieval (Vector Search)
                                    │
                                    ▼
                           LLM Lesson Generation
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                                               ▼
   Grounded Explanation                             Declarative Visual Spec
   (Optional Interest Analogy)                    (Pipeline / Hazard / etc.)
            │                                               │
            └───────────────────────┬───────────────────────┘
                                    │
                                    ▼
                         Lesson Delivery + Renderer
                                    │
                                    ▼
                           REASSESSMENT (Doc 6)
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                                               ▼
         PASSED                                          FAILED
            │                                               │
   Update Learner Model                            Adapt Strategy (Attempt++)
   (Mastery Increases)                             (Max 3 Attempts Limit)
```

---

## Decision A: WHAT to Teach (Root-Cause Action Mapping)

The 6 root-cause categories from Document 3 map deterministically to teaching actions:

| Diagnosis Root Cause | Adaptive Engine Action | Pedagogical Strategy |
|---|---|---|
| `MISSING_PREREQUISITE` | **Prerequisite Repair** | Step backward in Knowledge Graph to teach the missing prerequisite node before retrying the target concept. |
| `MISCONCEPTION` | **Mental-Model Correction** | Present a direct counterexample that highlights the flaw in the student's reasoning, then replace it with the correct model. |
| `PROCEDURAL_ERROR` | **Guided Application Practice** | Skip definition overviews. Provide step-by-step worked examples showing proper application. |
| `TERMINOLOGY_CONFUSION` | **Distinction & Contrast** | Present side-by-side comparative matrices contrasting the confused terms. |
| `REPRESENTATION_PROBLEM` | **Representation Shift** | Change the primary modal medium (e.g. text $\rightarrow$ step-by-step interactive diagram). |
| `INSUFFICIENT_EVIDENCE` | **Targeted Probing** | Issue a targeted probe question to collect diagnostic signal. |

---

## Decision B: HOW to Teach (Strategy & Context Selection)

### 1. Strategy Library (`teachingStrategy`)
- `DIRECT_EXPLANATION`: Concise, first-principles technical breakdown.
- `VISUAL_STEP_BY_STEP`: Micro-step decomposition paired with synchronized visual state changes.
- `WORKED_EXAMPLE`: Problem-solving walkthrough with explicit reasoning steps.
- `INTEREST_CONTEXT`: Contextual analogy bridging real-world interest to technical mechanics.
- `INTERACTIVE_EXPLANATION`: Step-by-step user-driven exploration.
- `PREREQUISITE_REPAIR`: Focused mini-lesson repairing a foundational node.

### 2. Strategy Selection Algorithm
The engine inspects `learner_models.strategyProfile`:
1. **Exclude Ineffective**: Remove strategies previously logged as `NO_CHANGE` or `REGRESSED` for this concept.
2. **Prioritize Proven**: Select strategies logged as `IMPROVED` in similar contexts.
3. **Attempt Escalation**:
   - **Attempt 1**: `VISUAL_STEP_BY_STEP` + (Optional `INTEREST_CONTEXT`).
   - **Attempt 2 (on failure)**: `WORKED_EXAMPLE` + `REPRESENTATION_CHANGE`.
   - **Attempt 3 (on second failure)**: Step back to `PREREQUISITE_REPAIR` or flag for human assistance.

---

## The Mandatory Visualization Requirement

### Core Rule:
**Every explanation delivered by EduFusion MUST include a concept-accurate visualization.**

```
                     TEACHING DECISION
                            │
               ┌────────────┴────────────┐
               ▼                         ▼
      CONTEXTUAL ANALOGY         TECHNICAL MECHANIC
      (e.g., Cricket / Gaming)   (e.g., Data Hazard)
               │                         │
               ▼                         ▼
      Explanation Text          Mandatory Visual Spec
      (Analogy Bridge)          (Concept-Accurate Renderer)
```

- **Interest Analogy**: Alters the text/narrative context (e.g. cricket batting partnership).
- **Visualization Spec**: Shows the exact, technically accurate mechanics of the diagnosed concept from the learner's material (for the CPU validation/demo domain: instruction stages, hazards, and forwarding).
- **Constraint**: The visual renderer NEVER renders fake domain images (e.g., no animated cricket bats); it renders the actual subject concept accurately (for CPU: the computer architecture diagram).

---

## Grounded Lesson Generation via RAG

To ensure accuracy and prevent LLM hallucination:
1. Target concept ID $\rightarrow$ Query `document_chunks` via Vector Search.
2. Top-k relevant chunks retrieved (`sourceReferences`).
3. LLM prompt constructed with:
   - Target Concept & Root Cause
   - Selected Strategy & Interest Context
   - Retrieved Source Chunks (Grounding Text)
   - Mandatory Pydantic Visualization Spec Schema

---

## Structured Output Contracts (LLM Hand-off)

The LLM does NOT write React/JSX code. It outputs a validated Pydantic JSON structure:

```json
{
  "targetConceptId": "concept_data_hazard",
  "diagnosisId": "diagnosis_001",
  "teachingStrategy": "VISUAL_STEP_BY_STEP",
  "interestContextUsed": "cricket",
  "explanation": "Before we look at forwarding, let's understand why Instruction B must wait for Instruction A. Think of a batting partnership where the non-striker cannot start running until the striker hits the ball...",
  "visualizationSpec": {
    "type": "PIPELINE",
    "version": "1.0",
    "title": "Data Hazard: Instruction Dependency",
    "highlight": "DATA_DEPENDENCY",
    "data": {
      "instructions": [
        { "id": "I1", "text": "ADD R1, R2, R3", "color": "#4CAF50" },
        { "id": "I2", "text": "SUB R4, R1, R5", "dependsOn": "I1", "color": "#F44336" }
      ]
    },
    "animation": {
      "steps": [
        { "step": 1, "description": "I1 enters EX stage, computing R1.", "activeStages": { "I1": "EX", "I2": "ID" } },
        { "step": 2, "description": "I2 needs R1 in ID, but R1 is not written back until WB.", "activeStages": { "I1": "MEM", "I2": "STALL" }, "hazardAlert": true }
      ]
    }
  },
  "sourceReferences": [
    { "materialId": "material_001", "chunkId": "chunk_037" }
  ]
}
```

---

## Bounded Adaptation & Loop Control

To prevent infinite "Teach $\rightarrow$ Fail $\rightarrow$ Teach $\rightarrow$ Fail" loops:

```
Intervention Attempt 1
  │
  ├─► Reassessment PASS ──► Mastery Updated (Doc 6) ──► Move to Next Concept
  │
  └─► Reassessment FAIL
        │
        ▼
Attempt 2 (Change Strategy e.g. VISUAL ──► WORKED_EXAMPLE)
  │
  ├─► Reassessment PASS ──► Update Learner Profile ──► Move to Next Concept
  │
  └─► Reassessment FAIL
        │
        ▼
Attempt 3 (Step Back to Foundational Prerequisite in Graph)
  │
  └─► Reassessment FAIL ──► Lock Node as PERSISTENT & Notify User/Mentor
```

- **Max Intervention Limit**: 3 attempts per concept before prerequisite rollback or escalating to `PERSISTENT` state.

---

## The 7 Levels of Adaptation Summary

1. **Concept Adaptation**: Different learners assess different graph nodes.
2. **Diagnosis Adaptation**: Interventions target specific root causes (6 categories).
3. **Strategy Adaptation**: Teaching style alters (`VISUAL`, `WORKED_EXAMPLE`, `DIRECT`).
4. **Context Adaptation**: Interest lens alters narrative (`cricket`, `gaming`, `normal`).
5. **Representation Adaptation**: Visual renderers shift representation modes.
6. **History Adaptation**: Learner model remembers strategy outcomes.
7. **Verification Adaptation**: Reassessment validates actual understanding gain before advancing.

---

*Document 4 complete. Next: Document 5 — Visualization Engine Architecture.*
