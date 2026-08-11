# EduFusion — Document 3: Diagnostic Intelligence Architecture
*Technical Design Phase. Updated Architecture Specification.*

---

## ⚑ Governing Principle — Diagnostic Probes as Investigation Mechanisms

> **Rule 1: A wrong answer must NEVER automatically be classified as a misconception.**
> A wrong answer is initial, unconfirmed evidence. It can indicate:
> - Misunderstanding/misreading the question phrasing
> - Careless/procedural mistake or calculation slip
> - Forgotten terminology
> - Missing prerequisite knowledge
> - Genuine conceptual misconception
> - Application/reasoning gap
> - Poor wording or expression
> - Guessing / insufficient signal
>
> **Rule 2: Diagnostic Probes are an INVESTIGATION MECHANISM, not a quiz feature.**
> Normal Tutor: *"You got it wrong. Here is the explanation."*
> EduFusion: *"You got it wrong. I don't know why yet. Let me ask one targeted question designed specifically to find out whether it is A, B, or C."*
> EduFusion teaches the actual root cause, not the superficial symptom.

---

## The 2-Stage Diagnostic Investigation Loop

```
                       STUDENT ANSWER + REASONING
                                   │
                                   ▼
                        Initial Evidence Analysis
                                   │
                      Is evidence sufficient & unambiguous?
                                   │
                  ┌────────────────┴────────────────┐
                  ▼                                 ▼
             YES (Confidence ≥ 0.75)           NO (Ambiguous Signal)
                  │                                 │
                  │                        Identify Candidate Hypotheses
                  │                        (e.g., A: Missing Prereq vs
                  │                         B: Conceptual Misconception)
                  │                                 │
                  │                        Generate 1-2 Targeted Probe
                  │                        Questions to Differentiate A vs B
                  │                                 │
                  │                        Student Answers Probe
                  │                        (Response + Reasoning)
                  │                                 │
                  │                        Analyze Probe Evidence
                  │                                 │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                      Final Root-Cause Diagnosis
                                   │
                                   ▼
                     Intervention (Docs 4 & 5)
                                   │
                                   ▼
                       Reassessment (Doc 6)
                                   │
                                   ▼
                      Update Learner Model
```

---

## Candidate Hypothesis Differentiation Strategy (How LLM Chooses Probes)

When initial answer analysis yields an ambiguous signal (e.g. equal likelihood of `MISSING_PREREQUISITE` vs `MISCONCEPTION`), the backend instructs the LLM to generate a **Targeted Probe Question**:

1. **Formulate Hypotheses**:
   - *Hypothesis A*: Student lacks prerequisite knowledge of `Data Dependency`.
   - *Hypothesis B*: Student has a specific misconception that pipeline stages operate in complete isolation.
   - *Hypothesis C*: Student misread the stage timing in the question.

2. **Probe Question Design**:
   - The probe MUST isolate the boundary condition separating Hypothesis A and Hypothesis B.
   - *Example Probe*: *"Consider a single instruction executing alone in the pipeline. Does the EX stage communicate its output to any register file before the WB stage finishes?"*
   - If Student answers *"No communication happens until WB"*, Hypothesis B (isolation misconception) is confirmed.
   - If Student answers *"Communication happens, but I don't know when Instruction B reads it"*, Hypothesis A (prerequisite gap in timing) is confirmed.

---

## Data Model Updates for Probes & Evidence

### 1. `diagnostic_sessions` Collection (Updated)
```json
{
  "_id": "session_001",
  "userId": "usr_001",
  "subjectId": "subj_001",
  "status": "IN_PROGRESS",
  "questionIds": ["q_001", "q_002", "q_003"],
  "answerIds": ["ans_001", "ans_002", "ans_003"],
  "investigationState": {
    "isUnderInvestigation": true,
    "targetConceptId": "con_005",
    "candidateHypotheses": [
      {
        "category": "MISSING_PREREQUISITE",
        "targetConceptId": "con_004",
        "likelihood": 0.50
      },
      {
        "category": "MISCONCEPTION",
        "targetConceptId": "con_005",
        "likelihood": 0.50
      }
    ],
    "probeQuestionIds": ["q_probe_001"],
    "probeAnswerIds": ["ans_probe_001"]
  },
  "diagnosisId": null,
  "startedAt": "2026-08-11T21:00:00Z"
}
```

### 2. `questions` Collection (Updated for Probes)
```json
{
  "_id": "q_probe_001",
  "subjectId": "subj_001",
  "conceptIds": ["con_005"],
  "questionType": "PROBE",
  "difficulty": "EASY",
  "questionText": "Consider a single instruction executing alone in the pipeline. Does the EX stage communicate its output to the register file before WB finishes?",
  "expectedAnswer": "No — outputs write to pipeline registers first, not the main register file until WB.",
  "expectedReasoning": "Student distinguishes between register file writes and inter-stage pipeline register forwarding.",
  "diagnosticTargets": ["DISTINGUISH_STAGE_COMMUNICATION_VS_ISOLATION"],
  "differentiationTarget": {
    "hypothesisA": "MISSING_PREREQUISITE",
    "hypothesisB": "MISCONCEPTION"
  },
  "parentQuestionId": "q_002",
  "generatedByLLM": true,
  "createdAt": "2026-08-11T21:05:00Z"
}
```

### 3. `diagnoses` Collection (Updated Evidence Bundle)
```json
{
  "_id": "diag_001",
  "userId": "usr_001",
  "subjectId": "subj_001",
  "sessionId": "session_001",
  "conceptId": "con_005",
  "rootCause": "MISCONCEPTION",
  "confidence": 0.88,
  "explanation": "You appear to believe pipeline stages operate in complete isolation.",
  "investigationHistory": {
    "initialFailureQuestionId": "q_002",
    "initialSignals": ["INCORRECT_STAGE_TIMING"],
    "probeExecuted": true,
    "probeQuestionId": "q_probe_001",
    "probeSignal": "CONFIRMED_STAGE_ISOLATION_BELIEF"
  },
  "evidenceReferences": [
    { "questionId": "q_002", "answerId": "ans_002", "signal": "Initial incorrect timing assumption" },
    { "questionId": "q_probe_001", "answerId": "ans_probe_001", "signal": "Stated stages never share data before WB" }
  ],
  "recommendedAction": "CORRECT_MISCONCEPTION",
  "status": "ACTIVE",
  "createdAt": "2026-08-11T21:10:00Z"
}
```

---

## Updated API Endpoint Specifications

### 1. `POST /api/v1/diagnostics/{sessionId}/analyze`
Analyzes answers submitted so far.
- **If Evidence Conclusive ($\ge 0.75$)**: Returns `status: "DIAGNOSED"`, `diagnosisId: "diag_001"`.
- **If Signal Ambiguous ($< 0.75$)**: Returns `status: "PROBE_REQUIRED"`, `probeQuestion: { ... }`.

### 2. `POST /api/v1/diagnostics/{sessionId}/probe-answer`
Submits student response & reasoning for the probe question.
- **Request**:
  ```json
  {
    "probeQuestionId": "q_probe_001",
    "response": "No, stages never communicate before WB.",
    "reasoning": "Each stage is completely isolated until the end."
  }
  ```
- **Response**: Re-evaluates combined evidence (Initial + Probe) and returns final structured diagnosis:
  ```json
  {
    "status": "DIAGNOSED",
    "diagnosisId": "diag_001",
    "rootCause": "MISCONCEPTION",
    "confidence": 0.88,
    "evidenceSummary": "Initial answer suggested timing error; probe confirmed stage isolation misconception."
  }
  ```

---

## LLM vs Backend Division of Responsibilities

```
┌───────────────────────────────────────────┐
│               LLM LAYER                   │
│  - Analyzes student reasoning quality     │
│  - Identifies candidate error hypotheses  │
│  - Generates targeted probe questions to  │
│    differentiate Hypothesis A vs B        │
│  - Evaluates probe reasoning signals      │
└─────────────────────┬─────────────────────┘
                      │ Candidate Output
                      ▼
┌───────────────────────────────────────────┐
│             BACKEND ENGINE                │
│  - Enforces allowed root-cause enums      │
│  - Stores probe questions & responses in  │
│    `diagnostic_sessions`               │
│  - Checks Knowledge Graph prerequisites   │
│  - Combines initial + probe evidence      │
│  - Computes final confidence score        │
│  - Persists diagnosis to MongoDB          │
└───────────────────────────────────────────┘
```

---

*Document 3 updated & locked with mandatory Diagnostic Investigation Probes.*
