-- EduFusion M4.2: diagnostic resolution trace.
-- Persists the M4 Target Resolution on the diagnostic session so the later
-- "Why We Think This" feature can reconstruct WHY this concept was diagnosed
-- (resolved concept, traversal path, root-gap flag, candidates, reason).

alter table public.diagnostic_sessions
    add column if not exists resolution jsonb not null default '{}'::jsonb;