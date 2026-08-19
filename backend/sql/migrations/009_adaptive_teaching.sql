-- EduFusion M5: Adaptive Teaching Engine (Dual-Decision).
-- Adds the durable teaching-decision record (lessons) and the per-learner
-- strategy outcome history that the Strategy Selector (Decision B) reads.
--
--   lessons            = one row per delivered teaching intervention
--   strategy_profile   = {concept_id: {strategy: outcome}} appended after each
--                        reassessment so the selector can exclude ineffective
--                        strategies and prioritize proven ones (doc4).

alter table public.learner_models
    add column if not exists strategy_profile jsonb not null default '{}'::jsonb;

create table if not exists public.lessons (
    id                  uuid primary key default gen_random_uuid(),
    learner_id          uuid not null references public.users(id) on delete cascade,
    subject_id          uuid not null references public.subjects(id) on delete cascade,
    diagnosis_id        uuid references public.diagnoses(id) on delete set null,
    concept_id          uuid not null references public.concepts(id) on delete cascade,
    root_cause          text not null
                        check (root_cause in (
                            'MISSING_PREREQUISITE','MISCONCEPTION','PROCEDURAL_ERROR',
                            'TERMINOLOGY_CONFUSION','REPRESENTATION_PROBLEM',
                            'INSUFFICIENT_EVIDENCE')),
    teaching_action     text not null,
    teaching_strategy   text not null,
    interest_context    text not null default 'normal',
    explanation         text not null default '',
    visualization_spec  jsonb not null default '{}'::jsonb,
    source_references   jsonb not null default '[]'::jsonb,
    attempt             integer not null default 1,
    status              text not null default 'DELIVERED'
                        check (status in ('DELIVERED','COMPLETED')),
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

create index if not exists lessons_learner_concept_idx
    on public.lessons (learner_id, concept_id);
create index if not exists lessons_learner_subject_idx
    on public.lessons (learner_id, subject_id);

alter table public.lessons enable row level security;