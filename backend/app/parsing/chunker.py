import re
from dataclasses import dataclass, field

from app.parsing.cleaning import clean_page_text, strip_leading_glyphs
from app.parsing.pdf import PageText

DEFAULT_MAX_CHARS = 1200
DEFAULT_OVERLAP_CHARS = 150

_HEADING_MAX_LEN = 60
_HEADING_HINT = re.compile(r"^\d+(\.\d+)*[)\s:.\-]|^[A-Z][A-Za-z ]{2,}:?$")
_SENTENCE_END = re.compile(r"[.!?]$")
_NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)")


@dataclass
class ExtractedChunk:
    chunk_index: int
    text: str
    page_number: int
    section_title: str | None = None
    heading_path: list[str] = field(default_factory=list)


def _looks_like_heading(text: str) -> bool:
    stripped = strip_leading_glyphs(text).strip()
    if not stripped or len(stripped) > _HEADING_MAX_LEN:
        return False
    if _SENTENCE_END.search(stripped):
        return False
    if "\n" in stripped:
        return False
    return bool(_HEADING_HINT.match(stripped))


def _split_oversized(text: str, max_chars: int) -> list[str]:
    tokens = text.split()
    pieces: list[str] = []
    buf = ""
    for token in tokens:
        if buf and len(buf) + 1 + len(token) > max_chars:
            pieces.append(buf)
            buf = token
        else:
            buf = f"{buf} {token}".strip()
    if buf:
        pieces.append(buf)
    return pieces or [text]


def _normalize_heading(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", strip_leading_glyphs(text).strip().lower()).strip()


def _level_for(heading_text: str, page_headings, stack: list[tuple[int, str]]) -> int:
    """Resolve a heading's absolute level.

    Font-size detected headings (pdf.py) are authoritative for unnumbered
    headings. For numbered headings we prefer document-structure logic so that
    sub-topics stay children of their section:

    - "N.M" nests one level under the "N." parent already on the stack.
    - A bare "N." item becomes a child of the deepest unnumbered section
      (a section that enumerates its sub-topics), so pages like
      "3.SCAN"/"4.C-SCAN" stay under "Disk Scheduling Algorithms".
    """
    target = _normalize_heading(heading_text)
    font_level = None
    for heading in page_headings:
        if _normalize_heading(heading.text) == target:
            font_level = heading.level
            break
    m = _NUMBERED.match(strip_leading_glyphs(heading_text).strip())
    if m:
        numbers = m.group(1).split(".")
        if len(numbers) > 1:
            prefix = numbers[0]
            for lvl, t in reversed(stack):
                tm = _NUMBERED.match(strip_leading_glyphs(t).strip())
                if tm and tm.group(1).split(".")[0] == prefix:
                    return lvl + 1
        unnumbered = [lvl for lvl, t in stack if not _NUMBERED.match(strip_leading_glyphs(t).strip())]
        if unnumbered:
            return max(unnumbered) + 1
        return font_level if font_level is not None else 1
    return font_level if font_level is not None else 2


def chunk_document(
    pages: list[PageText],
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[ExtractedChunk]:
    """Split cleaned page text into semantic chunks.

    Headings (detected by font size/weight in pdf.py, plus a conservative
    short-line heuristic) are treated as section boundaries and tracked as a
    hierarchy, so each chunk carries a heading_path like ["File Systems",
    "Directory Structure"]. Body text is grouped into chunks up to max_chars
    with a small overlap tail. Only headings actually introduced on a page are
    kept on the stack; bullets are stripped; page numbers are per-chunk.
    """
    chunks: list[ExtractedChunk] = []
    heading_stack: list[tuple[int, str]] = []
    current_heading: str | None = None

    chunk_paras: list[str] = []
    chunk_len = 0
    has_new = False
    current_page: int | None = None

    def flush_chunk():
        nonlocal chunk_paras, chunk_len, has_new, current_page
        if not chunk_paras or not has_new:
            return
        chunks.append(
            ExtractedChunk(
                chunk_index=len(chunks),
                text="\n\n".join(chunk_paras),
                page_number=current_page or 1,
                section_title=current_heading,
                heading_path=[h for _, h in heading_stack],
            )
        )
        tail: list[str] = []
        tail_len = 0
        for para in reversed(chunk_paras):
            if tail_len + len(para) > overlap_chars:
                break
            tail.insert(0, para)
            tail_len += len(para)
        chunk_paras = list(tail)
        chunk_len = tail_len
        has_new = False
        current_page = None

    def add_piece(text: str, page_number: int):
        nonlocal chunk_paras, chunk_len, has_new, current_page
        if chunk_len + len(text) > max_chars and chunk_paras:
            flush_chunk()
        if current_page is None:
            current_page = page_number
        chunk_paras.append(text)
        chunk_len += len(text)
        has_new = True

    def add_para(text: str, page_number: int):
        if len(text) > max_chars:
            for piece in _split_oversized(text, max_chars):
                add_piece(piece, page_number)
        else:
            add_piece(text, page_number)

    def push_heading(text: str, level: int):
        nonlocal heading_stack, current_heading
        flush_chunk()
        clean = strip_leading_glyphs(text).strip()
        norm = _normalize_heading(clean)
        # collapse near-duplicate headings (e.g. "1. Sequential Access" vs
        # "1.Sequential Access:") instead of stacking both.
        if heading_stack and _normalize_heading(heading_stack[-1][1]) == norm:
            heading_stack[-1] = (level, clean)
        else:
            heading_stack = [(lvl, t) for lvl, t in heading_stack if lvl < level]
            heading_stack.append((level, clean))
        current_heading = clean

    for page in pages:
        cleaned = clean_page_text(page.text)
        if not cleaned:
            continue
        lookup = {_normalize_heading(h.text): h.level for h in page.headings}
        para_lines: list[str] = []
        page_had_body = False
        page_heading_captures: list[tuple[str, list[str]]] = []
        for raw in cleaned.split("\n"):
            line = strip_leading_glyphs(raw).strip()
            if not line:
                if para_lines:
                    add_para(" ".join(para_lines), page.page_number)
                    page_had_body = True
                    para_lines = []
                continue
            norm = _normalize_heading(line)
            level = lookup.get(norm)
            is_heading = level is not None or (
                _looks_like_heading(line) and len(line) <= _HEADING_MAX_LEN
            )
            if is_heading:
                if para_lines:
                    add_para(" ".join(para_lines), page.page_number)
                    page_had_body = True
                    para_lines = []
                level = _level_for(line, page.headings, heading_stack)
                push_heading(line, level)
                # capture for image-only sections (heading but no body on page)
                if not page_heading_captures or _normalize_heading(
                    page_heading_captures[-1][0]
                ) != _normalize_heading(current_heading or ""):
                    page_heading_captures.append(
                        (current_heading or "", [h for _, h in heading_stack])
                    )
            else:
                para_lines.append(line)
        if para_lines:
            add_para(" ".join(para_lines), page.page_number)
            page_had_body = True
        # A section whose content is entirely images/tables still has headings;
        # surface them as topic chunks so the structure is visible to extraction.
        if not page_had_body:
            for clean, path in page_heading_captures:
                chunks.append(
                    ExtractedChunk(
                        chunk_index=len(chunks),
                        text=clean,
                        page_number=page.page_number,
                        section_title=clean,
                        heading_path=path,
                    )
                )
        else:
            page_heading_captures.clear()

    flush_chunk()
    return chunks