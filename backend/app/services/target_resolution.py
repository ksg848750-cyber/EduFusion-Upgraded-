"""M4 Target Resolution Engine (doc14).

Deterministically decides which single concept a diagnostic session should
investigate. Never consults the LLM: it uses learner-model state + the M2
knowledge graph (PREREQUISITE_OF edges).

The pure core ``resolve_target`` operates on in-memory dicts so it is
independently unit-testable without a database. The async wrapper fetches the
required data and maps infrastructure failures to RESOLUTION_ERROR.
"""

from typing import Any

from app.services import concepts as concepts_service
from app.services import learner as learner_service
from app.services import relationships as relationships_service

# Candidate statuses (M3 learner model). MASTERED and UNKNOWN are excluded.
_CANDIDATE_STATUSES = {"WEAK", "DEVELOPING"}
# Traversal follows PREREQUISITE_OF only (doc14, doc2:169).
_PRE_REL = "PREREQUISITE_OF"
_MASTERED = "MASTERED"

_ERROR_REASON = "Failed to load learner model or knowledge graph data."
_NO_MODEL_REASON = "No learner model for this subject — nothing has been assessed."
_NO_TARGET_REASON = "No assessed concept is WEAK or DEVELOPING."


def _empty_result(status: str, reason: str) -> dict[str, Any]:
    return {
        "status": status,
        "conceptId": None,
        "conceptName": None,
        "path": [],
        "rootGap": False,
        "candidatesConsidered": [],
        "reason": reason,
    }


def resolve_target(
    concept_states: dict[str, dict],
    concepts: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    entry_concept_id: str | None = None,
) -> dict[str, Any]:
    """Resolve the diagnostic target from in-memory learner + graph data.

    - concept_states: {concept_id: {mastery, status, interactionCount, ...}}
    - concepts: list of {id, name, canonicalName, ...}
    - relationships: list of {fromConceptId, toConceptId, relationshipType, ...}
    - entry_concept_id: the concept the learner selected. When provided, the
      resolution starts from it and walks upstream prerequisites; the resolved
      target may be the entry concept itself or an upstream prerequisite. When
      omitted, the subject-wide weakest candidate is used (legacy behaviour).

    Returns a TargetResolution dict with status TARGET_FOUND or NO_TARGET.
    Raises ValueError when the input is structurally invalid.
    """
    concepts_by_id: dict[str, dict[str, Any]] = {}
    for c in concepts:
        cid = c.get("id")
        if not cid:
            continue
        concepts_by_id[cid] = c

    if not concepts_by_id:
        raise ValueError("No concepts provided to target resolver")

    def state(cid: str) -> dict[str, Any]:
        return concept_states.get(cid) or {}

    def status(cid: str) -> str:
        return state(cid).get("status") or "UNKNOWN"

    def mastery(cid: str) -> float:
        return float(state(cid).get("mastery") or 0.0)

    def interactions(cid: str) -> int:
        return int(state(cid).get("interactionCount") or 0)

    def canonical(cid: str) -> str:
        c = concepts_by_id.get(cid)
        if not c:
            return cid
        return c.get("canonicalName") or c.get("name") or cid

    # Build prerequisite index: concept -> [prerequisite concept ids].
    prereqs: dict[str, list[str]] = {}
    for rel in relationships:
        if rel.get("relationshipType") != _PRE_REL:
            continue
        to_id = rel.get("toConceptId")
        from_id = rel.get("fromConceptId")
        if to_id and from_id and from_id != to_id:
            prereqs.setdefault(to_id, []).append(from_id)

    # Subject-wide candidates (used when no entry concept is supplied).
    candidates = [
        cid
        for cid in concepts_by_id
        if status(cid) in _CANDIDATE_STATUSES and interactions(cid) > 0
    ]
    candidates.sort(key=lambda cid: (mastery(cid), interactions(cid), canonical(cid)))

    def non_mastered_prereqs(cid: str) -> list[str]:
        return [p for p in prereqs.get(cid, []) if status(p) != _MASTERED]

    def walk(cid: str, path: list[str]) -> tuple[str, list[str]]:
        pending = non_mastered_prereqs(cid)
        if not pending:
            return cid, path
        chosen = min(pending, key=lambda p: (mastery(p), interactions(p), canonical(p)))
        path.append(chosen)
        return walk(chosen, path)

    if entry_concept_id is not None:
        # The learner selected a concept: start resolution from it. The target
        # may be that concept or an upstream prerequisite it depends on.
        if entry_concept_id not in concepts_by_id:
            return _empty_result("NO_TARGET", "Entry concept not found in the graph.")
        surface = entry_concept_id
        considered = [surface]
    else:
        # First (highest-priority) subject-wide candidate resolves (doc14 §7).
        if not candidates:
            return _empty_result("NO_TARGET", _NO_TARGET_REASON)
        surface = candidates[0]
        considered = candidates

    path = [surface]
    target, path = walk(surface, path)
    root_gap = target != surface

    if root_gap:
        hops = len(path) - 1
        reason = (
            f"Foundational unmastered prerequisite resolved {hops} hop(s) upstream "
            f"from surface concept '{canonical(surface)}'."
        )
    else:
        reason = (
            f"Concept '{canonical(surface)}' is the gap; its prerequisites are "
            "mastered or absent."
        )

    return {
        "status": "TARGET_FOUND",
        "conceptId": target,
        "conceptName": canonical(target),
        "path": [canonical(c) for c in path],
        "rootGap": root_gap,
        "candidatesConsidered": [canonical(c) for c in candidates],
        "reason": reason,
    }


async def resolve_diagnostic_target(
    user_id: str, subject_id: str, entry_concept_id: str | None = None
) -> dict[str, Any]:
    """Fetch learner + graph data and resolve the diagnostic target.

    Infrastructure/service failures surface as RESOLUTION_ERROR (never NO_TARGET).
    """
    try:
        model = await learner_service.get_learner_model(user_id, subject_id)
        concepts = await concepts_service.list_concepts(subject_id)
        relationships = await relationships_service.list_relationships(subject_id)
    except Exception:
        return _empty_result("RESOLUTION_ERROR", _ERROR_REASON)

    if model is None:
        # No prior assessment. When the learner explicitly selected a concept
        # (Test yourself), there is no learner signal to route upstream — the
        # honest target is the concept they asked about. Subject-wide resolution
        # still needs an assessed model.
        if entry_concept_id is not None:
            name = None
            for c in concepts:
                if c.get("id") == entry_concept_id:
                    name = c.get("canonicalName") or c.get("name")
                    break
            if not name:
                return _empty_result("NO_TARGET", "Entry concept not found in the graph.")
            return {
                "status": "TARGET_FOUND",
                "conceptId": entry_concept_id,
                "conceptName": name,
                "path": [name],
                "rootGap": False,
                "candidatesConsidered": [name],
                "reason": (
                    "No prior assessment — testing the concept you selected "
                    "before resolving any prerequisites."
                ),
            }
        return _empty_result("NO_TARGET", _NO_MODEL_REASON)

    concept_states = model.get("conceptStates") or {}
    try:
        return resolve_target(concept_states, concepts, relationships, entry_concept_id)
    except ValueError:
        return _empty_result("RESOLUTION_ERROR", _ERROR_REASON)
