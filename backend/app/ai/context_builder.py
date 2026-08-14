from typing import Any

MAX_EXTRACTION_CHARS = 12_000


def _section_label(chunk: dict[str, Any]) -> str:
    path = chunk.get("headingPath") or []
    if path:
        return " / ".join(str(p) for p in path)
    return str(chunk.get("sectionTitle") or "untitled")


def _build_outline(chunks: list[dict[str, Any]]) -> str:
    """Render the document's heading hierarchy as a compact outline.

    Derived from each chunk's heading_path, so image-heavy sections whose body
    is diagrams still appear. Gives the LLM the complete topic list so it does
    not drop enumerated sub-topics that appear only as headings.
    """
    children: dict[tuple[str, ...], list[str]] = {}
    for chunk in chunks:
        path = [str(p) for p in (chunk.get("headingPath") or [])]
        if not path:
            path = [str(chunk.get("sectionTitle") or "untitled")]
        for i, text in enumerate(path):
            parent_key = tuple(path[:i])
            siblings = children.setdefault(parent_key, [])
            if text not in siblings:
                siblings.append(text)

    lines: list[str] = []
    def render(parent_key: tuple[str, ...], depth: int) -> None:
        for text in children.get(parent_key, []):
            lines.append(f"{'  ' * depth}- {text}")
            render(parent_key + (text,), depth + 1)

    render((), 0)
    return "\n".join(lines)


def build_extraction_context(chunks: list[dict[str, Any]]) -> str:
    """Serialize chunks (with full section hierarchy) into a prompt excerpt block.

    Each chunk is labelled by its complete heading path, e.g.
    "Operating Systems / File Systems / Directory Structure", so the LLM can
    respect the document's section hierarchy. A document outline (from the
    heading hierarchy) is prepended so the full topic list is visible. Respects
    a token budget with an even distribution across chunks.
    """
    outline = _build_outline(chunks)
    budget = MAX_EXTRACTION_CHARS
    per_chunk = budget // max(len(chunks), 1)

    parts: list[str] = []
    for idx, chunk in enumerate(chunks):
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        if len(text) > per_chunk:
            text = text[:per_chunk].rstrip() + "…"
        parts.append(f"[{idx + 1}] SECTION: {_section_label(chunk)}\nPAGE: {chunk.get('pageNumber')}\n{text}")

    joined = "\n\n".join(parts) or "(no content)"
    header = f"DOCUMENT OUTLINE:\n{outline}\n\n" if outline else ""
    return (header + joined)[:MAX_EXTRACTION_CHARS]