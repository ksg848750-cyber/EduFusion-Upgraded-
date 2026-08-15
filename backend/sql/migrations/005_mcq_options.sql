-- EduFusion M3 refinement: structured MCQ support.
-- Adds selectable option data to questions and records the selected option id
-- on answers so MCQ grading is deterministic and never string-parsed.

-- ---------- questions ----------
alter table public.questions add column if not exists options jsonb not null default '[]'::jsonb;
alter table public.questions add column if not exists correct_option_id text not null default '';

-- ---------- answers ----------
alter table public.answers add column if not exists selected_option_id text;

-- Indexing isn't required for these columns (answered questions are read via
-- question_id), but an index on correct_option_id keeps option lookups cheap.
create index if not exists questions_correct_option_idx
    on public.questions (correct_option_id) where correct_option_id <> '';