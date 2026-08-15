import pytest
from pydantic import ValidationError

from app.ai.schemas.extraction import ConceptOut, KnowledgeExtraction, RelationshipOut
from app.services.graph import build_graph


def _extraction(concepts, relationships):
    return KnowledgeExtraction(
        concepts=[ConceptOut(**c) for c in concepts],
        relationships=[RelationshipOut(**r) for r in relationships],
    )


def _names(plan):
    return {c.canonical_name for c in plan.concepts}


def _edges(plan, rtype):
    return {
        (e.from_canonical, e.to_canonical)
        for e in plan.edges
        if e.relationship_type == rtype
    }


def test_duplicate_concepts_normalized_acronym_and_expansion():
    ex = _extraction(
        [
            {"name": "FCFS", "canonical_name": "FCFS"},
            {"name": "First Come First Serve", "canonical_name": "first come first serve"},
            {"name": "FCFS (First Come First Serve)", "canonical_name": "FCFS (First Come First Serve)"},
        ],
        [],
    )
    plan = build_graph(ex)
    assert len(plan.concepts) == 1
    assert plan.concepts[0].canonical_name == "FCFS"
    assert "First Come First Serve" in plan.concepts[0].name


def test_hierarchy_preserved_via_parent_concept():
    ex = _extraction(
        [
            {"name": "File Systems", "canonical_name": "file systems"},
            {"name": "File", "canonical_name": "file", "parent_concept": "file systems"},
            {"name": "Directory Structure", "canonical_name": "directory structure", "parent_concept": "file systems"},
            {"name": "Disk Scheduling", "canonical_name": "disk scheduling"},
            {"name": "FCFS", "canonical_name": "fcfs", "parent_concept": "disk scheduling"},
        ],
        [],
    )
    plan = build_graph(ex)
    part_of = _edges(plan, "PART_OF")
    assert ("file", "file systems") in part_of
    assert ("directory structure", "file systems") in part_of
    assert ("fcfs", "disk scheduling") in part_of
    # unrelated cross-section concepts must not be connected
    assert ("fcfs", "directory structure") not in part_of
    assert ("file", "disk scheduling") not in part_of


def test_unrelated_concepts_are_not_connected():
    ex = _extraction(
        [
            {"name": "File", "canonical_name": "file", "parent_concept": "file systems"},
            {"name": "File Systems", "canonical_name": "file systems"},
            {"name": "FCFS", "canonical_name": "fcfs", "parent_concept": "disk scheduling"},
            {"name": "Disk Scheduling", "canonical_name": "disk scheduling"},
        ],
        [],
    )
    plan = build_graph(ex)
    pairs = {(e.from_canonical, e.to_canonical) for e in plan.edges}
    # only the two PART_OF hierarchy edges exist; nothing between file and fcfs
    assert ("file", "fcfs") not in pairs
    assert ("fcfs", "file") not in pairs
    assert len(plan.edges) == 2


def test_self_and_duplicate_relationships_rejected():
    ex = _extraction(
        [
            {"name": "A", "canonical_name": "a"},
            {"name": "B", "canonical_name": "b"},
        ],
        [
            {"from_concept": "a", "to_concept": "a", "relationship_type": "INSTANCE_OF"},
            {"from_concept": "a", "to_concept": "b", "relationship_type": "RELATED_TO"},
            {"from_concept": "a", "to_concept": "b", "relationship_type": "RELATED_TO"},
        ],
    )
    plan = build_graph(ex)
    assert len(plan.edges) == 1
    assert any(e.drop_reason == "self-loop" for e in plan.dropped_edges)
    assert any(e.drop_reason == "duplicate" for e in plan.dropped_edges)


def test_malformed_and_furniture_concepts_rejected():
    # empty names are already blocked by schema validation; verify furniture is filtered here
    ex = _extraction(
        [
            {"name": "Introduction", "canonical_name": "Introduction"},
            {"name": "Summary", "canonical_name": "Summary"},
            {"name": "References", "canonical_name": "references"},
            {"name": "File Systems", "canonical_name": "file systems"},
        ],
        [],
    )
    plan = build_graph(ex)
    names = _names(plan)
    assert "file systems" in names
    assert {"introduction", "summary", "references"} & names == set()


def test_empty_concept_name_rejected_by_schema():
    with pytest.raises(ValidationError):
        ConceptOut(name="", canonical_name="")


def test_relationship_types_restricted():
    with pytest.raises(ValidationError):
        RelationshipOut(
            from_concept="a", to_concept="b",
            relationship_type="IS_FRIEND_OF",
        )


def test_relationship_types_accept_all_controlled_values():
    for rtype in ["PART_OF", "INSTANCE_OF", "DEPENDS_ON",
                  "PREREQUISITE_OF", "CONTRASTS_WITH", "RELATED_TO"]:
        RelationshipOut(from_concept="a", to_concept="b", relationship_type=rtype)


def test_evidence_source_chunks_preserved():
    ex = _extraction(
        [
            {"name": "File", "canonical_name": "file", "source_chunks": [1, 3]},
            {"name": "File Systems", "canonical_name": "file systems", "source_chunks": [1]},
        ],
        [
            {"from_concept": "file", "to_concept": "file systems",
             "relationship_type": "PART_OF", "source_chunks": [3], "reason": "hierarchy"},
        ],
    )
    plan = build_graph(ex)
    assert plan.concepts[0].source_chunks == [1, 3]
    assert plan.edges[0].source_chunks == [3]
    assert plan.edges[0].reason == "hierarchy"


def test_dense_related_connections_capped_for_readability():
    concepts = [{"name": "A", "canonical_name": "a"}] + [
        {"name": f"N{i}", "canonical_name": f"n{i}"} for i in range(12)
    ]
    rels = [
        {"from_concept": "a", "to_concept": f"n{i}",
         "relationship_type": "RELATED_TO", "confidence": 0.5}
        for i in range(12)
    ]
    plan = build_graph(_extraction(concepts, rels))
    related_a = [e for e in plan.edges if e.from_canonical == "a" and e.relationship_type == "RELATED_TO"]
    assert len(related_a) <= 8


def test_edges_resolve_underscore_canonical_names():
    # Regression: canonical names may use underscores (e.g. "direct_access").
    # Edge endpoints must still match the concepts and NOT be dropped.
    ex = _extraction(
        [
            {"name": "File Access Methods", "canonical_name": "file_access_methods"},
            {"name": "Sequential Access", "canonical_name": "sequential_access"},
            {"name": "Direct Access", "canonical_name": "direct_access"},
        ],
        [
            {"from_concept": "sequential_access", "to_concept": "file_access_methods",
             "relationship_type": "PART_OF", "confidence": 0.9},
            {"from_concept": "direct_access", "to_concept": "file_access_methods",
             "relationship_type": "PART_OF", "confidence": 0.9},
        ],
    )
    plan = build_graph(ex)
    part_of = {(e.from_canonical, e.to_canonical) for e in plan.edges}
    assert ("sequential_access", "file_access_methods") in part_of
    assert ("direct_access", "file_access_methods") in part_of
    assert not plan.dropped_edges


def test_seeds_missing_enumerated_subtopics_from_structure():
    # LLM omits LOOK/C-LOOK/C-SCAN; the document heading hierarchy enumerates
    # them under "Disk Scheduling Algorithms", so they must be seeded generically.
    ex = _extraction(
        [
            {"name": "Disk Scheduling Algorithms", "canonical_name": "disk scheduling algorithms"},
            {"name": "FCFS (First Come First Serve)", "canonical_name": "fcfs"},
        ],
        [],
    )
    chunks = [
        {"chunkIndex": 0, "headingPath": ["Disk Scheduling Algorithms"], "text": "intro"},
        {"chunkIndex": 1, "headingPath": ["Disk Scheduling Algorithms", "1. FCFS"], "text": "fcfs body"},
        {"chunkIndex": 2, "headingPath": ["Disk Scheduling Algorithms", "2. SSTF"], "text": "sstf body"},
        {"chunkIndex": 3, "headingPath": ["Disk Scheduling Algorithms", "3. SCAN"], "text": "scan body"},
        {"chunkIndex": 4, "headingPath": ["Disk Scheduling Algorithms", "4. C-SCAN"], "text": "C-SCAN"},
        {"chunkIndex": 5, "headingPath": ["Disk Scheduling Algorithms", "5. LOOK"], "text": "look body"},
        {"chunkIndex": 6, "headingPath": ["Disk Scheduling Algorithms", "6. C-LOOK"], "text": "c-look body"},
    ]
    plan = build_graph(ex, chunks=chunks)
    names = _names(plan)
    for expected in ["SSTF", "SCAN", "C-SCAN", "LOOK", "C-LOOK"]:
        assert expected in names, f"missing seeded concept {expected}"
    # seeded topics get a PART_OF edge to the enumerating section
    part_of = _edges(plan, "PART_OF")
    assert ("C-LOOK", "disk scheduling algorithms") in part_of
    assert ("LOOK", "disk scheduling algorithms") in part_of


def test_seeding_does_not_seed_isolated_headings():
    # A lone numbered heading (no enumerated siblings) must NOT be seeded.
    ex = _extraction(
        [
            {"name": "File Access Methods", "canonical_name": "file access methods"},
        ],
        [],
    )
    chunks = [
        {"chunkIndex": 0, "headingPath": ["File Access Methods"], "text": "intro"},
        {"chunkIndex": 1, "headingPath": ["File Access Methods", "1. Sequential Access"], "text": "seq"},
    ]
    plan = build_graph(ex, chunks=chunks)
    names = _names(plan)
    assert "sequential access" not in names


def test_parent_resolution_tolerates_singular_plural():
    # The seeded parent "Directory Structures" (plural) must resolve to the
    # existing concept "directory_structure" (singular).
    ex = _extraction(
        [
            {"name": "Directory Structure", "canonical_name": "directory_structure"},
        ],
        [],
    )
    chunks = [
        {"chunkIndex": 0, "headingPath": ["Directory Structures"], "text": "intro"},
        {"chunkIndex": 1, "headingPath": ["Directory Structures", "1. Single Level Directory"], "text": "s"},
        {"chunkIndex": 2, "headingPath": ["Directory Structures", "2. Acyclic Graph Directory"], "text": "a"},
    ]
    plan = build_graph(ex, chunks=chunks)
    part_of = _edges(plan, "PART_OF")
    assert ("Acyclic Graph Directory", "directory_structure") in part_of


def test_near_variant_spelling_deduplicated():
    # OCR/LLM misspelling "Directory" as "Director" must collapse to one concept,
    # and the more-evidenced (correct) spelling should win as the canonical name.
    ex = _extraction(
        [
            {"name": "Acyclic Graph Directory", "canonical_name": "acyclic graph directory",
             "source_chunks": [1, 2]},
            {"name": "Acyclic Graph Director", "canonical_name": "acyclic graph director",
             "source_chunks": [1]},
        ],
        [],
    )
    plan = build_graph(ex)
    assert len(plan.concepts) == 1
    assert plan.concepts[0].canonical_name == "acyclic graph directory"
    assert plan.concepts[0].source_chunks == [1, 2]


def test_near_variant_does_not_merge_unrelated_one_token():
    # A single differing token that is NOT a near spelling variant must stay separate.
    ex = _extraction(
        [
            {"name": "Binary Search", "canonical_name": "binary search"},
            {"name": "Binary Tree", "canonical_name": "binary tree"},
        ],
        [],
    )
    plan = build_graph(ex)
    assert len(plan.concepts) == 2


def test_near_variant_ignores_single_word_names():
    # Single-word concepts are never merged by the near-variant rule.
    ex = _extraction(
        [
            {"name": "Cache", "canonical_name": "cache"},
            {"name": "Cachet", "canonical_name": "cachet"},
        ],
        [],
    )
    plan = build_graph(ex)
    assert len(plan.concepts) == 2


def test_drops_single_word_prefix_fragment():
    # "Directory" is a fragment beside "Directory Structures" -> dropped generically.
    ex = _extraction(
        [
            {"name": "Directory", "canonical_name": "directory", "source_chunks": [1]},
            {"name": "Directory Structures", "canonical_name": "directory structures",
             "source_chunks": [1, 2, 3, 4, 5, 6, 7, 8, 9]},
        ],
        [],
    )
    plan = build_graph(ex)
    names = _names(plan)
    assert "directory structures" in names
    assert "directory" not in names


def test_prefix_fragment_preserved_when_it_is_a_parent():
    # "File" owns a child so it is a genuine top-level concept -> never dropped.
    ex = _extraction(
        [
            {"name": "File", "canonical_name": "file", "source_chunks": [1]},
            {"name": "File Systems", "canonical_name": "file systems", "source_chunks": [2, 3]},
            {"name": "File Types", "canonical_name": "file types", "source_chunks": [4],
             "parent_concept": "file"},
        ],
        [],
    )
    plan = build_graph(ex)
    assert "file" in _names(plan)
    assert "file systems" in _names(plan)
    assert len(plan.concepts) == 3


def test_prefix_logic_never_drops_multiword_topics():
    # Multi-word topics are never treated as fragments.
    ex = _extraction(
        [
            {"name": "Disk Scheduling", "canonical_name": "disk scheduling", "source_chunks": [1]},
            {"name": "Disk Scheduling Algorithms", "canonical_name": "disk scheduling algorithms",
             "source_chunks": [2]},
        ],
        [],
    )
    plan = build_graph(ex)
    assert len(plan.concepts) == 2
    assert "disk scheduling" in _names(plan)


def test_redundant_part_of_collapsed_with_instance_of():
    # When the same ordered pair has both, keep the more specific INSTANCE_OF and
    # drop the subsumed PART_OF (reduces graph edge noise for readability).
    ex = _extraction(
        [
            {"name": "FCFS", "canonical_name": "fcfs"},
            {"name": "Disk Scheduling Algorithms", "canonical_name": "disk scheduling algorithms"},
        ],
        [
            {"from_concept": "fcfs", "to_concept": "disk scheduling algorithms",
             "relationship_type": "PART_OF", "confidence": 0.9},
            {"from_concept": "fcfs", "to_concept": "disk scheduling algorithms",
             "relationship_type": "INSTANCE_OF", "confidence": 0.9},
        ],
    )
    plan = build_graph(ex)
    assert len(_edges(plan, "INSTANCE_OF")) == 1
    assert len(_edges(plan, "PART_OF")) == 0
    assert any(e.drop_reason == "redundant with INSTANCE_OF on same pair"
               for e in plan.dropped_edges)


def test_redundant_collapse_keeps_part_of_without_instance_of():
    # A PART_OF edge with no matching INSTANCE_OF is unaffected.
    ex = _extraction(
        [
            {"name": "FCFS", "canonical_name": "fcfs"},
            {"name": "Disk Scheduling", "canonical_name": "disk scheduling"},
        ],
        [{"from_concept": "fcfs", "to_concept": "disk scheduling",
          "relationship_type": "PART_OF", "confidence": 0.9}],
    )
    plan = build_graph(ex)
    assert len(_edges(plan, "PART_OF")) == 1
    assert not plan.dropped_edges


def test_metadata_noise_concepts_rejected():
    # Cover-page administrative metadata must never become concepts.
    ex = _extraction(
        [
            {"name": "Course Outcomes", "canonical_name": "course outcomes"},
            {"name": "CO-PO Mapping", "canonical_name": "co-po mapping"},
            {"name": "Syllabus", "canonical_name": "syllabus"},
            {"name": "File Systems", "canonical_name": "file systems"},
        ],
        [],
    )
    plan = build_graph(ex)
    names = _names(plan)
    assert "file systems" in names
    assert {"course outcomes", "co-po mapping", "syllabus"} & names == set()