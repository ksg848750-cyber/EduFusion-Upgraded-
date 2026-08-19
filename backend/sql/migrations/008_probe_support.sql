-- EduFusion M4: targeted probe support (doc3).
-- A probe is a diagnostic question generated to disambiguate a single
-- hypothesized root cause. It points back to the diagnostic session question
-- that produced the ambiguous signal, and its generation metadata carries the
-- differentiation target (the hypothesis being confirmed/refuted).

alter table public.questions
    add column if not exists parent_question_id uuid
        references public.questions(id) on delete set null;

-- generation_metadata on probe questions carries the differentiation target:
--   { "differentiationTarget": { "hypothesis": "MISSING_PREREQUISITE", ... } }