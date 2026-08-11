# EduFusion — Document 1: Data Architecture
*Technical Design Phase. Complete & Finalized Document.*

---

## Governing Principle

> MongoDB is EduFusion's long-term memory.
> We separate **Subject Knowledge** (what is true in the material) from **Learner Knowledge** (what THIS student understands).
> Every piece of intelligence the system produces is stored, retrievable, and explainable.

**State Model**: Current-State + Event-History
- `learner_models` = Current state of student understanding (embedded `conceptStates[]` for fast lookup)
- `learning_events` = Immutable, append-only history of every meaningful action

---

## Data Taxonomy: The 3 Data Worlds

```
                    EDUFUSION DATA
                         │
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
     KNOWLEDGE        LEARNER        ACTIVITY
       DATA             DATA           DATA
          │              │              │
          ├─ subjects    ├─ learner_    ├─ diagnostic_sessions
          ├─ materials      models      ├─ questions
          ├─ document_   └─ misconcep-  ├─ answers
          │  chunks         tions       ├─ diagnoses
          ├─ concepts                   ├─ lessons
          └─ concept_                   ├─ reassessments
             relationships              └─ learning_events
```

---

## Global Database Rules

1. **IDs**: Use native `ObjectId` for `_id` and all foreign key references (`userId`, `subjectId`, `conceptId`, etc.).
2. **Timestamps**: All persistent entities get `createdAt` and `updatedAt` in UTC ISO 8601. Immutable event records use `timestamp` or `createdAt`.
3. **Identity Boundary**: `authUserId` (from Better Auth) is verified on every request by FastAPI. Frontends cannot supply arbitrary user IDs.
4. **Current vs History**: `learner_models.conceptStates` holds current mastery for fast reads; historical evidence lives in `answers`, `diagnoses`, `reassessments`, and `learning_events`.

---

## Detailed Collection Specifications

### 1. `users`
App-level profile linked to Better Auth identity.
```json
{
  "_id": "ObjectId",
  "authUserId": "String (REQUIRED, UNIQUE)",
  "name": "String (REQUIRED)",
  "email": "String (REQUIRED, UNIQUE)",
  "interests": ["String"],
  "preferences": {
    "language": "en",
    "educationLevel": "undergraduate",
    "studyClass": "btech-3"
  },
  "isOnboarded": "Boolean (REQUIRED)",
  "createdAt": "Date (REQUIRED)",
  "updatedAt": "Date (REQUIRED)"
}
```
**Indexes**: `authUserId` (UNIQUE), `email` (UNIQUE)

---

### 2. `subjects`
Learning subjects/courses owned by a user.
```json
{
  "_id": "ObjectId",
  "ownerId": "ObjectId (REQUIRED, Ref -> users)",
  "name": "String (REQUIRED)",
  "description": "String (OPTIONAL)",
  "status": "Enum [ACTIVE, ARCHIVED] (REQUIRED)",
  "conceptCount": "Number (OPTIONAL)",
  "createdAt": "Date (REQUIRED)",
  "updatedAt": "Date (REQUIRED)"
}
```
**Indexes**: `ownerId`

---

### 3. `materials`
Source documents uploaded for a subject.
```json
{
  "_id": "ObjectId",
  "subjectId": "ObjectId (REQUIRED, Ref -> subjects)",
  "ownerId": "ObjectId (REQUIRED, Ref -> users)",
  "filename": "String (REQUIRED)",
  "fileType": "Enum [PDF, DOCX, PPTX, TXT, IMAGE] (REQUIRED)",
  "storageReference": "String (REQUIRED)",
  "processingStatus": "Enum [UPLOADED, PROCESSING, COMPLETED, FAILED] (REQUIRED)",
  "pageCount": "Number (OPTIONAL)",
  "processingError": "String (OPTIONAL)",
  "createdAt": "Date (REQUIRED)",
  "updatedAt": "Date (REQUIRED)"
}
```
**Indexes**: `subjectId`, `ownerId`, `processingStatus`

---

### 4. `document_chunks`
Primary RAG retrieval units with vector embeddings.
```json
{
  "_id": "ObjectId",
  "materialId": "ObjectId (REQUIRED, Ref -> materials)",
  "subjectId": "ObjectId (REQUIRED, Ref -> subjects)",
  "chunkIndex": "Number (REQUIRED)",
  "text": "String (REQUIRED)",
  "pageNumber": "Number (OPTIONAL)",
  "sectionTitle": "String (OPTIONAL)",
  "embedding": "Array[Float] (REQUIRED - Dim TBD in Doc 2)",
  "metadata": {
    "headingPath": ["Computer Architecture", "Pipelining", "Hazards"]
  },
  "createdAt": "Date (REQUIRED)"
}
```
**Indexes**: Vector Index on `embedding`, `(materialId, chunkIndex)`, `subjectId`

---

### 5. `concepts`
Nodes of the Knowledge Graph extracted from materials.
```json
{
  "_id": "ObjectId",
  "subjectId": "ObjectId (REQUIRED, Ref -> subjects)",
  "name": "String (REQUIRED)",
  "canonicalName": "String (REQUIRED - e.g., 'data_hazard')",
  "description": "String (REQUIRED)",
  "difficulty": "Number (1-5)",
  "sourceReferences": [
    {
      "materialId": "ObjectId",
      "chunkId": "ObjectId",
      "pageNumber": 14
    }
  ],
  "extractionMetadata": {
    "model": "String",
    "promptVersion": "String",
    "confidence": 0.94
  },
  "embedding": "Array[Float] (OPTIONAL)",
  "createdAt": "Date (REQUIRED)",
  "updatedAt": "Date (REQUIRED)"
}
```
**Indexes**: `(subjectId, canonicalName)` (UNIQUE), `subjectId`, Text index on `name`

---

### 6. `concept_relationships`
Directed edges of the Knowledge Graph.
```json
{
  "_id": "ObjectId",
  "subjectId": "ObjectId (REQUIRED, Ref -> subjects)",
  "fromConceptId": "ObjectId (REQUIRED, Ref -> concepts)",
  "toConceptId": "ObjectId (REQUIRED, Ref -> concepts)",
  "relationshipType": "Enum [PREREQUISITE, DEPENDS_ON, PART_OF, RELATED_TO, CONTRASTS_WITH] (REQUIRED)",
  "confidence": "Float (0.0-1.0, REQUIRED)",
  "sourceReferences": [
    {
      "materialId": "ObjectId",
      "chunkId": "ObjectId",
      "pageNumber": 14
    }
  ],
  "extractionMetadata": {
    "model": "String",
    "promptVersion": "String"
  },
  "createdAt": "Date (REQUIRED)",
  "updatedAt": "Date (REQUIRED)"
}
```
**Validation**: Graph validator prevents self-loops (`A -> A`) and cycles in `PREREQUISITE` edges.
**Indexes**: `(subjectId, fromConceptId, toConceptId)`, `subjectId`

---

### 7. `learner_models`
Central intelligence state for a student on a subject.
```json
{
  "_id": "ObjectId",
  "userId": "ObjectId (REQUIRED, Ref -> users)",
  "subjectId": "ObjectId (REQUIRED, Ref -> subjects)",
  "conceptStates": [
    {
      "conceptId": "ObjectId",
      "mastery": 0.34,
      "status": "Enum [UNKNOWN, WEAK, DEVELOPING, MASTERED]",
      "confidence": 0.81,
      "assessmentCount": 3,
      "lastAssessedAt": "Date"
    }
  ],
  "activeMisconceptionIds": ["ObjectId (Ref -> misconceptions)"],
  "prerequisiteGaps": [
    {
      "conceptId": "ObjectId",
      "missingPrereqId": "ObjectId"
    }
  ],
  "strategyProfile": {
    "effectiveStrategies": ["VISUAL_STEP_BY_STEP"],
    "ineffectiveStrategies": ["DIRECT_EXPLANATION"],
    "preferredInterest": "cricket",
    "history": []
  },
  "overallMastery": "Float (0.0-1.0)",
  "version": "Number (Optimistic Concurrency)",
  "createdAt": "Date (REQUIRED)",
  "updatedAt": "Date (REQUIRED)"
}
```
**Indexes**: `(userId, subjectId)` (UNIQUE)

---

### 8. `misconceptions`
Persistent mental-model distortions identified for a learner.
```json
{
  "_id": "ObjectId",
  "learnerId": "ObjectId (REQUIRED, Ref -> users)",
  "subjectId": "ObjectId (REQUIRED, Ref -> subjects)",
  "conceptId": "ObjectId (REQUIRED, Ref -> concepts)",
  "category": "Enum [MISSING_PREREQUISITE, MISCONCEPTION, PROCEDURAL_ERROR, TERMINOLOGY_CONFUSION, REPRESENTATION_PROBLEM, INSUFFICIENT_EVIDENCE] (REQUIRED)",
  "statement": "String (REQUIRED)",
  "confidence": "Float (0.0-1.0, REQUIRED)",
  "evidenceReferences": [
    {
      "questionId": "ObjectId",
      "answerId": "ObjectId",
      "signal": "student_treats_pipeline_stages_as_independent"
    }
  ],
  "status": "Enum [SUSPECTED, CONFIRMED, ACTIVE, RESOLVED, PERSISTENT] (REQUIRED)",
  "firstDetectedAt": "Date (REQUIRED)",
  "lastConfirmedAt": "Date (REQUIRED)",
  "resolvedAt": "Date (OPTIONAL)",
  "updatedAt": "Date (REQUIRED)"
}
```
**Indexes**: `(learnerId, subjectId, status)`, `(learnerId, conceptId)`

---

### 9. `diagnostic_sessions`
Assessment session orchestrating diagnostic questions.
```json
{
  "_id": "ObjectId",
  "learnerId": "ObjectId (REQUIRED, Ref -> users)",
  "subjectId": "ObjectId (REQUIRED, Ref -> subjects)",
  "conceptScope": ["ObjectId (Ref -> concepts)"],
  "questionIds": ["ObjectId (Ref -> questions)"],
  "status": "Enum [CREATED, IN_PROGRESS, COMPLETED, ABANDONED] (REQUIRED)",
  "startedAt": "Date (REQUIRED)",
  "completedAt": "Date (OPTIONAL)"
}
```
**Indexes**: `(learnerId, subjectId)`

---

### 10. `questions`
Questions created specifically for diagnostic mental-model discovery or reassessment.
```json
{
  "_id": "ObjectId",
  "subjectId": "ObjectId (REQUIRED, Ref -> subjects)",
  "conceptIds": ["ObjectId (Ref -> concepts)"],
  "questionType": "Enum [MCQ, SHORT_ANSWER, SCENARIO, DIAGNOSTIC, REASSESSMENT, PROBE] (REQUIRED)",
  "difficulty": "Number (1-5)",
  "questionText": "String (REQUIRED)",
  "expectedAnswer": "String (REQUIRED)",
  "expectedReasoning": "String (REQUIRED)",
  "diagnosticTargets": ["String (REQUIRED - e.g. 'UNDERSTANDS_DATA_DEPENDENCY')"],
  "sourceReferences": [
    { "materialId": "ObjectId", "chunkId": "ObjectId" }
  ],
  "generationMetadata": "Object",
  "createdAt": "Date (REQUIRED)"
}
```
**Indexes**: `(subjectId, questionType)`, `(subjectId, conceptIds)`

---

### 11. `answers`
Student responses containing reasoning for diagnostic analysis.
```json
{
  "_id": "ObjectId",
  "questionId": "ObjectId (REQUIRED, Ref -> questions)",
  "learnerId": "ObjectId (REQUIRED, Ref -> users)",
  "diagnosticSessionId": "ObjectId (OPTIONAL, Ref -> diagnostic_sessions)",
  "reassessmentId": "ObjectId (OPTIONAL, Ref -> reassessments)",
  "response": "String (REQUIRED)",
  "reasoning": "String (OPTIONAL)",
  "correctness": "Boolean (REQUIRED)",
  "reasoningAssessment": {
    "identifiedConceptError": true,
    "errorDescription": "String",
    "diagnosticValue": "HIGH"
  },
  "evidenceSignals": ["String"],
  "createdAt": "Date (REQUIRED)"
}
```
**Indexes**: `(learnerId, questionId)`, `(diagnosticSessionId, questionId)`

---

### 12. `diagnoses`
Results of diagnostic reasoning over a session's evidence.
```json
{
  "_id": "ObjectId",
  "learnerId": "ObjectId (REQUIRED, Ref -> users)",
  "subjectId": "ObjectId (REQUIRED, Ref -> subjects)",
  "sessionId": "ObjectId (REQUIRED, Ref -> diagnostic_sessions)",
  "conceptId": "ObjectId (REQUIRED, Ref -> concepts)",
  "rootCause": "Enum [MISSING_PREREQUISITE, MISCONCEPTION, PROCEDURAL_ERROR, TERMINOLOGY_CONFUSION, REPRESENTATION_PROBLEM, INSUFFICIENT_EVIDENCE] (REQUIRED)",
  "confidence": "Float (0.0-1.0, REQUIRED)",
  "explanation": "String (REQUIRED)",
  "evidenceReferences": [
    {
      "questionId": "ObjectId",
      "answerId": "ObjectId",
      "signal": "String"
    }
  ],
  "prerequisiteConceptId": "ObjectId (OPTIONAL, Ref -> concepts)",
  "recommendedAction": "Enum [REPAIR_PREREQUISITE, CORRECT_MISCONCEPTION, PRACTICE_PROCEDURE, CLARIFY_TERMINOLOGY, CHANGE_REPRESENTATION, REQUEST_MORE_EVIDENCE] (REQUIRED)",
  "modelMetadata": "Object",
  "createdAt": "Date (REQUIRED)"
}
```
**Indexes**: `(learnerId, subjectId)`, `(learnerId, conceptId)`

---

### 13. `lessons`
Instructional content & structured visualization specifications delivered to the learner.
```json
{
  "_id": "ObjectId",
  "learnerId": "ObjectId (REQUIRED, Ref -> users)",
  "subjectId": "ObjectId (REQUIRED, Ref -> subjects)",
  "diagnosisId": "ObjectId (REQUIRED, Ref -> diagnoses)",
  "targetConceptId": "ObjectId (REQUIRED, Ref -> concepts)",
  "strategy": "Enum [DIRECT_EXPLANATION, STEP_BY_STEP, WORKED_EXAMPLE, VISUAL_EXPLANATION, INTEREST_CONTEXT, INTERACTIVE_EXPLANATION, PREREQUISITE_REPAIR] (REQUIRED)",
  "explanation": "String (REQUIRED)",
  "interestContext": {
    "domain": "cricket",
    "analogy": "String"
  },
  "visualizationSpec": {
    "type": "PIPELINE",
    "version": "1.0",
    "data": {},
    "highlights": ["DATA_DEPENDENCY"],
    "animation": { "steps": [] }
  },
  "sourceReferences": [
    { "materialId": "ObjectId", "chunkId": "ObjectId" }
  ],
  "status": "Enum [GENERATED, DELIVERED, COMPLETED] (REQUIRED)",
  "createdAt": "Date (REQUIRED)"
}
```
**Indexes**: `(learnerId, diagnosisId)`

---

### 14. `reassessments`
Targeted evaluation verifying whether an intervention corrected the diagnosed gap.
```json
{
  "_id": "ObjectId",
  "learnerId": "ObjectId (REQUIRED, Ref -> users)",
  "originalDiagnosisId": "ObjectId (REQUIRED, Ref -> diagnoses)",
  "targetConceptId": "ObjectId (REQUIRED, Ref -> concepts)",
  "targetGap": {
    "description": "String",
    "category": "String"
  },
  "questionId": "ObjectId (REQUIRED, Ref -> questions)",
  "answerId": "ObjectId (REQUIRED, Ref -> answers)",
  "result": "Enum [PASSED, FAILED, INCONCLUSIVE] (REQUIRED)",
  "masteryBefore": "Float (REQUIRED)",
  "masteryAfter": "Float (REQUIRED)",
  "createdAt": "Date (REQUIRED)"
}
```
**Indexes**: `(learnerId, originalDiagnosisId)`

---

### 15. `learning_events`
Immutable historical timeline recording every event in the system.
```json
{
  "_id": "ObjectId",
  "learnerId": "ObjectId (REQUIRED, Ref -> users)",
  "subjectId": "ObjectId (OPTIONAL, Ref -> subjects)",
  "eventType": "Enum [MATERIAL_UPLOADED, MATERIAL_PROCESSED, DIAGNOSTIC_STARTED, QUESTION_ANSWERED, DIAGNOSIS_CREATED, MISCONCEPTION_DETECTED, MISCONCEPTION_RESOLVED, LESSON_STARTED, LESSON_COMPLETED, VISUALIZATION_VIEWED, REASSESSMENT_STARTED, REASSESSMENT_COMPLETED, MASTERY_UPDATED] (REQUIRED)",
  "entityType": "String",
  "entityId": "ObjectId",
  "metadata": "Object",
  "timestamp": "Date (REQUIRED)"
}
```
**Indexes**: `(learnerId, timestamp)`, `(learnerId, subjectId, timestamp)`

---

## Master Architecture Map

```
                         USER
                          │
         ┌────────────────┴────────────────┐
         ↓                                 ↓
      SUBJECT                        LEARNER MODEL
         │                                 │
         ↓                                 │
      MATERIAL                             │
         │                                 │
         ↓                                 │
  DOCUMENT CHUNKS                          │
         │                                 │
         └─────────┐                       │
                   ↓                       │
                CONCEPTS ◄─────────────────┘
                   │
                   ↓
         CONCEPT RELATIONSHIPS
                   │
                   ↓
              DIAGNOSTICS
                   ↑
                   │
                ANSWERS
                   ↑
                   │
               QUESTIONS
                   │
                   ↓
               DIAGNOSIS
                   │
                   ├───────────────→ MISCONCEPTION
                   │
                   ↓
                 LESSON
                   │
                   ↓
             VISUALIZATION
                   │
                   ↓
              REASSESSMENT
                   │
                   └───────────────→ LEARNER MODEL UPDATE
                                           │
                                           ↓
                                    LEARNING EVENTS
```

---

## Data Architecture Complete

Document 1 is locked. All field structures, relationship boundaries, enums, index strategies, and lifecycle steps are established.

**Next Document**: `Document 2 — LLM Knowledge Extraction` (PDF → extraction → cleaning → chunking → embeddings → LLM concept extraction → relationship extraction → prerequisite detection → validation → knowledge graph → MongoDB).
