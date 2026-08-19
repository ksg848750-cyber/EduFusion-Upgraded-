"""Unit tests for the M4 Target Resolution Engine (doc14).

The pure ``resolve_target`` is tested directly with in-memory data. The async
wrapper's error/fallback behavior is tested with mocked services.
"""

import asyncio

import pytest

from app.services import concepts as concepts_service
from app.services import learner as learner_service
from app.services import relationships as relationships_service
from app.services import target_resolution as tr
from app.services.target_resolution import resolve_target


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _concepts(names: list[tuple[str, str]]) -> list[dict]:
    """Return concepts list from [(canonical_name, id)] pairs."""
    return [{"id": cid, "name": cname, "canonicalName": cname} for cname, cid in names]


def _states(mapping: dict[str, dict]) -> dict[str, dict]:
    """Return concept_states from {id: {status, mastery, interactionCount}}."""
    states = {}
    for cid, fields in mapping.items():
        states[cid] = {
            "mastery": fields.get("mastery", 0.0),
            "status": fields.get("status", "UNKNOWN"),
            "interactionCount": fields.get("interactionCount", 0),
        }
    return states


def _pre(edges: list[tuple[str, str]]) -> list[dict]:
    """Return PREREQUISITE_OF relationships from [(from_id, to_id)]."""
    return [
        {"fromConceptId": f, "toConceptId": t, "relationshipType": "PREREQUISITE_OF"}
        for f, t in edges
    ]


# --------------------------------------------------------------------------- #
# 1. No candidates
# --------------------------------------------------------------------------- #

def test_no_candidates_empty_states():
    concepts = _concepts([("forwarding", "f"), ("data_hazard", "h"), ("data_dependency", "d")])
    result = resolve_target({}, concepts, [])
    assert result["status"] == "NO_TARGET"
    assert result["conceptId"] is None
    assert result["path"] == []


def test_no_candidates_all_mastered():
    concepts = _concepts([("forwarding", "f"), ("data_hazard", "h")])
    states = _states({
        "f": {"status": "MASTERED", "mastery": 0.9, "interactionCount": 4},
        "h": {"status": "MASTERED", "mastery": 0.95, "interactionCount": 5},
    })
    result = resolve_target(states, concepts, [])
    assert result["status"] == "NO_TARGET"


def test_unknown_excluded_from_candidates():
    concepts = _concepts([("forwarding", "f"), ("data_hazard", "h")])
    states = _states({
        "f": {"status": "UNKNOWN", "mastery": 0.0, "interactionCount": 0},
        "h": {"status": "UNKNOWN", "mastery": 0.0, "interactionCount": 0},
    })
    result = resolve_target(states, concepts, [])
    assert result["status"] == "NO_TARGET"


def test_zero_interactions_excluded_from_candidates():
    concepts = _concepts([("forwarding", "f")])
    states = _states({"f": {"status": "WEAK", "mastery": 0.3, "interactionCount": 0}})
    result = resolve_target(states, concepts, [])
    assert result["status"] == "NO_TARGET"


# --------------------------------------------------------------------------- #
# 3. Surface candidate, no prerequisites
# --------------------------------------------------------------------------- #

def test_weak_isolated_concept_resolves_itself():
    concepts = _concepts([("forwarding", "f")])
    states = _states({"f": {"status": "WEAK", "mastery": 0.3, "interactionCount": 2}})
    result = resolve_target(states, concepts, [])
    assert result["status"] == "TARGET_FOUND"
    assert result["conceptId"] == "f"
    assert result["path"] == ["forwarding"]
    assert result["rootGap"] is False


# --------------------------------------------------------------------------- #
# 4. Surface candidate, prerequisites all mastered
# --------------------------------------------------------------------------- #

def test_prerequisites_all_mastered_keeps_surface():
    concepts = _concepts([("forwarding", "f"), ("data_hazard", "h")])
    states = _states({
        "f": {"status": "WEAK", "mastery": 0.3, "interactionCount": 2},
        "h": {"status": "MASTERED", "mastery": 0.9, "interactionCount": 4},
    })
    result = resolve_target(states, concepts, _pre([("h", "f")]))
    assert result["status"] == "TARGET_FOUND"
    assert result["conceptId"] == "f"
    assert result["path"] == ["forwarding"]
    assert result["rootGap"] is False


# --------------------------------------------------------------------------- #
# 5-6. Single-hop and multi-hop foundational gap
# --------------------------------------------------------------------------- #

def test_single_hop_foundational_gap():
    concepts = _concepts([("forwarding", "f"), ("data_hazard", "h")])
    states = _states({
        "f": {"status": "WEAK", "mastery": 0.35, "interactionCount": 2},
        "h": {"status": "WEAK", "mastery": 0.45, "interactionCount": 3},
    })
    result = resolve_target(states, concepts, _pre([("h", "f")]))
    assert result["status"] == "TARGET_FOUND"
    assert result["conceptId"] == "h"
    assert result["path"] == ["forwarding", "data_hazard"]
    assert result["rootGap"] is True


def test_multi_hop_foundational_gap_demo():
    concepts = _concepts([
        ("forwarding", "f"),
        ("data_hazard", "h"),
        ("data_dependency", "d"),
        ("pipeline_stages", "p"),
        ("instruction_cycle", "i"),
    ])
    states = _states({
        "f": {"status": "WEAK", "mastery": 0.35, "interactionCount": 2},
        "h": {"status": "WEAK", "mastery": 0.45, "interactionCount": 3},
        "d": {"status": "UNKNOWN", "mastery": 0.0, "interactionCount": 0},
        "p": {"status": "MASTERED", "mastery": 0.9, "interactionCount": 4},
        "i": {"status": "MASTERED", "mastery": 0.95, "interactionCount": 5},
    })
    result = resolve_target(states, concepts, _pre([("p", "d"), ("d", "h"), ("h", "f")]))
    assert result["status"] == "TARGET_FOUND"
    assert result["conceptId"] == "d"
    assert result["path"] == ["forwarding", "data_hazard", "data_dependency"]
    assert result["rootGap"] is True


# --------------------------------------------------------------------------- #
# 7. UNKNOWN upstream becomes target
# --------------------------------------------------------------------------- #

def test_unknown_upstream_becomes_target():
    concepts = _concepts([("forwarding", "f"), ("data_hazard", "h")])
    states = _states({
        "f": {"status": "WEAK", "mastery": 0.3, "interactionCount": 2},
        "h": {"status": "UNKNOWN", "mastery": 0.0, "interactionCount": 0},
    })
    result = resolve_target(states, concepts, _pre([("h", "f")]))
    assert result["status"] == "TARGET_FOUND"
    assert result["conceptId"] == "h"  # UNKNOWN is traversed upstream as a target


# --------------------------------------------------------------------------- #
# Entry-concept resolution (Test yourself selects a concept)
# --------------------------------------------------------------------------- #

def test_entry_concept_resolves_upstream_prerequisite():
    """User selects Forwarding -> resolution walks upstream to Data Dependency."""
    concepts = _concepts([
        ("forwarding", "f"), ("data_hazard", "h"), ("data_dependency", "d"),
    ])
    states = _states({
        "f": {"status": "WEAK", "mastery": 0.4, "interactionCount": 2},
        "h": {"status": "WEAK", "mastery": 0.5, "interactionCount": 3},
        "d": {"status": "UNKNOWN", "mastery": 0.0, "interactionCount": 0},
    })
    result = resolve_target(states, concepts, _pre([("d", "h"), ("h", "f")]),
                            entry_concept_id="f")
    assert result["status"] == "TARGET_FOUND"
    assert result["conceptId"] == "d"
    assert result["path"] == ["forwarding", "data_hazard", "data_dependency"]
    assert result["rootGap"] is True


def test_entry_concept_that_is_the_gap_resolves_itself():
    """Entry concept with mastered/absent prerequisites is itself the target."""
    concepts = _concepts([("forwarding", "f"), ("data_hazard", "h")])
    states = _states({
        "f": {"status": "WEAK", "mastery": 0.3, "interactionCount": 2},
        "h": {"status": "MASTERED", "mastery": 0.9, "interactionCount": 4},
    })
    result = resolve_target(states, concepts, _pre([("h", "f")]),
                            entry_concept_id="f")
    assert result["status"] == "TARGET_FOUND"
    assert result["conceptId"] == "f"
    assert result["rootGap"] is False
    assert result["path"] == ["forwarding"]


def test_entry_concept_missing_from_graph_is_no_target():
    concepts = _concepts([("forwarding", "f")])
    states = _states({"f": {"status": "WEAK", "mastery": 0.3, "interactionCount": 2}})
    result = resolve_target(states, concepts, [], entry_concept_id="ghost")
    assert result["status"] == "NO_TARGET"


def test_async_resolve_forwards_entry_concept(monkeypatch):
    async def fake_model(uid, sid):
        return {"conceptStates": {"f": {"status": "WEAK", "mastery": 0.3, "interactionCount": 2},
                                  "h": {"status": "WEAK", "mastery": 0.5, "interactionCount": 3}}}

    async def fake_concepts(sid):
        return [{"id": "f", "name": "forwarding", "canonicalName": "forwarding"},
                {"id": "h", "name": "data_hazard", "canonicalName": "data_hazard"}]

    async def fake_rels(sid):
        return [{"fromConceptId": "h", "toConceptId": "f", "relationshipType": "PREREQUISITE_OF"}]

    monkeypatch.setattr(learner_service, "get_learner_model", fake_model)
    monkeypatch.setattr(concepts_service, "list_concepts", fake_concepts)
    monkeypatch.setattr(relationships_service, "list_relationships", fake_rels)

    result = _run(tr.resolve_diagnostic_target("u", "s", entry_concept_id="f"))
    assert result["status"] == "TARGET_FOUND"
    assert result["conceptId"] == "h"
    assert result["rootGap"] is True


# --------------------------------------------------------------------------- #
# 8-10. Tie-breaking
# --------------------------------------------------------------------------- #

def test_tie_break_by_mastery():
    concepts = _concepts([("forwarding", "f"), ("b", "b"), ("c", "c")])
    states = _states({
        "f": {"status": "WEAK", "mastery": 0.3, "interactionCount": 2},
        "b": {"status": "WEAK", "mastery": 0.3, "interactionCount": 1},
        "c": {"status": "WEAK", "mastery": 0.2, "interactionCount": 4},
    })
    # f's prerequisites are b and c; both weak. c has lower mastery -> chosen.
    result = resolve_target(states, concepts, _pre([("b", "f"), ("c", "f")]))
    assert result["conceptId"] == "c"


def test_tie_break_by_interaction_count():
    concepts = _concepts([("forwarding", "f"), ("b", "b"), ("c", "c")])
    states = _states({
        "f": {"status": "WEAK", "mastery": 0.3, "interactionCount": 2},
        "b": {"status": "WEAK", "mastery": 0.3, "interactionCount": 4},
        "c": {"status": "WEAK", "mastery": 0.3, "interactionCount": 1},
    })
    result = resolve_target(states, concepts, _pre([("b", "f"), ("c", "f")]))
    assert result["conceptId"] == "c"  # equal mastery -> fewer interactions


def test_tie_break_by_canonical_name():
    concepts = _concepts([("forwarding", "f"), ("alpha", "b"), ("bravo", "c")])
    states = _states({
        "f": {"status": "WEAK", "mastery": 0.3, "interactionCount": 2},
        "b": {"status": "WEAK", "mastery": 0.3, "interactionCount": 1},
        "c": {"status": "WEAK", "mastery": 0.3, "interactionCount": 1},
    })
    result = resolve_target(states, concepts, _pre([("b", "f"), ("c", "f")]))
    assert result["conceptId"] == "b"  # equal mastery+interactions -> canonical alpha


# --------------------------------------------------------------------------- #
# 11. Chain fully mastered above stops recursion
# --------------------------------------------------------------------------- #

def test_recursion_stops_at_first_non_mastered():
    concepts = _concepts([("a", "a"), ("b", "b"), ("c", "c")])
    states = _states({
        "a": {"status": "WEAK", "mastery": 0.3, "interactionCount": 2},
        "b": {"status": "WEAK", "mastery": 0.4, "interactionCount": 1},
        "c": {"status": "MASTERED", "mastery": 0.9, "interactionCount": 5},
    })
    # chain: c -> b -> a
    result = resolve_target(states, concepts, _pre([("c", "b"), ("b", "a")]))
    # a -> b (non-mastered); b -> c (mastered) stops. Target = b.
    assert result["status"] == "TARGET_FOUND"
    assert result["conceptId"] == "b"
    assert result["path"] == ["a", "b"]


# --------------------------------------------------------------------------- #
# 12-13. Async wrapper error handling
# --------------------------------------------------------------------------- #

def test_async_service_failure_is_resolution_error(monkeypatch):
    async def boom(*_args, **_kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(learner_service, "get_learner_model", boom)
    monkeypatch.setattr(concepts_service, "list_concepts", boom)
    monkeypatch.setattr(relationships_service, "list_relationships", boom)

    result = _run(tr.resolve_diagnostic_target("u", "s"))
    assert result["status"] == "RESOLUTION_ERROR"


def test_async_missing_learner_model_is_no_target(monkeypatch):
    async def no_model(*_args, **_kwargs):
        return None

    async def empty(*_args, **_kwargs):
        return []

    monkeypatch.setattr(learner_service, "get_learner_model", no_model)
    monkeypatch.setattr(concepts_service, "list_concepts", empty)
    monkeypatch.setattr(relationships_service, "list_relationships", empty)

    result = _run(tr.resolve_diagnostic_target("u", "s"))
    assert result["status"] == "NO_TARGET"
    assert result["conceptId"] is None


def test_async_missing_learner_model_with_entry_concept_targets_selection(monkeypatch):
    """A fresh user (no learner model) who selects a concept must still be able
    to start a diagnostic — the selected concept becomes the target."""
    async def no_model(*_args, **_kwargs):
        return None

    async def concepts(sid):
        return [{"id": "f", "name": "forwarding", "canonicalName": "forwarding"},
                {"id": "h", "name": "data_hazard", "canonicalName": "data_hazard"}]

    async def rels(sid):
        return []

    monkeypatch.setattr(learner_service, "get_learner_model", no_model)
    monkeypatch.setattr(concepts_service, "list_concepts", concepts)
    monkeypatch.setattr(relationships_service, "list_relationships", rels)

    result = _run(tr.resolve_diagnostic_target("u", "s", entry_concept_id="f"))
    assert result["status"] == "TARGET_FOUND"
    assert result["conceptId"] == "f"
    assert result["rootGap"] is False
    assert result["path"] == ["forwarding"]


def test_async_missing_learner_model_entry_concept_not_found(monkeypatch):
    async def no_model(*_args, **_kwargs):
        return None

    async def concepts(sid):
        return [{"id": "f", "name": "forwarding", "canonicalName": "forwarding"}]

    async def rels(sid):
        return []

    monkeypatch.setattr(learner_service, "get_learner_model", no_model)
    monkeypatch.setattr(concepts_service, "list_concepts", concepts)
    monkeypatch.setattr(relationships_service, "list_relationships", rels)

    result = _run(tr.resolve_diagnostic_target("u", "s", entry_concept_id="ghost"))
    assert result["status"] == "NO_TARGET"


# --------------------------------------------------------------------------- #
# 14. Ordering of candidatesConsidered
# --------------------------------------------------------------------------- #

def test_candidates_considered_ordered():
    concepts = _concepts([("f", "f"), ("h", "h"), ("d", "d")])
    states = _states({
        "f": {"status": "WEAK", "mastery": 0.5, "interactionCount": 2},
        "h": {"status": "WEAK", "mastery": 0.35, "interactionCount": 3},
        "d": {"status": "DEVELOPING", "mastery": 0.6, "interactionCount": 1},
    })
    result = resolve_target(states, concepts, [])
    # ordered by mastery: h (0.35), f (0.5), d (0.6)
    assert result["candidatesConsidered"] == ["h", "f", "d"]


# --------------------------------------------------------------------------- #
# Structural invalid input -> ValueError
# --------------------------------------------------------------------------- #

def test_empty_concepts_raises_value_error():
    with pytest.raises(ValueError):
        resolve_target({}, [], [])
