# Fresh OpenCode Start Prompt

You are starting EduFusion from a clean repository.

Before doing anything:
1. Read `AGENTS.md`.
2. Read `context/edufusion_understanding.md`.
3. Read the relevant technical documents, especially Docs 1, 7, 8, 9, and 10.
4. Do NOT revive the old MongoDB/Better Auth implementation.
5. Do NOT start Milestone 2+.

Your immediate task is **Milestone 1 — Foundation & Auth only**.

Establish:
- frontend/ with Next.js + React + TypeScript
- backend/ with FastAPI + Python
- Supabase Auth
- Supabase PostgreSQL
- FastAPI Supabase JWT verification
- users/profile persistence
- health endpoint
- authenticated backend endpoint
- frontend login/signup
- authenticated frontend request to backend

Do not add MongoDB, Better Auth, Firebase, LangChain, LlamaIndex, Redis, Neo4j, Qdrant, Pinecone, or unnecessary infrastructure.

First inspect the clean repository and state the proposed Milestone 1 structure. Then implement it in small verified steps.

Prove:
1. backend starts
2. frontend starts
3. Supabase connects
4. signup works
5. login works
6. JWT verification works
7. unauthenticated protected request is rejected
8. authenticated protected request succeeds
9. user record persists

Do not proceed to Milestone 2 until Milestone 1 is actually verified.
