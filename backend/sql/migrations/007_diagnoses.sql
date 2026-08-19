-- EduFusion M4: final diagnoses.
-- A diagnosis is the durable outcome of a diagnostic session: the confirmed
-- root cause, the confidence, the resolution trace, and the evidence
-- references that justify it. This is the historical-evidence record the
-- "Why We Think This" feature reads back from.

create table if not exists public.diagnoses (
    id                   uuid primary key default gen_random_uuid(),
    learner_id           uuid not null references public.users(id) on delete cascade,
    subject_id           uuid not null references public.subjects(id) on delete cascade,
    session_id           uuid not null references public.diagnostic_sessions(id) on delete cascade,
    concept_id           uuid not null references public.concepts(id) on delete cascade,
    root_cause           text not null
                         check (root_cause in (
                             'MISSING_PREREQUISITE','MISCONCEPTION','PROCEDURAL_ERROR',
                             'TERMINOLOGY_CONFUSION','REPRESENTATION_PROBLEM',
                             'INSUFFICIENT_EVIDENCE')),
    confidence           double precision not null,
    status               text not null default 'OPEN'
                         check (status in ('OPEN','RESOLVED','PERSISTENT')),
    resolution           jsonb not null default '{}'::jsonb,
    investigation        jsonb not null default '{}'::jsonb,
    evidence_references  jsonb not null default '[]'::jsonb,
    created_at           timestamptz not null default now(),
    updated_at           timestamptz not null default now()
);

create index if not exists diagnoses_learner_subject_idx
    on public.diagnoses (learner_id, subject_id);
create index if not exists diagnoses_session_idx
    on public.diagnoses (session_id);

alter table public.diagnoses enable row level security;