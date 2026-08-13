# EduFusion — Document 11: Database Schema & Data Models
*Technical Design Phase. Updated Schema Contracts for Diagnostic Probes.*

---

## Probe-Enabled Schemas

### 1. `diagnostic_sessions` Table (Updated)
```json
{
  "id": "uuid (PRIMARY KEY)",
  "userId": "uuid (REQUIRED, FK -> users)",
  "subjectId": "uuid (REQUIRED, FK -> subjects)",
  "targetConceptIds": ["uuid (FK -> concepts)"],
  "questionIds": ["uuid (FK -> questions)"],
  "answerIds": ["uuid (FK -> diagnostic_answers)"],
  "status": "Enum [CREATED, IN_PROGRESS, PROBE_REQUIRED, COMPLETED, ABANDONED] (REQUIRED)",
  "investigationState": {
    "isUnderInvestigation": "Boolean",
    "candidateHypotheses": [
      {
        "category": "Enum [MISSING_PREREQUISITE, MISCONCEPTION, etc.]",
        "targetConceptId": "uuid",
        "likelihood": "Float"
      }
    ],
    "probeQuestionIds": ["uuid (FK -> questions)"],
    "probeAnswerIds": ["uuid (FK -> diagnostic_answers)"]
  },
  "diagnosisId": "uuid (OPTIONAL, FK -> diagnoses)",
  "startedAt": "Date (REQUIRED)",
  "completedAt": "Date (OPTIONAL)"
}
```

### 2. `diagnostic_questions` Table (Updated)
```json
{
  "id": "uuid (PRIMARY KEY)",
  "subjectId": "uuid (REQUIRED, FK -> subjects)",
  "conceptId": "uuid (REQUIRED, FK -> concepts)",
  "questionType": "Enum [SCENARIO, SHORT_ANSWER, MCQ, PROBE] (REQUIRED)",
  "difficulty": "Number (1-5)",
  "question": "String (REQUIRED)",
  "expectedAnswer": "String (REQUIRED)",
  "expectedReasoning": "String (REQUIRED)",
  "diagnosticTargets": ["String (REQUIRED)"],
  "differentiationTarget": {
    "hypothesisA": "String",
    "hypothesisB": "String"
  },
  "parentQuestionId": "uuid (OPTIONAL, FK -> diagnostic_questions)",
  "sourceChunkIds": ["uuid (FK -> document_chunks)"],
  "createdAt": "Date (REQUIRED)"
}
```

### 3. `diagnoses` Table (Updated)
```json
{
  "id": "uuid (PRIMARY KEY)",
  "userId": "uuid (REQUIRED, FK -> users)",
  "subjectId": "uuid (REQUIRED, FK -> subjects)",
  "sessionId": "uuid (REQUIRED, FK -> diagnostic_sessions)",
  "conceptId": "uuid (REQUIRED, FK -> concepts)",
  "rootCause": "Enum [MISSING_PREREQUISITE, CONCEPTUAL_MISUNDERSTANDING, PROCEDURAL_ERROR, REPRESENTATION_PROBLEM, TERMINOLOGY_CONFUSION, INSUFFICIENT_EVIDENCE] (REQUIRED)",
  "prerequisiteConceptId": "uuid (OPTIONAL, FK -> concepts)",
  "confidence": "Float (0.0-1.0, REQUIRED)",
  "explanation": "String (REQUIRED)",
  "investigationHistory": {
    "initialFailureQuestionId": "uuid",
    "initialSignals": ["String"],
    "probeExecuted": "Boolean",
    "probeQuestionId": "uuid",
    "probeSignal": "String"
  },
  "evidence": [
    {
      "questionId": "uuid",
      "answerId": "uuid",
      "reason": "String"
    }
  ],
  "recommendedAction": "Enum [REPAIR_PREREQUISITE, CORRECT_MISCONCEPTION, PRACTICE_PROCEDURE, CLARIFY_TERMINOLOGY, CHANGE_REPRESENTATION, REQUEST_MORE_EVIDENCE] (REQUIRED)",
  "status": "Enum [ACTIVE, RESOLVED] (REQUIRED)",
  "createdAt": "Date (REQUIRED)"
}
```

---

*Document 11 updated with Diagnostic Investigation Probe fields.*
