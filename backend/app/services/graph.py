import re
from dataclasses import dataclass, field

from app.ai.schemas.extraction import KnowledgeExtraction

# Relationship types that impose a directed ordering (and thus must be acyclic).
DIRECTED_TYPES = {"PREREQUISITE_OF", "DEPENDS_ON", "PART_OF", "INSTANCE_OF"}

# Document-furniture words that should never become concepts.
_FURNITURE = {
    "introduction", "overview", "conclusion", "summary", "abstract",
    "references", "bibliography", "table of contents", "contents", "index",
    "appendix", "glossary", "acknowledgments", "notes", "exercise", "exercises",
    "questions", "review questions", "objectives", "learning objectives",
}

_MAX_RELATED_PER_NODE = 8
_MAX_ACRONYM_LEN = 8

_NUMBERED_HEADING = re.compile(r"^\s*\d+(?:\.\d+)*[\.\s:)]*")

# OCR frequently glues a short acronym onto a following descriptive word with no
# space ("C-LOOKscheduling", "SSTF(shortestseektimefirst)algorithm"). When
# concept names differ only by such a descriptor suffix we treat them as the
# same concept. The whitelist keeps this deterministic and conservative: only
# these generic educational descriptor words may be stripped, so unrelated
# acronyms ("net" vs "network") are never merged.
_ACRONYM_SUFFIXES = frozenset(
    w
    for w in [
        "algorithm", "algorithms", "scheduling", "method", "methods",
        "technique", "techniques", "strategy", "strategies", "model", "models",
        "system", "systems", "operation", "operations", "process", "procedure",
        "approach", "structure", "structures", "protocol", "framework",
        "management", "policy", "policies", "mechanism", "mechanisms",
        "service", "services",
    ]
)

# Leading acronym detected in an original (case-preserving) concept name.
_LEADING_ACRONYM = re.compile(r"[^A-Za-z]*([A-Z][A-Z\-]*[A-Z])")


def _clean_enumerated_name(text: str) -> str:
    """Strip a leading numbering/bullet prefix from an enumerated sub-topic."""
    return _NUMBERED_HEADING.sub("", text).strip()


def _singular_plural_variant(key: str) -> str:
    """Return the singular/plural counterpart of a normalized key (best-effort)."""
    return key[:-1] if key.endswith("s") else key + "s"


def _is_reasonable_parent(text: str) -> bool:
    """A parent section is seedable only when its name is a real multi-word
    section title (not a fragment like "Methods" or a diagram label)."""
    if not text:
        return False
    norm = normalize_key(text)
    if not norm or norm in _FURNITURE:
        return False
    return len(norm.split()) >= 2


def _seed_enumerated_topics(concepts: list[PlannedConcept], chunks: list[dict]) -> list[PlannedConcept]:
    """Deterministically add enumerated sub-topics the LLM may have omitted.

    Uses the document heading hierarchy (from each chunk's headingPath) as
    grounded evidence: when a section enumerates several numbered sub-topics
    (e.g. algorithms, file types, directory structures), each is a teachable
    concept belonging to that section. This makes the graph complete and stable
    regardless of LLM extraction variance. Only leaf, numbered sub-topics with
    at least one numbered sibling are seeded; nothing is fabricated.

    The enumerating section itself is also materialised (if not already a
    concept) so seeded sub-topics get a real PART_OF parent instead of being
    dropped as "unknown endpoint" -- this is what lets OCR-recovered document
    hierarchy (whose parent section is not always extracted by the LLM) appear
    in the graph.
    """
    from collections import defaultdict

    parent_children: dict[tuple[str, ...], list[tuple[str, list[int]]]] = defaultdict(list)
    for chunk in chunks:
        path = [str(p) for p in (chunk.get("headingPath") or [])]
        if not path:
            path = [str(chunk.get("sectionTitle") or "untitled")]
        idx = chunk.get("chunkIndex")
        if idx is None:
            continue
        for i in range(1, len(path)):
            parent_children[tuple(path[:i])].append((path[i], [idx]))

    def find_match(name: str) -> PlannedConcept | None:
        key = normalize_key(name)
        for c in concepts + additions:
            if _concept_matches(normalize_key(c.canonical_name), c, key, name):
                return c
        return None

    additions: list[PlannedConcept] = []

    for parent_key, children in parent_children.items():
        numbered = [
            (text, idxs) for text, idxs in children
            if _NUMBERED_HEADING.match(text) and len(text) < 80
        ]
        if len(numbered) < 2:
            continue
        parent_text = parent_key[-1] if parent_key else ""
        if not _is_reasonable_parent(parent_text):
            continue
        # Resolve the parent concept, tolerating singular/plural variants.
        parent = find_match(parent_text)
        if parent is None:
            parent = find_match(_singular_plural_variant(parent_text))
        if parent is None:
            parent = PlannedConcept(
                canonical_name=parent_text,
                name=parent_text,
                description="",
                difficulty=3,
                expected_understanding="",
                common_misconceptions=[],
                source_chunks=[],
                parent_concept=None,
            )
            additions.append(parent)
        parent_name = parent.canonical_name
        for text, idxs in numbered:
            clean = _clean_enumerated_name(text)
            key = normalize_key(clean)
            if not key or key in _FURNITURE:
                continue
            child = find_match(clean)
            if child is not None:
                if not child.parent_concept:
                    child.parent_concept = parent_name
                continue
            additions.append(
                PlannedConcept(
                    canonical_name=clean,
                    name=clean,
                    description="",
                    difficulty=3,
                    expected_understanding="",
                    common_misconceptions=[],
                    source_chunks=list(dict.fromkeys(idxs)),
                    parent_concept=parent_name,
                )
            )

    return concepts + additions


@dataclass
class PlannedConcept:
    canonical_name: str
    name: str
    description: str
    difficulty: int
    expected_understanding: str
    common_misconceptions: list[str] = field(default_factory=list)
    source_chunks: list[int] = field(default_factory=list)
    parent_concept: str | None = None


@dataclass
class PlannedEdge:
    from_canonical: str
    to_canonical: str
    relationship_type: str
    confidence: float
    reason: str = ""
    source_chunks: list[int] = field(default_factory=list)
    dropped: bool = False
    drop_reason: str = ""


@dataclass
class GraphPlan:
    concepts: list[PlannedConcept]
    edges: list[PlannedEdge]
    dropped_edges: list[PlannedEdge] = field(default_factory=list)


def normalize_key(value: str) -> str:
    """Normalize a concept label for comparison: lowercase, drop parentheticals
    and punctuation, collapse whitespace."""
    stripped = re.sub(r"\([^)]*\)", " ", value)
    stripped = re.sub(r"[^a-z0-9]+", " ", stripped.lower()).strip()
    return stripped


def _initials(text: str) -> str:
    return "".join(w[0] for w in text.split() if w)


def _is_acronym(text: str) -> bool:
    return " " not in text and 2 <= len(text) <= _MAX_ACRONYM_LEN and text.isalpha()


def _leading_acronym(name: str) -> str:
    """Lowercased genuine leading acronym of an original concept name, or ''.

    Requires 2+ uppercase letters so normal capitalised words ("File",
    "Directory") are NOT treated as acronyms. Hyphenated acronyms ("C-LOOK",
    "C-SCAN") are handled.
    """
    m = _LEADING_ACRONYM.match(name)
    if not m:
        return ""
    return "".join(ch for ch in m.group(1) if ch.isalpha()).lower()


def _descriptor_ok(remainder: str) -> bool:
    """True when a key remainder is empty or decomposes into descriptor words.

    Greedy longest-match over the whitelist, so glued compounds such as
    'schedulingalgorithm' are recognised as 'scheduling' + 'algorithm'.
    """
    if not remainder:
        return True
    i = 0
    while i < len(remainder):
        for word in sorted(_ACRONYM_SUFFIXES, key=len, reverse=True):
            if remainder.startswith(word, i):
                i += len(word)
                break
        else:
            return False
    return True


def _ocr_same_concept(a_name: str, b_name: str) -> bool:
    """OCR concatenation match: two names are the same concept when they share a
    genuine leading acronym and differ only by an optional descriptor suffix.

    Gated on a real (uppercase) acronym appearing on at least one side, so
    lowercase words ("file" vs "file systems") are never merged.
    """
    ac = _leading_acronym(a_name) or _leading_acronym(b_name)
    if not ac:
        return False
    blob_a = "".join(normalize_key(a_name).split())
    blob_b = "".join(normalize_key(b_name).split())
    if not (blob_a.startswith(ac) and blob_b.startswith(ac)):
        return False
    return _descriptor_ok(blob_a[len(ac):]) and _descriptor_ok(blob_b[len(ac):])


def _concept_matches(existing_key: str, existing: PlannedConcept, key: str, incoming_name: str = "") -> bool:
    """Return True when key denotes the same concept as existing_key."""
    if key == existing_key:
        return True
    # acronym <-> expansion merge (e.g. "fcfs" <-> "first come first serve")
    if _is_acronym(key) and " " in existing_key and _initials(existing_key) == key:
        return True
    if _is_acronym(existing_key) and " " in key and _initials(key) == existing_key:
        return True
    # OCR token-concatenation merge (e.g. "c look" <-> "c lookscheduling",
    # "sstf" <-> "sstfalgorithm"); requires a genuine acronym + descriptor tail.
    if incoming_name and _ocr_same_concept(existing.name, incoming_name):
        return True
    return False


def _merge_into(existing: PlannedConcept, incoming: PlannedConcept) -> None:
    # prefer the expanded, more informative display name; keep the shorter canonical
    if len(incoming.name.split()) > len(existing.name.split()):
        existing.name = incoming.name
        existing.canonical_name = _choose_canonical(existing.canonical_name, incoming.canonical_name)
    existing.description = incoming.description or existing.description
    if incoming.expected_understanding:
        existing.expected_understanding = incoming.expected_understanding
    if incoming.common_misconceptions:
        existing.common_misconceptions = incoming.common_misconceptions
    if incoming.parent_concept:
        existing.parent_concept = incoming.parent_concept
    existing.difficulty = min(existing.difficulty, incoming.difficulty) or existing.difficulty
    existing.source_chunks = list(dict.fromkeys(existing.source_chunks + incoming.source_chunks))


def _choose_canonical(a: str, b: str) -> str:
    # prefer the shorter (usually acronym) canonical label
    ka, kb = normalize_key(a), normalize_key(b)
    return a if len(ka.split()) <= len(kb.split()) else b


def _drop_furniture(concepts: list[PlannedConcept]) -> list[PlannedConcept]:
    kept: list[PlannedConcept] = []
    for c in concepts:
        if normalize_key(c.canonical_name) in _FURNITURE:
            continue
        if not c.name.strip() or not c.canonical_name.strip():
            continue
        kept.append(c)
    return kept


def _dedup_concepts(extraction: KnowledgeExtraction) -> list[PlannedConcept]:
    seen: list[PlannedConcept] = []
    for concept in extraction.concepts:
        if not concept.name.strip() or not concept.canonical_name.strip():
            continue
        key = normalize_key(concept.canonical_name)
        if not key:
            continue
        incoming = PlannedConcept(
            canonical_name=concept.canonical_name.strip(),
            name=concept.name.strip(),
            description=concept.description,
            difficulty=concept.difficulty,
            expected_understanding=concept.expected_understanding,
            common_misconceptions=list(concept.common_misconceptions),
            source_chunks=list(concept.source_chunks),
            parent_concept=concept.parent_concept,
        )
        merged = False
        for i, existing in enumerate(seen):
            if _concept_matches(normalize_key(existing.canonical_name), existing, key, concept.name):
                _merge_into(existing, incoming)
                merged = True
                break
        if not merged:
            seen.append(incoming)
    return _drop_furniture(seen)


def _has_cycle(nodes: set[str], edges: list[tuple[str, str]]) -> bool:
    adjacency: dict[str, list[str]] = {n: [] for n in nodes}
    for frm, to in edges:
        adjacency.setdefault(frm, []).append(to)
    state: dict[str, int] = {}

    def dfs(node: str) -> bool:
        state[node] = 1
        for neighbor in adjacency.get(node, []):
            neighbor_state = state.get(neighbor, 0)
            if neighbor_state == 1:
                return True
            if neighbor_state == 0 and dfs(neighbor):
                return True
        state[node] = 2
        return False

    for node in nodes:
        if state.get(node, 0) == 0 and dfs(node):
            return True
    return False


def build_graph(extraction: KnowledgeExtraction, chunks: list[dict] | None = None) -> GraphPlan:
    """Deterministically build and validate a concept graph from LLM output.

    - normalizes + dedupes concepts (case, punctuation, parentheticals, acronyms)
    - seeds enumerated sub-topics missing from the LLM output (document structure)
    - drops document-furniture and malformed concepts
    - turns parent_concept into PART_OF (hierarchy) edges
    - drops edges referencing unknown concepts, self-loops, and duplicates
    - caps dense RELATED_TO connections for readability
    - drops directed edges that would create a cycle (DFS)
    """
    concepts = _dedup_concepts(extraction)
    if chunks:
        concepts = _seed_enumerated_topics(concepts, chunks)
    concepts = _drop_furniture(concepts)
    # Map normalized key -> persisted canonical_name. Edge endpoints are matched
    # on normalized keys (so "direct_access" == "direct access") but emitted with
    # the canonical names so they resolve to concept IDs on persistence.
    norm_to_canon: dict[str, str] = {}
    for c in concepts:
        key = normalize_key(c.canonical_name)
        norm_to_canon.setdefault(key, c.canonical_name)
    node_set = set(norm_to_canon)

    edges: list[PlannedEdge] = []
    seen_pairs: set[tuple[str, str, str]] = set()

    def add_edge(
        frm: str,
        to: str,
        rtype: str,
        confidence: float,
        reason: str = "",
        source_chunks: list[int] | None = None,
    ):
        fk, tk = normalize_key(frm), normalize_key(to)
        if fk not in node_set or tk not in node_set:
            edges.append(PlannedEdge(frm, to, rtype, confidence, reason,
                                     source_chunks or [], dropped=True,
                                     drop_reason="unknown concept endpoint"))
            return
        canon_f, canon_t = norm_to_canon[fk], norm_to_canon[tk]
        if canon_f == canon_t:
            edges.append(PlannedEdge(frm, to, rtype, confidence, reason,
                                     source_chunks or [], dropped=True,
                                     drop_reason="self-loop"))
            return
        if (fk, tk, rtype) in seen_pairs:
            edges.append(PlannedEdge(frm, to, rtype, confidence, reason,
                                     source_chunks or [], dropped=True,
                                     drop_reason="duplicate"))
            return
        seen_pairs.add((fk, tk, rtype))
        edges.append(PlannedEdge(canon_f, canon_t, rtype, confidence, reason,
                                 source_chunks or []))

    # 1. Hierarchy edges from parent_concept.
    for concept in concepts:
        if not concept.parent_concept:
            continue
        parent_key = normalize_key(concept.parent_concept)
        if parent_key not in node_set:
            parent_key = _singular_plural_variant(parent_key)
        if parent_key not in node_set or parent_key == normalize_key(concept.canonical_name):
            continue
        add_edge(concept.canonical_name, norm_to_canon[parent_key], "PART_OF",
                 0.9, "Concept belongs to this section/topic (document hierarchy)",
                 concept.source_chunks)

    # 2. Explicit relationships from the LLM.
    for relationship in extraction.relationships:
        add_edge(relationship.from_concept, relationship.to_concept,
                 relationship.relationship_type, relationship.confidence,
                 relationship.reason, list(relationship.source_chunks))

    # 3. Cap dense RELATED_TO connections per node for readability.
    edges = _cap_related(edges)

    # 4. Cycle check over directed ordering edges.
    kept_directed: list[tuple[str, str]] = []
    dropped_edges: list[PlannedEdge] = []
    for edge in edges:
        if edge.dropped:
            dropped_edges.append(edge)
            continue
        if edge.relationship_type in DIRECTED_TYPES:
            candidate = kept_directed + [(edge.from_canonical, edge.to_canonical)]
            if _has_cycle(node_set, candidate):
                edge.dropped = True
                edge.drop_reason = "introduces a cycle"
                dropped_edges.append(edge)
                continue
            kept_directed.append((edge.from_canonical, edge.to_canonical))

    plan_edges = [e for e in edges if not e.dropped]
    return GraphPlan(concepts=concepts, edges=plan_edges, dropped_edges=dropped_edges)


def _cap_related(edges: list[PlannedEdge]) -> list[PlannedEdge]:
    from collections import defaultdict

    counts: dict[str, list[PlannedEdge]] = defaultdict(list)
    for edge in edges:
        if not edge.dropped:
            counts[edge.from_canonical].append(edge)
            counts[edge.to_canonical].append(edge)

    over: set[int] = set()
    for node, node_edges in counts.items():
        related = [e for e in node_edges if e.relationship_type == "RELATED_TO"]
        if len(related) > _MAX_RELATED_PER_NODE:
            ordered = sorted(related, key=lambda e: e.confidence, reverse=True)
            for surplus in ordered[_MAX_RELATED_PER_NODE:]:
                surplus.dropped = True
                surplus.drop_reason = "dense RELATED_TO (readability)"
                over.add(id(surplus))
    return edges