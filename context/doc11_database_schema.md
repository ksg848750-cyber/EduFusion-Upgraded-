# EduFusion — Document 11: Database Schema & Data Models
*Updated: M7 Reassessment tables added. 15 tables total.*

---

## Complete Schema (15 tables)

### 1. `users`
```sql
id              uuid PRIMARY KEY DEFAULT gen_random_uuid()
auth_user_id    uuid NOT NULL UNIQUE  -- Supabase Auth ID
display_name    text NOT NULL DEFAULT ''
created_at      timestamptz NOT NULL DEFAULT now()
```

### 2. `subjects`
```sql
id              uuid PRIMARY KEY DEFAULT gen_random_uuid()
owner_id        uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE
name            text NOT NULL
description     text NOT NULL DEFAULT ''
concept_count   integer NOT NULL DEFAULT 0
created_at      timestamptz NOT NULL DEFAULT now()
updated_at      timestamptz NOT NULL DEFAULT now()
```

### 3. `materials`
```sql
id              uuid PRIMARY KEY DEFAULT gen_random_uuid()
subject_id      uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE
owner_id        uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE
filename        text NOT NULL
storage_ref     text NOT NULL DEFAULT ''
status          text NOT NULL DEFAULT 'UPLOADED'
                CHECK (status IN ('UPLOADED','PROCESSING','READY','FAILED'))
chunk_count     integer NOT NULL DEFAULT 0
created_at      timestamptz NOT NULL DEFAULT now()
updated_at      timestamptz NOT NULL DEFAULT now()
```

### 4. `document_chunks`
```sql
id              uuid PRIMARY KEY DEFAULT gen_random_uuid()
subject_id      uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE
material_id     uuid NOT NULL REFERENCES materials(id) ON DELETE CASCADE
chunk_index     integer NOT NULL
content         text NOT NULL
embedding       vector(768)
source_page     integer
created_at      timestamptz NOT NULL DEFAULT now()
```

### 5. `concepts`
```sql
id                      uuid PRIMARY KEY DEFAULT gen_random_uuid()
subject_id              uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE
name                    text NOT NULL
canonical_name          text NOT NULL
description             text NOT NULL DEFAULT ''
difficulty              integer NOT NULL DEFAULT 3 CHECK (difficulty BETWEEN 1 AND 5)
expected_understanding  text NOT NULL DEFAULT ''
common_misconceptions   jsonb NOT NULL DEFAULT '[]'::jsonb
source_references       jsonb NOT NULL DEFAULT '[]'::jsonb
created_at              timestamptz NOT NULL DEFAULT now()
```

### 6. `concept_relationships`
```sql
id              uuid PRIMARY KEY DEFAULT gen_random_uuid()
subject_id      uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE
source_id       uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE
target_id       uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE
relationship    text NOT NULL DEFAULT 'PREREQUISITE_OF'
weight          double precision NOT NULL DEFAULT 1.0
created_at      timestamptz NOT NULL DEFAULT now()
```

### 7. `learner_models`
```sql
id              uuid PRIMARY KEY DEFAULT gen_random_uuid()
user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE
subject_id      uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE
overall_mastery double precision NOT NULL DEFAULT 0.0
concept_states  jsonb NOT NULL DEFAULT '{}'::jsonb
strategy_profile jsonb NOT NULL DEFAULT '{}'::jsonb  -- {concept_id: {strategy: outcome}}
version         integer NOT NULL DEFAULT 1
created_at      timestamptz NOT NULL DEFAULT now()
updated_at      timestamptz NOT NULL DEFAULT now()
UNIQUE (user_id, subject_id)
```

### 8. `misconceptions`
```sql
id                  uuid PRIMARY KEY DEFAULT gen_random_uuid()
learner_id          uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE
subject_id          uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE
concept_id          uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE
category            text NOT NULL
                    CHECK (category IN (
                        'MISSING_PREREQUISITE','MISCONCEPTION','PROCEDURAL_ERROR',
                        'TERMINOLOGY_CONFUSION','REPRESENTATION_PROBLEM',
                        'INSUFFICIENT_EVIDENCE'))
statement           text NOT NULL
confidence          double precision NOT NULL DEFAULT 0.5
evidence_references jsonb NOT NULL DEFAULT '[]'::jsonb
status              text NOT NULL DEFAULT 'SUSPECTED'
                    CHECK (status IN ('SUSPECTED','CONFIRMED','ACTIVE','RESOLVED','PERSISTENT'))
first_detected_at   timestamptz NOT NULL DEFAULT now()
last_confirmed_at   timestamptz
resolved_at         timestamptz
created_at          timestamptz NOT NULL DEFAULT now()
updated_at          timestamptz NOT NULL DEFAULT now()
UNIQUE (learner_id, subject_id, concept_id, category, statement)
```

### 9. `diagnostic_sessions`
```sql
id          uuid PRIMARY KEY DEFAULT gen_random_uuid()
learner_id  uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE
subject_id  uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE
concept_id  uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE
status      text NOT NULL DEFAULT 'CREATED'
            CHECK (status IN ('CREATED','IN_PROGRESS','COMPLETED','ABANDONED'))
resolution  jsonb NOT NULL DEFAULT '{}'::jsonb
started_at  timestamptz NOT NULL DEFAULT now()
completed_at timestamptz
created_at  timestamptz NOT NULL DEFAULT now()
updated_at  timestamptz NOT NULL DEFAULT now()
```

### 10. `questions`
```sql
id                  uuid PRIMARY KEY DEFAULT gen_random_uuid()
subject_id          uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE
concept_id          uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE
question_type       text NOT NULL
                    CHECK (question_type IN ('MCQ','SHORT_ANSWER','SCENARIO','DIAGNOSTIC','REASSESSMENT','PROBE'))
difficulty          integer NOT NULL DEFAULT 3 CHECK (difficulty BETWEEN 1 AND 5)
question_text       text NOT NULL
expected_answer     text NOT NULL
expected_reasoning  text NOT NULL DEFAULT ''
diagnostic_targets  jsonb NOT NULL DEFAULT '[]'::jsonb
source_references   jsonb NOT NULL DEFAULT '[]'::jsonb
generation_metadata jsonb NOT NULL DEFAULT '{}'::jsonb
options             jsonb NOT NULL DEFAULT '[]'::jsonb
correct_option_id   text NOT NULL DEFAULT ''
parent_question_id  uuid REFERENCES questions(id) ON DELETE SET NULL
created_at          timestamptz NOT NULL DEFAULT now()
```

### 11. `answers`
```sql
id                   uuid PRIMARY KEY DEFAULT gen_random_uuid()
question_id          uuid NOT NULL REFERENCES questions(id) ON DELETE CASCADE
learner_id           uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE
diagnostic_session_id uuid NOT NULL REFERENCES diagnostic_sessions(id) ON DELETE CASCADE
response             text NOT NULL
reasoning            text NOT NULL DEFAULT ''
correctness          boolean NOT NULL
reasoning_assessment jsonb NOT NULL DEFAULT '{}'::jsonb
evidence_signals     jsonb NOT NULL DEFAULT '[]'::jsonb
selected_option_id   text
created_at           timestamptz NOT NULL DEFAULT now()
```

### 12. `diagnoses`
```sql
id                   uuid PRIMARY KEY DEFAULT gen_random_uuid()
learner_id           uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE
subject_id           uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE
session_id           uuid NOT NULL REFERENCES diagnostic_sessions(id) ON DELETE CASCADE
concept_id           uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE
root_cause           text NOT NULL
                    CHECK (root_cause IN (
                        'MISSING_PREREQUISITE','MISCONCEPTION','PROCEDURAL_ERROR',
                        'TERMINOLOGY_CONFUSION','REPRESENTATION_PROBLEM',
                        'INSUFFICIENT_EVIDENCE'))
confidence           double precision NOT NULL
status               text NOT NULL DEFAULT 'OPEN'
                    CHECK (status IN ('OPEN','RESOLVED','PERSISTENT'))
resolution           jsonb NOT NULL DEFAULT '{}'::jsonb
investigation        jsonb NOT NULL DEFAULT '{}'::jsonb
evidence_references  jsonb NOT NULL DEFAULT '[]'::jsonb
created_at           timestamptz NOT NULL DEFAULT now()
updated_at           timestamptz NOT NULL DEFAULT now()
```

### 13. `lessons`
```sql
id                  uuid PRIMARY KEY DEFAULT gen_random_uuid()
learner_id          uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE
subject_id          uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE
diagnosis_id        uuid REFERENCES diagnoses(id) ON DELETE SET NULL
concept_id          uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE
root_cause          text NOT NULL
                    CHECK (root_cause IN (
                        'MISSING_PREREQUISITE','MISCONCEPTION','PROCEDURAL_ERROR',
                        'TERMINOLOGY_CONFUSION','REPRESENTATION_PROBLEM',
                        'INSUFFICIENT_EVIDENCE'))
teaching_action     text NOT NULL
teaching_strategy   text NOT NULL
interest_context    text NOT NULL DEFAULT 'normal'
explanation         text NOT NULL DEFAULT ''
visualization_spec  jsonb NOT NULL DEFAULT '{}'::jsonb
source_references   jsonb NOT NULL DEFAULT '[]'::jsonb
attempt             integer NOT NULL DEFAULT 1
status              text NOT NULL DEFAULT 'DELIVERED'
                    CHECK (status IN ('DELIVERED','COMPLETED'))
created_at          timestamptz NOT NULL DEFAULT now()
updated_at          timestamptz NOT NULL DEFAULT now()
```

### 14. `reassessments` (NEW — M7)
```sql
id                  uuid PRIMARY KEY DEFAULT gen_random_uuid()
lesson_id           uuid NOT NULL REFERENCES lessons(id) ON DELETE CASCADE
learner_id          uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE
subject_id          uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE
concept_id          uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE
diagnosis_id        uuid REFERENCES diagnoses(id) ON DELETE SET NULL
question_id         uuid REFERENCES questions(id) ON DELETE SET NULL
question_type       text NOT NULL DEFAULT 'REASSESSMENT'
                    CHECK (question_type IN ('MCQ','SHORT_ANSWER','REASSESSMENT'))
question_text       text NOT NULL DEFAULT ''
options             jsonb NOT NULL DEFAULT '[]'::jsonb
correct_option_id   text NOT NULL DEFAULT ''
expected_answer     text NOT NULL DEFAULT ''
expected_reasoning  text NOT NULL DEFAULT ''
status              text NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING','PASSED','FAILED','INCONCLUSIVE'))
response            text NOT NULL DEFAULT ''
reasoning           text NOT NULL DEFAULT ''
reasoning_assessment jsonb NOT NULL DEFAULT '{}'::jsonb
correctness         boolean
attempt             integer NOT NULL DEFAULT 1
created_at          timestamptz NOT NULL DEFAULT now()
updated_at          timestamptz NOT NULL DEFAULT now()
```

### 15. `learning_events`
```sql
id          uuid PRIMARY KEY DEFAULT gen_random_uuid()
learner_id  uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE
subject_id  uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE
event_type  text NOT NULL
            CHECK (event_type IN (
                'MATERIAL_UPLOADED','MATERIAL_PROCESSED','DIAGNOSTIC_STARTED',
                'QUESTION_ANSWERED','DIAGNOSIS_CREATED','MISCONCEPTION_DETECTED',
                'MISCONCEPTION_RESOLVED','LESSON_STARTED','LESSON_CONTENT_READY',
                'LESSON_COMPLETED',
                'VISUALIZATION_VIEWED','REASSESSMENT_STARTED','REASSESSMENT_COMPLETED',
                'MASTERY_UPDATED','CONCEPT_UNDERSTAND_REQUESTED','TEST_SESSION_COMPLETED'))
entity_type text NOT NULL DEFAULT ''
entity_id   uuid
metadata    jsonb NOT NULL DEFAULT '{}'::jsonb
timestamp   timestamptz NOT NULL DEFAULT now()
```

---

## Key Data Patterns

### Learner Model Concept States (JSONB in `learner_models.concept_states`)
```json
{
  "concept-uuid": {
    "mastery": 0.65,
    "status": "DEVELOPING",
    "confidence": 0.64,
    "interactionCount": 3,
    "correctCount": 2,
    "incorrectCount": 1,
    "lastAssessedAt": "2026-08-21T..."
  }
}
```

### Strategy Profile (JSONB in `learner_models.strategy_profile`)
```json
{
  "concept-uuid": {
    "VISUAL_STEP_BY_STEP": "IMPROVED",
    "WORKED_EXAMPLE": "NO_CHANGE"
  }
}
```

### Reassessment Flow
```
LESSON (DELIVERED) → REASSESSMENT (PENDING) → ANSWER → 
  PASSED: mastery ↑, misconception RESOLVED, lesson COMPLETED
  FAILED: mastery ↓, strategy recorded, attempt++
  INCONCLUSIVE: small delta based on reasoning
```
