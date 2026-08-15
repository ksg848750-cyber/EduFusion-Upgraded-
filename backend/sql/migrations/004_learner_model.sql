-- EduFusion Milestone 3: adaptive learner model & topic understanding.
-- Learner-world + activity-world tables: learner_models, misconceptions,
-- diagnostic_sessions, questions, answers, learning_events.
--
-- Design notes (current-state + event-history):
--   learner_models     = current learner state per (user, subject)
--   misconceptions     = current misconception state per learner
--   questions/answers  = historical evidence
--   diagnostic_sessions= assessment session orchestration
--   learning_events    = immutable append-only history
--
-- Concept states are stored as a jsonb map keyed by concept uuid, giving fast
-- point reads/writes while keeping one row per (user, subject).

-- ---------- learner_models ----------
create table if not exists public.learner_models (
    id              uuid primary key default gen_random_uuid(),
    user_id         uuid not null references public.users(id) on delete cascade,
    subject_id      uuid not null references public.subjects(id) on delete cascade,
    overall_mastery double precision not null default 0.0,
    concept_states  jsonb not null default '{}'::jsonb,
    version         integer not null default 1,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    unique (user_id, subject_id)
);

create index if not exists learner_models_user_subject_idx
    on public.learner_models (user_id, subject_id);

-- ---------- misconceptions ----------
create table if not exists public.misconceptions (
    id                  uuid primary key default gen_random_uuid(),
    learner_id          uuid not null references public.users(id) on delete cascade,
    subject_id          uuid not null references public.subjects(id) on delete cascade,
    concept_id          uuid not null references public.concepts(id) on delete cascade,
    category            text not null
                        check (category in (
                            'MISSING_PREREQUISITE','MISCONCEPTION','PROCEDURAL_ERROR',
                            'TERMINOLOGY_CONFUSION','REPRESENTATION_PROBLEM',
                            'INSUFFICIENT_EVIDENCE')),
    statement           text not null,
    confidence          double precision not null default 0.5,
    evidence_references jsonb not null default '[]'::jsonb,
    status              text not null default 'SUSPECTED'
                        check (status in ('SUSPECTED','CONFIRMED','ACTIVE','RESOLVED','PERSISTENT')),
    first_detected_at   timestamptz not null default now(),
    last_confirmed_at   timestamptz,
    resolved_at         timestamptz,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    unique (learner_id, subject_id, concept_id, category, statement)
);

create index if not exists misconceptions_learner_subject_idx
    on public.misconceptions (learner_id, subject_id, status);
create index if not exists misconceptions_learner_concept_idx
    on public.misconceptions (learner_id, concept_id);

-- ---------- diagnostic_sessions ----------
create table if not exists public.diagnostic_sessions (
    id          uuid primary key default gen_random_uuid(),
    learner_id  uuid not null references public.users(id) on delete cascade,
    subject_id  uuid not null references public.subjects(id) on delete cascade,
    concept_id  uuid not null references public.concepts(id) on delete cascade,
    status      text not null default 'CREATED'
                check (status in ('CREATED','IN_PROGRESS','COMPLETED','ABANDONED')),
    started_at  timestamptz not null default now(),
    completed_at timestamptz,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create index if not exists diagnostic_sessions_learner_subject_idx
    on public.diagnostic_sessions (learner_id, subject_id);

-- ---------- questions ----------
create table if not exists public.questions (
    id                  uuid primary key default gen_random_uuid(),
    subject_id          uuid not null references public.subjects(id) on delete cascade,
    concept_id          uuid not null references public.concepts(id) on delete cascade,
    question_type       text not null
                        check (question_type in ('MCQ','SHORT_ANSWER','SCENARIO','DIAGNOSTIC','REASSESSMENT','PROBE')),
    difficulty          integer not null default 3 check (difficulty between 1 and 5),
    question_text       text not null,
    expected_answer     text not null,
    expected_reasoning  text not null default '',
    diagnostic_targets  jsonb not null default '[]'::jsonb,
    source_references   jsonb not null default '[]'::jsonb,
    generation_metadata jsonb not null default '{}'::jsonb,
    created_at          timestamptz not null default now()
);

create index if not exists questions_subject_concept_idx
    on public.questions (subject_id, concept_id);

-- ---------- answers ----------
create table if not exists public.answers (
    id                   uuid primary key default gen_random_uuid(),
    question_id          uuid not null references public.questions(id) on delete cascade,
    learner_id           uuid not null references public.users(id) on delete cascade,
    diagnostic_session_id uuid not null references public.diagnostic_sessions(id) on delete cascade,
    response             text not null,
    reasoning            text not null default '',
    correctness          boolean not null,
    reasoning_assessment jsonb not null default '{}'::jsonb,
    evidence_signals     jsonb not null default '[]'::jsonb,
    created_at           timestamptz not null default now()
);

create index if not exists answers_learner_question_idx
    on public.answers (learner_id, question_id);
create index if not exists answers_session_question_idx
    on public.answers (diagnostic_session_id, question_id);

-- ---------- learning_events ----------
create table if not exists public.learning_events (
    id          uuid primary key default gen_random_uuid(),
    learner_id  uuid not null references public.users(id) on delete cascade,
    subject_id  uuid not null references public.subjects(id) on delete cascade,
    event_type  text not null
                check (event_type in (
                    'MATERIAL_UPLOADED','MATERIAL_PROCESSED','DIAGNOSTIC_STARTED',
                    'QUESTION_ANSWERED','DIAGNOSIS_CREATED','MISCONCEPTION_DETECTED',
                    'MISCONCEPTION_RESOLVED','LESSON_STARTED','LESSON_COMPLETED',
                    'VISUALIZATION_VIEWED','REASSESSMENT_STARTED','REASSESSMENT_COMPLETED',
                    'MASTERY_UPDATED','CONCEPT_UNDERSTAND_REQUESTED','TEST_SESSION_COMPLETED')),
    entity_type text not null default '',
    entity_id   uuid,
    metadata    jsonb not null default '{}'::jsonb,
    timestamp   timestamptz not null default now()
);

create index if not exists learning_events_learner_ts_idx
    on public.learning_events (learner_id, timestamp);

-- RLS: backend connects with the service role (bypasses RLS); ownership is
-- enforced at the application layer. Enabled here for defense-in-depth parity
-- with the M1/M2 tables.
alter table public.learner_models enable row level security;
alter table public.misconceptions enable row level security;
alter table public.diagnostic_sessions enable row level security;
alter table public.questions enable row level security;
alter table public.answers enable row level security;
alter table public.learning_events enable row level security;