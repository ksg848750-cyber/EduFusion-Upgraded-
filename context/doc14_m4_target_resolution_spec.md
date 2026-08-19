# EduFusion — Document 14: M4 Target Resolution Specification

*Milestone 4 — Diagnostic Reasoning Engine. Approved spec for the M4 diagnostic target-selection resolver.*

---

## Purpose

This document specifies the **deterministic M4 Target Resolution Engine**: the component that decides **which single concept gets diagnosed** when a diagnostic session begins. It is the entry point to the M4 Diagnostic Reasoning Engine (doc10, "MILESTONE 4: DIAGNOSTIC REASONING ENGINE").

The governing principle (AGENTS.md, doc12):

> "LLM proposes, EduFusion decides."

Therefore the LLM **must NOT** choose the concept to diagnose. Target selection is **deterministic**, computed from learner-model state + the M2 knowledge graph. The LLM may only *execute* diagnostic work (generate scenario questions, classify root causes) once the resolver has chosen a target.

---

## Inputs

The resolver consumes only data that already exists (no new tables, no new LLM calls):

1. **Learner model** — `learner_models` row for `(user_id, subject_id)`:
   - `concept_states`: jsonb dict keyed by `concept_id`, each entry:
     - `mastery` (float 0–1)
     - `status` (`UNKNOWN` / `WEAK` / `DEVELOPING` / `MASTERED`)
     - `confidence`
     - `interactionCount`, `correctCount`, `incorrectCount`
     - `lastAssessedAt`
   - Source: `backend/app/services/learner.py` (`get_learner_model`, `apply_evidence`, `_status_for`).

2. **Concepts** — `concepts` rows for `subject_id` (id, name, canonical_name, ...).
   Source: `backend/app/services/concepts.py` (`list_concepts`).

3. **Relationships** — `concept_relationships` rows for `subject_id`, filtered to `PREREQUISITE_OF`.
   Source: `backend/app/services/relationships.py` (`list_relationships`).

No other data is required. The resolver is a pure traversal over these structures.

---

## Candidate Predicate

A concept `C` is a **diagnostic candidate** if and only if:

```
status(C) ∈ { WEAK, DEVELOPING }   AND   interactionCount(C) > 0
```

- `WEAK`  ⇔ `mastery < 0.50` (already defined in `learner.py:WEAK_THRESHOLD`).
- `DEVELOPING` ⇔ `0.50 ≤ mastery < 0.85` (already defined in `learner.py:MASTERED_THRESHOLD`).
- `interactionCount > 0` excludes concepts with no assessed evidence.

**Explicit exclusions:**
- `UNKNOWN` — excluded because there is no evidence to diagnose. A concept with no interactions has not been meaningfully assessed (doc13, §4). "Nothing assessed" is handled separately from "nothing wrong."
- `MASTERED` — excluded; `MASTERED` requires `mastery ≥ 0.85` and `correctCount ≥ 2`.

**No new thresholds are invented.** The predicate reuses the status values and mastery thresholds that M3 already produces deterministically. The only decision not previously encoded is excluding `UNKNOWN` (no evidence), which is specified here.

---

## Candidate Ordering

Candidates are ordered deterministically by:

1. **lowest `mastery` first** (weakest concepts first),
2. **then fewest `interactionCount`** (least-evidence concepts first),
3. **then lexicographic `canonical_name`** (stable final tie-break).

This ordering is fully deterministic and explainable, and it is applied both to the top-level candidate list and (recursively) to prerequisites at each level (see Tie-Breaking).

---

## Prerequisite Traversal Algorithm

### Directionality (verified)

From `backend/app/ai/prompts/extraction.py`:
> `PREREQUISITE_OF: from_concept is a prerequisite for to_concept.`

Therefore, for a concept `X`:
- The **prerequisites** of `X` are all edges where **`to_concept == X`**.
- Each such edge's **`from_concept` is the prerequisite**.

### Acyclicity (verified)

M2 already guarantees the persisted directed graph is acyclic:
- `graph.py:DIRECTED_TYPES = {"PREREQUISITE_OF", "DEPENDS_ON", "PART_OF", "INSTANCE_OF"}`
- `build_graph` runs a DFS `_has_cycle` check and **drops any directed edge that would create a cycle** (`graph.py:577`, "introduces a cycle").

Because `PREREQUISITE_OF` is in `DIRECTED_TYPES`, the persisted `PREREQUISITE_OF` subgraph is **provably acyclic**. M4's resolver requires **no separate cycle-handling mechanism**.

### Recursive rule

Traversal is **recursive upstream**, and does **NOT** stop at the first weak prerequisite.

```
resolve(X, states, edges):
    # 1. Continue upstream while a non-mastered prerequisite exists.
    prereqs = [ p.from_concept
                for p in edges
                if p.relationship_type == 'PREREQUISITE_OF'
                   and p.to_concept == X ]

    # 2. Among prereqs that are NOT mastered, choose the shallowest (ordered) one.
    non_mastered = [ p for p in prereqs if status(p) != 'MASTERED' ]

    if non_mastered:
        # Recurse into the best (most upstream-relevant) non-mastered prerequisite.
        chosen = pick_best(non_mastered)   # see Tie-Breaking
        return resolve(chosen, states, edges)

    # 3. No non-mastered prerequisite: X is the root-most gap to diagnose.
    return X
```

Key behaviors:
- **Do NOT stop at the first weak prerequisite.** The resolver keeps walking upstream so long as a non-mastered prerequisite exists. The **final / root-most non-mastered prerequisite** is the resolved target.
- **If all prerequisites are `MASTERED`**, stop and keep the **original surface candidate** `X`.
- **If `X` has no `PREREQUISITE_OF` prerequisites** (isolated node), `prereqs` is empty → return `X`.
- The **complete traversal path** (every node visited, in order) is preserved for explainability.

### Interpretation note

This matches doc4's "Step backward in Knowledge Graph" / "Step Back to **Foundational** Prerequisite" (doc4:73, doc4:196) and the doc10 demo, where a failure on `forwarding` resolves to `data_dependency` (2 hops up, the root-most non-mastered prerequisite), **not** the shallowest weak node (`data_hazard`). "Shallowest weak" is explicitly **not** the chosen behavior.

---

## Tie-Breaking

When multiple non-mastered prerequisites exist at the same level (or multiple top-level candidates), choose deterministically:

1. **lowest `mastery`** (the weakest prerequisite wins),
2. **then fewest `interactionCount`**,
3. **then lexicographic `canonical_name`**.

This is the same ordering as Candidate Ordering, reused recursively, so the whole resolver is one consistent, deterministic rule.

---

## Fallback Behavior

- **No candidates** (empty `concept_states`, or every assessed concept is `MASTERED`, or none match the predicate):
  Return `NO_TARGET` with a human-readable reason, e.g. "nothing to diagnose — no assessed concept is WEAK or DEVELOPING."
- **All prerequisites mastered for the chosen surface candidate**: return the surface candidate itself as the target (`rootGap = false`).
- **Degrade gracefully, never crash**: any unexpected state shape is treated as a defined outcome, not an exception.

---

## Error Behavior

**Infrastructure / service failures must NOT be converted into `NO_TARGET`.** The resolver distinguishes three terminal statuses:

| Status | Meaning |
|---|---|
| `TARGET_FOUND` | A diagnostic target was resolved. |
| `NO_TARGET` | Resolved legitimately: no assessed concept is a candidate. |
| `RESOLUTION_ERROR` | A non-recoverable failure occurred (e.g. database/service call failed) — distinct from "nothing wrong." |

- `RESOLUTION_ERROR` signals the caller that the resolution did not complete, so the caller can surface a failure instead of silently reporting "nothing to diagnose."
- A missing learner model (never assessed) is **`NO_TARGET`**, not an error: there is genuinely nothing to diagnose.

---

## Output Contract

`TargetResolution` (all fields always present unless marked):

```
{
  "status":            "TARGET_FOUND" | "NO_TARGET" | "RESOLUTION_ERROR",
  "conceptId":         "<uuid>",           // TARGET_FOUND only
  "conceptName":       "...",              // TARGET_FOUND only
  "path":              ["forwarding","data_hazard","data_dependency"],  // traversal trace, root-most last
  "rootGap":           true | false,       // true if target is an upstream prereq, false if surface candidate
  "candidatesConsidered": [ "<conceptName>" , ... ],  // ordered candidates examined
  "reason":            "human-readable explanation"
}
```

- `path` preserves every node visited by the resolver, in traversal order, with the **resolved target as the final element**.
- `candidatesConsidered` lists the top-level candidates in resolved order (lowest mastery → fewest interactions → canonical_name).
- `reason` is a human-readable string explaining why this target was chosen (and, on `NO_TARGET`/`RESOLUTION_ERROR`, why).

---

## Examples

### Example 1 — fresh learner (nothing assessed)
- `concept_states` empty / all `UNKNOWN`, `interactionCount = 0`.
- Candidates: none (predicate requires `interactionCount > 0`).
- **Result:** `status = NO_TARGET`, `reason = "no assessed concept is WEAK or DEVELOPING"`.
- Frontend behavior: suggest studying, not diagnosing.

### Example 2 — foundational gap (matches demo)
Graph: `instruction_cycle → pipeline_stages → data_dependency → data_hazard → forwarding` (each `PREREQUISITE_OF` the next).

States:
| Concept | Status | mastery | interactions |
|---|---|---|---|
| forwarding | WEAK | 0.35 | 2 |
| data_hazard | WEAK | 0.45 | 3 |
| data_dependency | UNKNOWN | 0.0 | 0 |
| pipeline_stages | MASTERED | 0.90 | 4 |
| instruction_cycle | MASTERED | 0.95 | 5 |

- Candidates (assessed, WEAK/DEVELOPING): forwarding (0.35), data_hazard (0.45). Ordered: forwarding, data_hazard.
- Resolve(forwarding): prereqs = [data_hazard], non-mastered → resolve(data_hazard).
  Resolve(data_hazard): prereqs = [data_dependency]. `data_dependency` status is UNKNOWN → not MASTERED → non-mastered → resolve(data_dependency).
  Resolve(data_dependency): prereqs = [pipeline_stages], which is MASTERED → stop.
- **Result:** `TARGET_FOUND`, `conceptId = data_dependency`, `path = ["forwarding","data_hazard","data_dependency"]`, `rootGap = true`.
- Matches doc10 demo (resolve to the root-most non-mastered prerequisite, 2 hops up).

### Example 3 — surface gap, prerequisites healthy
States: `forwarding` WEAK (0.35); `data_hazard` MASTERED; `data_dependency` MASTERED.
- Resolve(forwarding): prereqs = [data_hazard] mastered → stop.
- **Result:** `TARGET_FOUND`, `conceptId = forwarding`, `path = ["forwarding"]`, `rootGap = false`.

### Example 4 — tie-break among multiple weak prerequisites
Graph: `A` has prerequisites `B` (mastery 0.30, 1 interaction) and `C` (mastery 0.30, 4 interactions). `A` is WEAK.
- Resolve(A): non_mastered = [B, C]. Tie-break: equal mastery → fewer interactions → **B**.
- Recurse resolve(B). (Assume B's prerequisites mastered or none.)
- **Result:** `TARGET_FOUND`, `conceptId = B`.

---

## Edge Cases

- **Empty `concept_states`** → `NO_TARGET` (nothing assessed).
- **All assessed concepts `MASTERED`** → `NO_TARGET` (nothing wrong).
- **Isolated concept (no `PREREQUISITE_OF` edges)** → treated as having no prerequisites → surface candidate itself.
- **Candidate's whole upstream chain mastered** → surface candidate (see Example 3).
- **Multiple weak prerequisites** → tie-break by lowest mastery → fewest interactions → canonical_name (Example 4).
- **`UNKNOWN` upstream concept** → `UNKNOWN` is not `MASTERED`, so it is traversed as a non-mastered prerequisite and becomes a valid target (Example 2). This is correct: an unassessed prerequisite is a more likely root cause than the surface concept.
- **Acyclic guarantee** → no cycle code needed; M2 already drops cycle-forming directed edges.

---

## Explicit Non-Goals

The M4 Target Resolution Engine does **NOT**:
- Choose the concept via the LLM (governing principle).
- Classify root causes (that is M4's later step, after target selection).
- Generate scenario/probe questions (later M4 step).
- Persist a diagnosis (later M4 step).
- Traverse `DEPENDS_ON`, `PART_OF`, `INSTANCE_OF`, `CONTRASTS_WITH`, or `RELATED_TO` for resolution.
  - Rationale: doc2:170 defines `DEPENDS_ON` as "**not a strict conceptual dependency** — used for contextual explanation selection," and doc2:169 scopes diagnostic step-back to `PREREQUISITE`. Nothing in the project docs requires `DEPENDS_ON` traversal for M4.
- Handle cycles (M2 guarantees acyclicity).
- Introduce new thresholds beyond those M3 already defines.
- Implement reassessment, visualization, or probe generation (out of scope for this resolver; they are M4/M5+ concerns).
- Write or modify application code as part of this document's approval (implementation is a separate step).

---

## Unit-Test Scenarios

Test the resolver as a pure function over in-memory `(states, concepts, edges)` dicts (no DB).

1. **No candidates** — empty `concept_states` → `NO_TARGET`.
2. **No candidates** — all concepts `MASTERED` → `NO_TARGET`.
3. **Surface candidate, no prerequisites** — WEAK isolated concept → `TARGET_FOUND`, `path=[C]`, `rootGap=false`.
4. **Surface candidate, prerequisites all mastered** → `TARGET_FOUND`, `rootGap=false`.
5. **Single-hop foundational gap** — WEAK concept with one WEAK prerequisite → resolves to the prerequisite.
6. **Multi-hop foundational gap (demo)** — forwarding → data_hazard → data_dependency, with the root-most non-mastered → `TARGET_FOUND` on `data_dependency`, full `path` preserved.
7. **`UNKNOWN` upstream becomes target** — surface WEAK, prereq `UNKNOWN` → target is the `UNKNOWN` prerequisite.
8. **Tie-break by mastery** — two weak prerequisites, different mastery → lower mastery wins.
9. **Tie-break by interactionCount** — equal mastery → fewer interactions wins.
10. **Tie-break by canonical_name** — equal mastery and interactions → lexicographic wins.
11. **Prereq chain fully mastered above** — recursion stops at the first non-mastered, never goes below a mastered prereq.
12. **`RESOLUTION_ERROR`** — a mocked service raises → `RESOLUTION_ERROR`, not `NO_TARGET`.
13. **Missing learner model** (never assessed) → `NO_TARGET`, not error.
14. **Ordering of `candidatesConsidered`** — verifies lowest mastery → fewest interactions → canonical_name ordering.
