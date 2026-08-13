# EduFusion — Document 9: Technology Architecture & Learning Guide
*Technical Design Phase. Complete & Finalized Document.*

---

## Governing Principle

> Every technology in EduFusion has a clear, non-redundant job.
> We do not add frameworks for buzzword compliance.
> **LLMs provide probabilistic intelligence; deterministic software provides control.**

---

## The Technology Map & Company Analogy

```
                                  EDUFUSION SYSTEM
                                         │
 ┌───────────────────────────────────────┴───────────────────────────────────────┐
 │                                                                               │
 ▼                                                                               ▼
FRONTEND ("The Front Desk")                                     BACKEND ("The Manager")
Next.js 16 + React 19 + TS                                      FastAPI + Python 3.11+
Handles student UI, state, & rendering                           Orchestrates logic, authz, & rules
 │                                                                               │
 ├─► Supabase Auth ("Security Guard")                                              ├─► Supabase PostgreSQL ("Filing System")
 │   Identity & JWT validation                                                     │   Persistent learner & graph data
 │                                                                               │
 └─► SVG + Framer Motion                                                         ├─► pgvector ("Librarian")
     Visual animation player                                                     │   Semantic chunk retrieval
                                                                                  │
                                                                                  └─► Groq / Llama ("Reasoning Specialist")
                                                                                     Concept & diagnostic intelligence
```

---

## Complete Technology Stack & Responsibilities

| Layer | Selected Technology | Role & Responsibility in EduFusion |
|---|---|---|
| **Web Application** | **Next.js 16 (App Router)** | Client-side routing, React component rendering, user state management. |
| **UI Components** | **React 19** | Component-driven UI architecture (Forms, Cards, Steppers, Modals). |
| **Type System** | **TypeScript** | Static typing & interface contracts for all frontend objects. |
| **Styling & Design** | **Tailwind CSS** | Utility-first styling implementing design tokens from Stitch MCP. |
| **UI/UX Design** | **Stitch MCP** | AI-assisted design exploration, layout prototyping, and design system creation. |
| **Authentication** | **Supabase Auth** | Credentials/OAuth login, session management, signed JWT issuance & JWKS verification. |
| **Backend API** | **FastAPI (Python 3.11+)** | High-performance asynchronous API, business logic, authorization, pipeline orchestration. |
| **Schema Validation** | **Pydantic v2** | Strict validation of incoming API payloads and outgoing LLM JSON objects. |
| **Database** | **Supabase PostgreSQL** | Relational storage (`uuid` primary keys) for `users`, `profiles`, `subjects`, `concepts`, `learner_models`, `learning_events`. |
| **Vector Search** | **pgvector (Supabase PostgreSQL)** | Native vector index on `document_chunks` for RAG semantic retrieval. |
| **Document Processing** | **PyMuPDF / pypdf** | Extracting page text, titles, and layout structures from uploaded PDFs. |
| **LLM Inference** | **Groq SDK** | Ultra-low latency inference for Llama 3.3 70B (reasoning) & Llama 3.1 8B Instant (fast tasks). |
| **Visual Animation** | **SVG + Framer Motion** | Declarative 2D vector animation player for CPU Pipelining & technical diagrams. |
| **Version Control** | **Git / GitHub** | Source code management, feature branching, and commit history. |

---

## Centralized AI Service Abstraction Layer

To avoid scattering Groq SDK calls directly across route files, FastAPI uses an abstracted **`AIService`**:

```
FastAPI Business Route (e.g. /api/v1/lessons)
                       │
                       ▼
                 AIService (Python Class)
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
     Prompt Templates    Pydantic Schema Validator
             │                   │
             └─────────┬─────────┘
                       ▼
               LLM Provider Adapter
                       │
                       ▼
                  Groq SDK Call
```

**Benefit**: If we switch LLM models or inference providers, zero business logic routes change. Only the `LLMProviderAdapter` is modified.

---

## Security Architecture & Secret Isolation

```
┌─────────────────────────────────────────────────────────────┐
│                    PUBLIC FRONTEND (Browser)                │
│  - Receives ONLY short-lived Supabase Auth JWTs             │
│  - Receives NO database connection strings                  │
│  - Receives NO AI provider API keys                         │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS API Calls (Bearer Token)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   PRIVATE BACKEND (FastAPI)                 │
│  - Reads `GROQ_API_KEY` from server `.env`                  │
│  - Reads `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` from server `.env` │
│  - Verifies Supabase Auth JWTs via Supabase JWKS            │
└─────────────────────────────────────────────────────────────┘
```

- **Rule**: Secrets NEVER enter Next.js client bundles (`NEXT_PUBLIC_` prefix is prohibited for backend keys).

---

## Technology Exclusion List (Deliberately Omitted)

We explicitly exclude unnecessary dependencies to maintain architecture clarity:

| Omitted Technology | Reason for Exclusion |
|---|---|
| **LangChain / LlamaIndex** | Adds unnecessary abstraction overhead. We write simple, explicit RAG pipelines using Python + pgvector Vector Search. |
| **Qdrant / Pinecone** | Supabase PostgreSQL's native pgvector handles vector retrieval directly, eliminating extra database infrastructure. |
| **Redis** | Supabase PostgreSQL handles session state and caching for MVP scale. |
| **Neo4j** | Graph relationships are efficiently queried in PostgreSQL using `concept_relationships` and `fromConceptId` indexes. |
| **Docker / Kubernetes** | Unnecessary deployment complexity for hackathon MVP. Next.js deploys on Vercel; FastAPI deploys on Render/Railway. |

---

## Progressive Learning Roadmap (What to Master Before Coding)

```
PHASE 1: FRONTEND FOUNDATIONS
React 19 (State, Props, Effects) ──► Next.js App Router ──► TypeScript Interfaces

PHASE 2: BACKEND & DATA VALIDATION
Python Async/Await ──► FastAPI Routes & Dependency Injection ──► Pydantic v2 Schemas

PHASE 3: DATABASE & VECTOR SEARCH
Supabase SQL / PostgREST ──► PostgreSQL Relational Modeling ──► pgvector (HNSW) Index Queries

PHASE 4: RAG & LLM ORCHESTRATION
Chunking Strategies ──► Embedding Model Call ──► Prompt Engineering ──► JSON Schema Mode

PHASE 5: VISUALIZATION RENDERER
SVG Path Construction ──► Framer Motion Step Transitions ──► React Player Sync
```

---

## Evaluator / Judge Defense Q&A Guide

When presenting EduFusion, use these concise technical answers:

- **Q: Why use Next.js + FastAPI instead of a pure Next.js stack?**
  - **A**: *"Next.js delivers a responsive, interactive UI. FastAPI in Python gives us native access to the Python AI/ML ecosystem (PDF parsing, embeddings, RAG, LLM orchestration) with high-performance Pydantic validation."*

- **Q: Why pgvector (Supabase) over Qdrant or Pinecone?**
  - **A**: *"Supabase PostgreSQL with pgvector allows our document chunks, embeddings, Knowledge Graph nodes, and Learner Model state to reside in one unified, relational, high-performance database, integrated with Supabase Auth."*

- **Q: Why not let the LLM generate React code for visualizations directly?**
  - **A**: *"LLMs generating executable code at runtime is slow, unsecure, and prone to breaking UI rendering. We use the LLM to output a validated, declarative JSON spec, while our frontend SVG/Framer Motion renderer deterministically renders the exact hardware concept."*

- **Q: How does EduFusion prevent LLM hallucinations in lessons?**
  - **A**: *"Every lesson is grounded via RAG retrieval from the student's uploaded material. Explanations carry explicit `sourceReferences` linking back to the exact chunk and page number."*

---

*Document 9 complete. Next: Document 10 — Implementation Plan.*
