from app.ai.schemas.extraction import ConceptOut, KnowledgeExtraction, RelationshipOut
from app.services.graph import build_graph


def _extraction(concepts, relationships):
    return KnowledgeExtraction(
        concepts=[ConceptOut(**c) for c in concepts],
        relationships=[RelationshipOut(**r) for r in relationships],
    )


def test_dedup_concepts_by_canonical_name():
    ex = _extraction(
        [
            {"name": "Pipeline", "canonical_name": "Pipeline"},
            {"name": "instruction pipeline", "canonical_name": "pipeline"},
        ],
        [],
    )
    plan = build_graph(ex)
    assert len(plan.concepts) == 1
    assert plan.concepts[0].canonical_name == "Pipeline"


def test_drops_edges_with_unknown_endpoint():
    ex = _extraction(
        [{"name": "A", "canonical_name": "a"}],
        [{"from_concept": "a", "to_concept": "missing", "relationship_type": "RELATED_TO"}],
    )
    plan = build_graph(ex)
    assert len(plan.edges) == 0
    assert len(plan.dropped_edges) == 1
    assert plan.dropped_edges[0].drop_reason == "unknown concept endpoint"


def test_drops_self_loop():
    ex = _extraction(
        [{"name": "A", "canonical_name": "a"}],
        [{"from_concept": "a", "to_concept": "a", "relationship_type": "PART_OF"}],
    )
    plan = build_graph(ex)
    assert len(plan.edges) == 0
    assert plan.dropped_edges[0].drop_reason == "self-loop"


def test_drops_cycle_forming_directed_edge():
    ex = _extraction(
        [
            {"name": "A", "canonical_name": "a"},
            {"name": "B", "canonical_name": "b"},
            {"name": "C", "canonical_name": "c"},
        ],
        [
            {"from_concept": "a", "to_concept": "b", "relationship_type": "PREREQUISITE_OF"},
            {"from_concept": "b", "to_concept": "c", "relationship_type": "PREREQUISITE_OF"},
            {"from_concept": "c", "to_concept": "a", "relationship_type": "PREREQUISITE_OF"},
        ],
    )
    plan = build_graph(ex)
    assert len(plan.edges) == 2  # third would create a->b->c->a cycle
    assert plan.dropped_edges[0].drop_reason == "introduces a cycle"


def test_undirected_edge_is_not_cycle_checked():
    ex = _extraction(
        [
            {"name": "A", "canonical_name": "a"},
            {"name": "B", "canonical_name": "b"},
        ],
        [
            {"from_concept": "a", "to_concept": "b", "relationship_type": "RELATED_TO"},
            {"from_concept": "b", "to_concept": "a", "relationship_type": "CONTRASTS_WITH"},
        ],
    )
    plan = build_graph(ex)
    assert len(plan.edges) == 2


def test_keeps_valid_acyclic_graph():
    ex = _extraction(
        [
            {"name": "A", "canonical_name": "a"},
            {"name": "B", "canonical_name": "b"},
        ],
        [{"from_concept": "a", "to_concept": "b", "relationship_type": "DEPENDS_ON"}],
    )
    plan = build_graph(ex)
    assert len(plan.edges) == 1
    assert len(plan.dropped_edges) == 0
