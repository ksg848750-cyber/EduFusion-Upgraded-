-- EduFusion Milestone 2: knowledge ingestion & knowledge graph.
-- Knowledge-world tables: subjects, materials, document_chunks, concepts,
-- concept_relationships. pgvector provides the vector type + HNSW index.

create extension if not exists "vector";

-- ---------- subjects ----------
create table if not exists public.subjects (
    id            uuid primary key default gen_random_uuid(),
    owner_id      uuid not null references public.users(id) on delete cascade,
    name          text not null,
    description   text not null default '',
    status        text not null default 'ACTIVE' check (status in ('ACTIVE','ARCHIVED')),
    concept_count integer not null default 0,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

create index if not exists subjects_owner_idx on public.subjects (owner_id);

-- ---------- materials ----------
create table if not exists public.materials (
    id                uuid primary key default gen_random_uuid(),
    subject_id        uuid not null references public.subjects(id) on delete cascade,
    owner_id          uuid not null references public.users(id) on delete cascade,
    filename          text not null,
    file_type         text not null default 'PDF' check (file_type in ('PDF','DOCX','PPTX','TXT','IMAGE')),
    storage_reference text not null default '',
    processing_status text not null default 'UPLOADED'
                      check (processing_status in ('UPLOADED','PROCESSING','COMPLETED','FAILED')),
    page_count        integer,
    processing_error  text,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);

create index if not exists materials_subject_idx on public.materials (subject_id);
create index if not exists materials_owner_idx on public.materials (owner_id);
create index if not exists materials_status_idx on public.materials (processing_status);

-- ---------- document_chunks ----------
create table if not exists public.document_chunks (
    id           uuid primary key default gen_random_uuid(),
    material_id  uuid not null references public.materials(id) on delete cascade,
    subject_id   uuid not null references public.subjects(id) on delete cascade,
    chunk_index  integer not null,
    text         text not null,
    page_number  integer,
    section_title text,
    metadata     jsonb not null default '{}'::jsonb,
    embedding    vector(384),
    created_at   timestamptz not null default now(),
    unique (material_id, chunk_index)
);

create index if not exists document_chunks_subject_idx on public.document_chunks (subject_id);
create index if not exists document_chunks_embedding_hnsw
    on public.document_chunks using hnsw (embedding vector_cosine_ops);

-- ---------- concepts ----------
create table if not exists public.concepts (
    id                  uuid primary key default gen_random_uuid(),
    subject_id          uuid not null references public.subjects(id) on delete cascade,
    name                text not null,
    canonical_name      text not null,
    description         text not null default '',
    difficulty          integer not null default 3 check (difficulty between 1 and 5),
    expected_understanding text not null default '',
    common_misconceptions jsonb not null default '[]'::jsonb,
    source_references   jsonb not null default '[]'::jsonb,
    extraction_metadata jsonb not null default '{}'::jsonb,
    embedding           vector(384),
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    unique (subject_id, canonical_name)
);

create index if not exists concepts_subject_idx on public.concepts (subject_id);

-- ---------- concept_relationships ----------
create table if not exists public.concept_relationships (
    id                  uuid primary key default gen_random_uuid(),
    subject_id          uuid not null references public.subjects(id) on delete cascade,
    from_concept_id     uuid not null references public.concepts(id) on delete cascade,
    to_concept_id       uuid not null references public.concepts(id) on delete cascade,
    relationship_type   text not null
                        check (relationship_type in ('PREREQUISITE','DEPENDS_ON','PART_OF','RELATED_TO','CONTRASTS_WITH')),
    confidence          double precision not null default 1.0,
    source_references   jsonb not null default '[]'::jsonb,
    extraction_metadata jsonb not null default '{}'::jsonb,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    check (from_concept_id <> to_concept_id),
    unique (subject_id, from_concept_id, to_concept_id, relationship_type)
);

create index if not exists concept_relationships_subject_idx on public.concept_relationships (subject_id);

-- RLS: backend connects with the service role (bypasses RLS); ownership is
-- enforced at the application layer. Enabled here for defense-in-depth parity
-- with the users table.
alter table public.subjects enable row level security;
alter table public.materials enable row level security;
alter table public.document_chunks enable row level security;
alter table public.concepts enable row level security;
alter table public.concept_relationships enable row level security;
