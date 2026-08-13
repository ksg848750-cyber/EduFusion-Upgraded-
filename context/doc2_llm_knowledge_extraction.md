# EduFusion — Document 2: LLM Knowledge Extraction Architecture
*Technical Design Phase. Complete & Finalized Document.*

---

## Governing Principle

> EduFusion transforms raw uploaded materials into structured knowledge before any learner assessment begins.
> **Vector Search** provides semantic retrieval ("Which text is relevant?"); **Knowledge Graph** provides structural comprehension ("What concepts exist and how do they depend on each other?").
> The LLM proposes candidate concepts and relationships; deterministic backend code validates, canonicalizes, checks for cycles, and enforces database truth.

---

## Complete Pipeline Architecture

```
                       STUDENT UPLOAD (PDF)
                                │
                                ▼
                       ┌─────────────────┐
                       │ PDF Extraction  │
                       └────────┬────────┘
                                ▼
                       ┌─────────────────┐
                       │ Text Cleaning   │
                       └────────┬────────┘
                                ▼
                       ┌─────────────────┐
                       │ Semantic Chunk  │
                       └────────┬────────┘
                                │
               ┌────────────────┴────────────────┐
               ▼                                 ▼
       PATH A: VECTOR SEARCH            PATH B: KNOWLEDGE GRAPH
               │                                 │
               ▼                                 ▼
      Embedding Generator               LLM Concept Extractor
               │                                 │
               ▼                                 ▼
pgvector Vector Index (Supabase)      Candidate Concepts
                                                 │
                                                 ▼
                                       Concept Normalization
                                                 │
                                                 ▼
                                     LLM Relationship Extractor
                                                 │
                                                 ▼
                                        Graph Validation
                                     (Cycle & Edge Checking)
                                                 │
                                                 ▼
                                    Supabase PostgreSQL Graph Storage
```

---

## Detailed Pipeline Stages

### Stage 1: File Ingestion & Parsing
- **Input**: Uploaded file (`Computer_Architecture_Notes.pdf`).
- **Target File Types**: Text-based PDFs for MVP (PyMuPDF / pypdf).
- **Extracted Structure**:
  - Raw text per page.
  - Page boundaries (`pageNumber`).
  - Section headings (`headingPath` e.g., `["3.0 Pipelining", "3.4 Pipeline Hazards"]`).
- **Output Record**: `materials` table row (`processingStatus = PROCESSING`).

### Stage 2: Structural Text Cleaning
Normalized without altering pedagogical meaning.
- Fix word hyphenation across lines (`pipel-` + `ine` $\rightarrow$ `pipeline`).
- Remove repetitive header/footer artifacts (e.g., page numbers, chapter watermarks).
- Normalize whitespace and preserve heading hierarchies.
- Maintain strict mapping between cleaned text blocks and source `pageNumber`.

### Stage 3: Semantic Document Chunking
Rather than arbitrary character/token splits, chunks preserve semantic completeness.
- **Boundaries**: Split on paragraph/subsection breaks where possible.
- **Context Overlap**: Small sliding window overlap to avoid severing concepts split across boundaries.
- **Metadata Tagging**: Each chunk carries `materialId`, `subjectId`, `chunkIndex`, `pageNumber`, `headingPath`.

### Stage 4: Dual-Path Processing

#### Path A: Vector Memory (RAG Foundation)
1. **Embedding Generation**: Text chunks sent to embedding model (model & dimensions TBD in Implementation Phase).
2. **Database Record**: Written to `document_chunks` table with `embedding` float vector.
3. **Index**: Indexed via pgvector in Supabase PostgreSQL for semantic similarity queries during lesson generation.

#### Path B: Knowledge Graph Extraction

```
Chunk + Heading Context ──► LLM Concept Extractor ──► Candidate Concepts
                                                           │
                                                           ▼
                                                 Canonical Deduplication
                                                           │
                                                           ▼
                                                LLM Relationship Extractor
                                                           │
                                                           ▼
                                                Deterministic Graph Validator
                                                           │
                                                           ▼
                                                 Supabase PostgreSQL concepts &
                                                 concept_relationships
```

---

## LLM Output Contracts (Pydantic Validation Schemas)

The LLM is invoked with `response_format={"type": "json_object"}`. The backend validates the response against strict Pydantic schemas before saving.

### 1. Candidate Concept Schema
```json
{
  "concepts": [
    {
      "name": "Data Hazard",
      "description": "A pipeline hazard occurring when an instruction requires data produced by an earlier instruction still in execution.",
      "difficulty": 3,
      "expectedUnderstanding": "Student understands that Instruction B cannot proceed until Instruction A's result is computed or forwarded.",
      "commonMisconceptions": [
        "Pipeline stages operate completely independently with no data sharing",
        "Every data hazard requires stalling the pipeline"
      ]
    }
  ]
}
```

### 2. Candidate Relationship Schema
```json
{
  "relationships": [
    {
      "fromConceptName": "Data Hazard",
      "toConceptName": "Forwarding",
      "relationshipType": "PREREQUISITE",
      "description": "Forwarding cannot be understood without first understanding why data hazards occur.",
      "confidence": 0.91
    }
  ]
}
```

---

## Concept Normalization & Deduplication

To prevent duplicate nodes (`"Data Hazard"`, `"Data hazards"`, `"data_hazard"`):

1. **Canonical Key Generation**:
   $$\text{canonicalName} = \text{slugify}(\text{lowercase}(\text{trim}(\text{concept.name})))$$
   *Example*: `"Data Hazards"` $\rightarrow$ `"data_hazard"`.

2. **Deduplication Logic**:
   - Query `concepts` where `subjectId = currentSubjectId` AND `canonicalName = candidateCanonicalName`.
   - **If exists**: Merge `sourceReferences` and append new `commonMisconceptions`.
   - **If new**: Insert new row into `concepts`.

---

## Relationship Taxonomy & Validation Rules

### Allowed Relationship Types
| Enum Value | Semantic Meaning | Diagnostic Impact |
|---|---|---|
| `PREREQUISITE` | $A$ must be understood before $B$ can be reliably learned | Diagnostic Engine steps back to $A$ if $B$ fails |
| `DEPENDS_ON` | $B$ uses $A$, but $A$ is not a strict conceptual dependency | Used for contextual explanation selection |
| `PART_OF` | $A$ is a component module of $B$ | Used for structural topic breakdown |
| `RELATED_TO` | Connected concepts with no directional dependency | Used for alternative analogies |
| `CONTRASTS_WITH` | Concepts frequently confused or juxtaposed | Used for terminology/representation interventions |

### Deterministic Backend Graph Validation
Before writing edges to `concept_relationships`:

1. **Node Existence Check**: Both `fromConceptId` and `toConceptId` must exist in `concepts`.
2. **Self-Reference Prevention**: Reject if $\text{fromConceptId} == \text{toConceptId}$.
3. **Taxonomy Enforcement**: `relationshipType` must match allowed Enum exactly.
4. **Duplicate Edge Merging**: If edge $(A \xrightarrow{\text{TYPE}} B)$ exists, update confidence & merge `sourceReferences`.
5. **Cycle Detection (PREREQUISITE Edges)**:
   - Run Depth-First Search (DFS) / Tarjan's algorithm on all `PREREQUISITE` edges.
   - If adding $A \xrightarrow{\text{PREREQUISITE}} B$ creates a directed cycle ($A \rightarrow B \rightarrow \dots \rightarrow A$), **REJECT** the edge and log a graph validation warning.

---

## Division of Responsibilities

```
┌─────────────────────────────────────────┐
│              LLM LAYER                  │
│  - Understand natural language text     │
│  - Extract candidate concepts           │
│  - Propose relationships & prerequisites │
│  - Summarize expected understanding     │
└────────────────────┬────────────────────┘
                     │ Candidate JSON
                     ▼
┌─────────────────────────────────────────┐
│            BACKEND LAYER                │
│  - Pydantic schema validation           │
│  - Canonical name slugification          │
│  - Duplicate concept merging            │
│  - Graph cycle detection (DFS)          │
│  - Source chunk mapping & provenance    │
│  - Supabase PostgreSQL database writes  │
└─────────────────────────────────────────┘
```

---

## Grounding & Provenance Tracking

Every extracted concept and relationship carries explicit `sourceReferences`:

```json
"sourceReferences": [
  {
    "materialId": "uuid('66b9...')",
    "chunkId": "uuid('66b9...')",
    "pageNumber": 14
  }
]
```

**Why this matters**:
If EduFusion presents a lesson or diagnosis, it can trace back to the exact chunk and page in the student's original PDF. There are no ungrounded "hallucinated" concept nodes in the Knowledge Graph.

---

## Validation/Demo Example: CPU Pipelining

1. Student uploads `Computer_Architecture_Notes.pdf`.
2. Backend parses 84 pages into 312 semantic chunks and stores embeddings via pgvector in Supabase PostgreSQL.
3. LLM extracts 37 concepts and canonicalizes them (e.g. `instruction_cycle`, `pipeline_stages`, `data_hazard`, `forwarding`, `stalling`).
4. LLM proposes relationships; Backend graph validator checks for cycles and validates prerequisites.
5. Supabase PostgreSQL stores the validated Knowledge Graph.
6. **Result**: The system is ready for diagnostic assessment without hardcoded knowledge nodes.

---

*Document 2 complete. Next: Document 3 — Diagnostic Intelligence Architecture.*
