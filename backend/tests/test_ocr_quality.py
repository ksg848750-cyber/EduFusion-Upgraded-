"""Regression tests for OCR-aware concept normalization and OCR hierarchy.

Issue 1 - OCR token concatenation must not create duplicate concepts
  ("C-LOOKscheduling" vs "c_look", "SSTF(shortestseektimefirst)algorithm" vs
  "sstf"), but genuinely different concepts must NOT be merged.

Issue 2 - a scanned page's clear numbered heading/subsection structure must be
  preserved enough for the existing chunker and graph builder to reconstruct
  hierarchy (e.g. "Disk Scheduling Algorithms" -> the 6 disk algorithms).

Uses only generic examples; nothing is hardcoded for any specific subject.
"""

import pytest

from app.ai.schemas.extraction import ConceptOut, KnowledgeExtraction
from app.parsing.chunker import chunk_document
from app.parsing.pdf import PageText
from app.services.graph import build_graph


def _extraction(concepts, relationships=None):
    return KnowledgeExtraction(
        concepts=[ConceptOut(**c) for c in concepts],
        relationships=[RelationshipOut(**r) for r in (relationships or [])],
    )


def _names(plan):
    return {c.canonical_name for c in plan.concepts}


def _edges(plan, rtype):
    return {
        (e.from_canonical, e.to_canonical)
        for e in plan.edges
        if e.relationship_type == rtype
    }


from app.ai.schemas.extraction import RelationshipOut  # noqa: E402


# --- Issue 1: OCR concatenation normalization -------------------------------

@pytest.mark.parametrize("acronym,concatenated", [
    ("c_look", "C-LOOKscheduling"),
    ("sstf", "SSTF(shortestseektimefirst)algorithm"),
    ("look", "LOOK Scheduling"),
    ("scan", "SCAN scheduling"),
    ("c_scan", "C-SCAN scheduling"),
    ("fcfs", "FCFS scheduling algorithm"),
    ("clook", "C-LOOK scheduling"),
])
def test_ocr_concatenated_acronym_and_word_merge(acronym, concatenated):
    plan = build_graph(_extraction([
        {"name": acronym, "canonical_name": acronym},
        {"name": concatenated, "canonical_name": concatenated},
    ]))
    assert len(plan.concepts) == 1
    assert plan.concepts[0].canonical_name in {acronym, concatenated}


def test_ocr_acronym_parenthetical_expansion_merge():
    plan = build_graph(_extraction([
        {"name": "sstf", "canonical_name": "sstf"},
        {"name": "SSTF (Shortest Seek Time First)", "canonical_name": "SSTF (Shortest Seek Time First)"},
    ]))
    assert len(plan.concepts) == 1


def test_legitimately_different_concepts_not_merged():
    plan = build_graph(_extraction([
        {"name": "file", "canonical_name": "file"},
        {"name": "File Systems", "canonical_name": "file systems"},
        {"name": "net", "canonical_name": "net"},
        {"name": "Network", "canonical_name": "network"},
        {"name": "core", "canonical_name": "core"},
        {"name": "Core Scheduling", "canonical_name": "core scheduling"},
    ]))
    # "file" and "file systems" are distinct; "net" and "network" are distinct.
    assert len(plan.concepts) == 6


def test_ocr_restore_spacing_glued_acronym():
    from app.parsing.ocr import _restore_ocr_spacing

    assert "C-LOOK scheduling" in _restore_ocr_spacing("C-LOOKscheduling")
    assert "algorithm" in _restore_ocr_spacing("SSTF(shortestseektimefirst)algorithm")
    # normal words must be left alone
    assert _restore_ocr_spacing("MacBook") == "MacBook"
    assert _restore_ocr_spacing("DVDs") == "DVDs"


def test_ocr_restore_spacing_keeps_document_text_intact():
    from app.parsing.ocr import _restore_ocr_spacing

    body = "This is a normal paragraph with the FCFS scheduling algorithm."
    out = _restore_ocr_spacing(body)
    assert "FCFS scheduling" in out
    assert "normal paragraph" in out


# --- Issue 2: OCR hierarchy recovery ----------------------------------------

def test_chunker_recovers_numbered_heading_hierarchy_from_ocr_lines():
    # A scanned page whose OCR text has a clear section heading + numbered
    # sub-headings must nest the sub-headings under the section.
    page = PageText(
        page_number=1,
        text="Disk Scheduling Algorithms\n"
             "1. FCFS (First Come First Serve)\n"
             "2. SSTF (Shortest Seek Time First)\n"
             "3. SCAN\n"
             "4. C-SCAN\n"
             "5. LOOK\n"
             "6. C-LOOK",
        ocr_used=True,
    )
    chunks = chunk_document([page])
    paths = [c.heading_path for c in chunks]
    # every numbered algorithm nests under the section
    for p in paths:
        if p:
            assert p[0] == "Disk Scheduling Algorithms", f"bad path {p}"
    assert any(p[-1] == "6. C-LOOK" for p in paths if p)


def test_ocr_subsection_associated_with_parent_when_evidence_clear():
    plan = build_graph(
        _extraction([{"name": "Disk Scheduling Algorithms", "canonical_name": "disk scheduling algorithms"}]),
        chunks=[
            {"chunkIndex": 0, "headingPath": ["Disk Scheduling Algorithms"], "text": "intro"},
            {"chunkIndex": 1, "headingPath": ["Disk Scheduling Algorithms", "1. FCFS"], "text": "fcfs"},
            {"chunkIndex": 2, "headingPath": ["Disk Scheduling Algorithms", "2. SSTF"], "text": "sstf"},
            {"chunkIndex": 3, "headingPath": ["Disk Scheduling Algorithms", "3. SCAN"], "text": "scan"},
        ],
    )
    part_of = _edges(plan, "PART_OF")
    assert ("FCFS", "disk scheduling algorithms") in part_of
    assert ("SSTF", "disk scheduling algorithms") in part_of
    assert ("SCAN", "disk scheduling algorithms") in part_of


def test_ambiguous_ocr_text_does_not_invent_hierarchy():
    # Isolated single-word OCR fragments must NOT be treated as an enumerating
    # section (no parent seeded, no false PART_OF).
    plan = build_graph(
        _extraction([
            {"name": "Platter", "canonical_name": "platter"},
            {"name": "Sector", "canonical_name": "sector"},
        ]),
        chunks=[
            {"chunkIndex": 0, "headingPath": ["Platter"], "text": "platter"},
            {"chunkIndex": 1, "headingPath": ["Sector"], "text": "sector"},
        ],
    )
    names = _names(plan)
    # single-word sections are not reasonable parents -> no invented parent
    assert "platter" in names
    assert "sector" in names
    part_of = _edges(plan, "PART_OF")
    assert len(part_of) == 0


def test_ocr_diagram_label_is_not_treated_as_heading():
    # A diagram/table caption line must not become a heading that grabs the
    # following numbered algorithm as a child (false hierarchy).
    page = PageText(
        page_number=1,
        text="Number of cylinders moved bythehead\n"
             "1. FCFS\n"
             "2. SSTF",
        ocr_used=True,
    )
    chunks = chunk_document([page])
    for c in chunks:
        for h in c.heading_path:
            assert "cylinders moved" not in h, f"diagram label became heading: {c.heading_path}"


def test_ocr_title_case_section_heading_kept():
    page = PageText(
        page_number=1,
        text="Disk Scheduling Algorithms\n"
             "1. FCFS (First Come First Serve)\n"
             "2. SSTF (Shortest Seek Time First)",
        ocr_used=True,
    )
    chunks = chunk_document([page])
    paths = [c.heading_path for c in chunks if c.heading_path]
    assert any(p[0] == "Disk Scheduling Algorithms" for p in paths)


def test_seeded_parent_resolves_singular_plural_variant():
    plan = build_graph(
        _extraction([{"name": "Directory Structure", "canonical_name": "directory_structure"}]),
        chunks=[
            {"chunkIndex": 0, "headingPath": ["Directory Structures"], "text": "intro"},
            {"chunkIndex": 1, "headingPath": ["Directory Structures", "1. Single Level Directory"], "text": "s"},
            {"chunkIndex": 2, "headingPath": ["Directory Structures", "2. Acyclic Graph Directory"], "text": "a"},
        ],
    )
    part_of = _edges(plan, "PART_OF")
    assert ("Acyclic Graph Directory", "directory_structure") in part_of
    # parent must NOT be duplicated by seeding
    assert _names(plan) == {"directory_structure", "Single Level Directory", "Acyclic Graph Directory"}