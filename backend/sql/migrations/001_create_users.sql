-- EduFusion Milestone 1: users / profile persistence
-- App-level profile linked to a Supabase Auth identity via authUserId.

create extension if not exists "pgcrypto";

create table if not exists public.users (
    id           uuid primary key default gen_random_uuid(),
    auth_user_id text not null unique,
    email        text not null unique,
    name         text not null default 'Learner',
    interests    text[] not null default '{}',
    preferences  jsonb not null default '{}'::jsonb,
    is_onboarded boolean not null default false,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

create index if not exists users_email_idx on public.users (email);

alter table public.users enable row level security;
