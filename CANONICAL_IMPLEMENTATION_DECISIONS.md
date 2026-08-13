# EduFusion — Canonical Implementation Decisions

These decisions only normalize implementation-level inconsistencies in the supplied design documents. They do not change the product definition.

## 1. Questions
Canonical table: `questions`.

Use `questionType` to distinguish MCQ, SHORT_ANSWER, SCENARIO, DIAGNOSTIC, REASSESSMENT, and PROBE.

Do not create a separate `diagnostic_questions` table for MVP.

## 2. Root causes
Canonical enum:
- MISSING_PREREQUISITE
- MISCONCEPTION
- PROCEDURAL_ERROR
- TERMINOLOGY_CONFUSION
- REPRESENTATION_PROBLEM
- INSUFFICIENT_EVIDENCE

The final aligned understanding is authoritative here.

## 3. Authentication
Supabase Auth identity is stored/referenced through `authUserId`.
Application profile is `users`.
No Better Auth or MongoDB.

## 4. Storage
Use Supabase Storage for uploaded materials.
`materials.storageReference` stores the storage path/reference.

## 5. State model
Use current-state + event-history, not full event sourcing.

## 6. Mastery
Do not copy any illustrative mastery formula blindly.
Before implementing reassessment, define a simple deterministic MVP formula that is transparent, bounded, testable, and avoids double-counting errors.

## 7. Embeddings
Provider, model, vector dimension, and similarity metric remain explicit implementation decisions.
Document the choice before implementing pgvector retrieval.

## 8. PDF scope
MVP supports text-based PDFs through PyMuPDF or pypdf.
OCR/scanned PDFs and complex image/table extraction are post-MVP.

## 9. Visualization
Architecture is registry-based and extensible.
MVP specialized renderers: Pipeline, Hazard, Forwarding.
Generic fallback is required.

## 10. Table-count wording
One source document says “16 tables specification,” but the supplied concrete schemas do not enumerate 16 concrete tables.
Do not invent tables merely to satisfy that number. Add tables only when a concrete feature requires them.
