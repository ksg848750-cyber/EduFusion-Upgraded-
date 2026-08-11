# EduFusion — Document 11: Database Schema & Data Models
*Technical Design Phase. Updated Schema Contracts for Diagnostic Probes.*

---

## Probe-Enabled Schemas

### 1. `diagnostic_sessions` Collection (Updated)
```json
{
  "_id": "ObjectId",
  "userId": "ObjectId (REQUIRED, Ref -> users)",
  "subjectId": "ObjectId (REQUIRED, Ref -> subjects)",
  "targetConceptIds": ["ObjectId (Ref -> concepts)"],
  "questionIds": ["ObjectId (Ref -> questions)"],
  "answerIds": ["ObjectId (Ref -> diagnostic_answers)"],
  "status": "Enum [CREATED, IN_PROGRESS, PROBE_REQUIRED, COMPLETED, ABANDONED] (REQUIRED)",
  "investigationState": {
    "isUnderInvestigation": "Boolean",
    "candidateHypotheses": [
      {
        "category": "Enum [MISSING_PREREQUISITE, MISCONCEPTION, etc.]",
        "targetConceptId": "ObjectId",
        "likelihood": "Float"
      }
    ],
    "probeQuestionIds": ["ObjectId (Ref -> questions)"],
    "probeAnswerIds": ["ObjectId (Ref -> diagnostic_answers)"]
  },
  "diagnosisId": "ObjectId (OPTIONAL, Ref -> diagnoses)",
  "startedAt": "Date (REQUIRED)",
  "completedAt": "Date (OPTIONAL)"
}
```

### 2. `diagnostic_questions` Collection (Updated)
```json
{
  "_id": "ObjectId",
  "subjectId": "ObjectId (REQUIRED, Ref -> subjects)",
  "conceptId": "ObjectId (REQUIRED, Ref -> concepts)",
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
  "parentQuestionId": "ObjectId (OPTIONAL, Ref -> diagnostic_questions)",
  "sourceChunkIds": ["ObjectId (Ref -> document_chunks)"],
  "createdAt": "Date (REQUIRED)"
}
```

### 3. `diagnoses` Collection (Updated)
```json
{
  "_id": "ObjectId",
  "userId": "ObjectId (REQUIRED, Ref -> users)",
  "subjectId": "ObjectId (REQUIRED, Ref -> subjects)",
  "sessionId": "ObjectId (REQUIRED, Ref -> diagnostic_sessions)",
  "conceptId": "ObjectId (REQUIRED, Ref -> concepts)",
  "rootCause": "Enum [MISSING_PREREQUISITE, CONCEPTUAL_MISUNDERSTANDING, PROCEDURAL_ERROR, REPRESENTATION_PROBLEM, TERMINOLOGY_CONFUSION, INSUFFICIENT_EVIDENCE] (REQUIRED)",
  "prerequisiteConceptId": "ObjectId (OPTIONAL, Ref -> concepts)",
  "confidence": "Float (0.0-1.0, REQUIRED)",
  "explanation": "String (REQUIRED)",
  "investigationHistory": {
    "initialFailureQuestionId": "ObjectId",
    "initialSignals": ["String"],
    "probeExecuted": "Boolean",
    "probeQuestionId": "ObjectId",
    "probeSignal": "String"
  },
  "evidence": [
    {
      "questionId": "ObjectId",
      "answerId": "ObjectId",
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
