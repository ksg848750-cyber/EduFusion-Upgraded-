# EduFusion — Document 6: Reassessment & Learner Model Architecture
*Technical Design Phase. Complete & Finalized Document.*

---

## Governing Principle

> Completing a lesson is NOT proof of learning.
> EduFusion verifies actual understanding gain by issuing a **targeted reassessment** that provably tests the **same underlying diagnosis/gap** using novel surface wording and context.
> Reassessment outcomes deterministically update current learner state in `learner_models` while preserving immutable historical evidence in `learning_events`.

---

## The Closed-Loop Verification Pipeline

```
                     LESSON DELIVERED (Doc 4 & 5)
                                │
                                ▼
                   Targeted Reassessment Question
                   (Same Gap, Novel Context)
                                │
                                ▼
                        STUDENT RESPONSE
                                │
                                ▼
                       LLM Evidence Evaluation
                                │
             ┌──────────────────┼──────────────────┐
             ▼                  ▼                  ▼
          PASSED              FAILED          INCONCLUSIVE
             │                  │                  │
             ▼                  ▼                  ▼
     Mastery Increases   Strategy Change     Gather More Signal
    Misconception Resolves (Attempt 2 or 3)   (Targeted Probe)
             │                  │                  │
             └──────────────────┼──────────────────┘
                                │
                                ▼
                   Deterministic Mastery Engine
                                │
                                ▼
                 Persistent Learner Model Update
                   (`learner_models` Version++)
                                │
                                ▼
                   Immutable Activity Timeline
                   (`learning_events` Appended)
```

---

## Targeted Reassessment Specification

### 1. Link to Original Diagnosis
Every reassessment object maintains explicit provenance to the original diagnosis:

```json
{
  "_id": "reassess_001",
  "originalDiagnosisId": "diagnosis_001",
  "lessonId": "lesson_001",
  "targetConceptId": "concept_data_hazard",
  "targetGap": "Student believes pipeline stages operate independently without data sharing"
}
```

### 2. Novel Scenario Requirement (Anti-Memorization)
Reassessment questions NEVER reuse surface phrasing or numbers from the original diagnostic or lesson.

- **Original Diagnostic Q**: *"Instruction A writes R1 in WB. Instruction B needs R1 in EX. What happens?"*
- **Reassessment Q**: *"Instruction X writes to register R4 during the EX stage. Instruction Y immediately reads R4 in its ID stage. Explain whether the pipeline can continue normally without stalling or forwarding."*
- **Targeted Gap**: Tests data dependency awareness in pipeline registers under a new scenario.

---

## Reassessment Outcomes & Engine Rules

| Outcome | Trigger Condition | Engine Action |
|---|---|---|
| `PASSED` | Student response & reasoning demonstrate correct conceptual model on novel scenario. | Concept mastery increases; misconception status $\rightarrow$ `RESOLVED`; unlocks downstream graph concepts. |
| `FAILED` | Student repeats original mental-model error or demonstrates continuing gap. | Strategy profile logs failure; triggers Strategy Adaptation (Attempt 2/3) or steps back to prerequisite. |
| `INCONCLUSIVE` | Reasoning is vague, incomplete, or ambiguous. | Does not mutate mastery score; issues 1 targeted probe question to collect conclusive evidence. |

---

## Learner Model Architecture (`learner_models`)

The Learner Model represents EduFusion's **current state of belief** regarding a student.

```json
{
  "_id": "lm_001",
  "userId": "user_001",
  "subjectId": "subject_001",
  "overallMastery": 0.54,
  "conceptStates": [
    {
      "conceptId": "concept_instruction_cycle",
      "mastery": 0.92,
      "status": "MASTERED",
      "confidence": 0.95,
      "lastAssessedAt": "2026-08-10T00:10:00Z"
    },
    {
      "conceptId": "concept_data_hazard",
      "mastery": 0.67,
      "status": "DEVELOPING",
      "confidence": 0.84,
      "lastAssessedAt": "2026-08-10T00:43:00Z"
    },
    {
      "conceptId": "concept_forwarding",
      "mastery": 0.21,
      "status": "WEAK",
      "confidence": 0.78,
      "lastAssessedAt": "2026-08-10T00:35:00Z"
    }
  ],
  "activeMisconceptionIds": [],
  "prerequisiteGapIds": ["concept_forwarding"],
  "strategyProfile": {
    "effectiveStrategies": ["VISUAL_STEP_BY_STEP"],
    "ineffectiveStrategies": ["DIRECT_EXPLANATION"],
    "preferredInterest": "cricket",
    "history": [
      { "strategy": "DIRECT_EXPLANATION", "conceptId": "concept_data_hazard", "outcome": "FAILED" },
      { "strategy": "VISUAL_STEP_BY_STEP", "conceptId": "concept_data_hazard", "outcome": "PASSED" }
    ]
  },
  "version": 8,
  "updatedAt": "2026-08-10T00:43:05Z"
}
```

---

## Concept State Machine

```
               Initial Assessment
                       │
                       ▼
                    UNKNOWN
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
    Assessed & Weak      Assessed & Solid
             │                   │
             ▼                   ▼
           WEAK              DEVELOPING
             │                   │
       Intervention              │
             │                   │
             ▼                   │
       REASSESSMENT              │
             │                   │
      ┌──────┴──────┐            │
      ▼             ▼            │
   PASSED        FAILED          │
      │             │            │
      ▼             ▼            │
  DEVELOPING    STILL_WEAK ◄─────┘
      │
  Repeated Success
      │
      ▼
   MASTERED
```

- **`UNKNOWN`**: Never assessed.
- **`WEAK`**: Mastery $< 0.50$. Requires targeted intervention.
- **`DEVELOPING`**: Mastery $0.50 \le m < 0.85$. Intervention succeeded, needs reinforcement.
- **`MASTERED`**: Mastery $\ge 0.85$ backed by repeated correct reasoning across multiple sessions.
- **`STILL_WEAK`**: Intervention attempted but reassessment failed.

---

## Misconception Lifecycle

```
    Signal Identified in Diagnostic
                  │
                  ▼
              SUSPECTED (1 Signal)
                  │
        Confirmed by 2nd Signal
                  │
                  ▼
              CONFIRMED
                  │
           Intervention Issued
                  │
                  ▼
                ACTIVE
                  │
         ┌────────┴────────┐
         ▼                 ▼
  Reassessment PASS  Reassessment FAIL (3x)
         │                 │
         ▼                 ▼
     RESOLVED          PERSISTENT
```

---

## Deterministic Backend Mastery Model

EduFusion **never asks the LLM to invent a mastery percentage**. The backend calculates mastery updates deterministically using an evidence-weighted function:

$$\Delta M = \text{OutcomeWeight}(\text{Result}) \times \text{DifficultyModifier}(Q) \times \text{ReasoningQualityScore} \times \text{IndependenceFactor}$$

Where:
- **OutcomeWeight**: `PASSED` $= +0.35$, `FAILED` $= -0.20$, `INCONCLUSIVE` $= 0.00$.
- **DifficultyModifier**: Easy $= 0.8$, Medium $= 1.0$, Hard $= 1.25$.
- **ReasoningQualityScore**: LLM-evaluated quality of stated reasoning ($0.5$ to $1.0$).
- **IndependenceFactor**: Penalty scaling if questions are highly similar or within the same immediate session.

---

## Current State vs. Immutable History

```
┌─────────────────────────────────────────┐
│     CURRENT STATE (FAST READ ACCESS)     │
│  - learner_models                       │
│    (overallMastery, conceptStates[])    │
│  - misconceptions (active status)       │
└─────────────────────────────────────────┘
                    ▲
                    │ Updated on Reassessment Pass/Fail
                    │
┌─────────────────────────────────────────┐
│     IMMUTABLE HISTORICAL EVIDENCE       │
│  - answers (raw student responses)      │
│  - diagnoses (historical assessment)    │
│  - reassessments (provable loop items)  │
│  - learning_events (append-only log)    │
└─────────────────────────────────────────┘
```

---

## Closed-Loop Execution Trace (CPU Pipelining)

1. **Initial State**: `data_hazard` $= 0.21$ (`WEAK`), Misconception `misc_001` $= \text{ACTIVE}$.
2. **Intervention**: Lesson 1 delivered (`VISUAL_STEP_BY_STEP` + Cricket Analogy + Pipeline SVG).
3. **Reassessment Issued**: Question 8 presented (novel hazard scenario).
4. **Student Answers**: Correct response & reasoning explaining why forwarding is required.
5. **Evaluation**: LLM evaluates reasoning $\rightarrow$ `PASSED` (Confidence: 0.91).
6. **Backend Mastery Engine**:
   - `masteryBefore` $= 0.21$.
   - $\Delta M = +0.46$.
   - `masteryAfter` $= 0.67$.
7. **Database Updates**:
   - `learner_models.conceptStates["concept_data_hazard"]`: State $\rightarrow$ `DEVELOPING`, Mastery $\rightarrow$ 0.67.
   - `misconceptions["misc_001"]`: Status $\rightarrow$ `RESOLVED`.
   - `learning_events`: Appended `REASSESSMENT_COMPLETED` & `MASTERY_UPDATED`.
8. **Unlocking Next Node**: `forwarding` prerequisite gap cleared. System advances to `forwarding` diagnostic/lesson.

---

*Document 6 complete. Next: Document 7 — API Specification & Flow Architecture.*
