-- EduFusion M7: Reassessment + Learner Model.
-- Adds the reassessment record that closes the adaptive loop:
--   DIAGNOSTIC → TEACH → REASSESS → UPDATE → REPEAT
--
--   reassessments = one row per reassessment question delivered after a lesson
--                   tracks the outcome (PASSED/FAILED/INCONCLUSIVE) and feeds
--                   the mastery update engine and strategy outcome recorder.

create table if not exists public.reassessments (
    id                  uuid primary key default gen_random_uuid(),
    lesson_id           uuid not null references public.lessons(id) on delete cascade,
    learner_id          uuid not null references public.users(id) on delete cascade,
    subject_id          uuid not null references public.subjects(id) on delete cascade,
    concept_id          uuid not null references public.concepts(id) on delete cascade,
    diagnosis_id        uuid references public.diagnoses(id) on delete set null,
    question_id         uuid references public.questions(id) on delete set null,
    question_type       text not null default 'REASSESSMENT'
                        check (question_type in ('MCQ','SHORT_ANSWER','REASSESSMENT')),
    question_text       text not null default '',
    options             jsonb not null default '[]'::jsonb,
    correct_option_id   text not null default '',
    expected_answer     text not null default '',
    expected_reasoning  text not null default '',
    status              text not null default 'PENDING'
                        check (status in ('PENDING','PASSED','FAILED','INCONCLUSIVE')),
    response            text not null default '',
    reasoning           text not null default '',
    reasoning_assessment jsonb not null default '{}'::jsonb,
    correctness         boolean,
    attempt             integer not null default 1,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

create index if not exists reassessments_lesson_idx
    on public.reassessments (lesson_id);
create index if not exists reassessments_learner_concept_idx
    on public.reassessments (learner_id, concept_id);

alter table public.reassessments enable row level security;
