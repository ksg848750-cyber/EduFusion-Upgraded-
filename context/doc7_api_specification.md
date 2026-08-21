# EduFusion — Document 7: API Specification
*Updated: M7 reassessment endpoints added. 24 endpoints total.*

---

## Base URL
`http://127.0.0.1:8000/api/v1`

All endpoints require `Authorization: Bearer <supabase_jwt>` unless noted.

---

## Health
| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/health` | Health check + DB connectivity |

## Auth
| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/auth/me` | Get authenticated user profile (auto-creates on first call) |

## Subjects & Materials
| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/subjects` | Create a new subject |
| GET | `/subjects` | List all subjects |
| GET | `/subjects/{id}/materials` | List materials for a subject |
| GET | `/subjects/{id}/materials/{id}` | Get a single material |
| POST | `/subjects/{id}/materials` | Upload PDF + trigger ingestion pipeline |
| GET | `/subjects/{id}/knowledge-graph` | Get concepts + relationships |

## Learner Model
| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/subjects/{id}/learner` | Get learner model (overallMastery, conceptStates) |
| GET | `/subjects/{id}/concepts/{id}/learner` | Get per-concept learner state + misconceptions |
| POST | `/subjects/{id}/concepts/{id}/explain` | Generate grounded explanation |
| POST | `/subjects/{id}/concepts/{id}/test` | Start self-test (generates questions) |
| POST | `/subjects/{id}/sessions/{id}/answers` | Submit self-test answer |

## Diagnostic Flow
| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/subjects/{id}/diagnostic` | Start diagnostic session |
| POST | `/subjects/{id}/sessions/{id}/diagnostic-answers` | Submit diagnostic answer |
| GET | `/subjects/{id}/sessions/{id}/diagnostic-decision` | Run evidence analysis |
| POST | `/subjects/{id}/sessions/{id}/diagnostic-probe` | Generate targeted probe |
| POST | `/subjects/{id}/sessions/{id}/diagnosis` | Persist final diagnosis |
| GET | `/subjects/{id}/sessions/{id}/evidence-bundle` | "Why We Think This" bundle |

## Teaching Flow
| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/subjects/{id}/teaching-decision` | Compute WHAT + HOW to teach |
| POST | `/subjects/{id}/lessons/{id}/generate` | Generate grounded lesson + visualization |
| GET | `/subjects/{id}/lessons/{id}` | Retrieve a lesson |
| POST | `/subjects/{id}/lessons/{id}/clarify` | Answer a doubt from RAG |

## Reassessment Flow (M7)
| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/subjects/{id}/lessons/{id}/reassess` | Generate reassessment question |
| POST | `/subjects/{id}/reassessments/{id}/answer` | Submit answer + get outcome |
| GET | `/subjects/{id}/lessons/{id}/reassessment` | Get current reassessment |

---

## Response Contracts

### Teaching Decision Response
```json
{
  "status": "OK",
  "lessonId": "uuid",
  "sessionId": "uuid",
  "diagnosisId": "uuid",
  "conceptId": "uuid",
  "rootCause": "MISCONCEPTION",
  "action": "MENTAL_MODEL_CORRECTION",
  "teachingStrategy": "VISUAL_STEP_BY_STEP",
  "attempt": 1,
  "excluded": [],
  "interestContext": "normal"
}
```

### Lesson Content Response
```json
{
  "status": "OK",
  "lessonId": "uuid",
  "conceptId": "uuid",
  "rootCause": "MISCONCEPTION",
  "teachingAction": "MENTAL_MODEL_CORRECTION",
  "teachingStrategy": "VISUAL_STEP_BY_STEP",
  "attempt": 1,
  "interestContext": "cricket",
  "explanation": "...",
  "keyPoints": ["..."],
  "analogy": { "scene": "...", "mapping": [...], "analogy_works": "...", "analogy_breaks": "..." },
  "sourceChunks": [0, 3, 7],
  "sourceReferences": [{"chunkIndex": 0}],
  "visualizationSpec": {
    "type": "PROCESS_FLOW",
    "title": "...",
    "caption": "...",
    "process": { "stages": [...], "items": [...], "animation": { "steps": [...] } }
  }
}
```

### Reassessment Response
```json
{
  "status": "OK",
  "reassessmentId": "uuid",
  "lessonId": "uuid",
  "conceptId": "uuid",
  "questionType": "MCQ",
  "questionText": "...",
  "options": [{"id": "a", "text": "..."}, ...],
  "attempt": 1
}
```

### Reassessment Answer Response
```json
{
  "status": "OK",
  "reassessmentId": "uuid",
  "outcome": "PASSED",
  "correctness": true,
  "mastery": 0.65,
  "conceptStatus": "DEVELOPING",
  "attempt": 1
}
```
