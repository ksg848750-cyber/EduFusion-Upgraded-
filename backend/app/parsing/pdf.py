import logging
from dataclasses import dataclass, field
import statistics

import pymupdf as fitz  # PyMuPDF

from app.parsing.ocr import OCR_SCALE, OcrEngine, get_ocr_engine, needs_ocr

logger = logging.getLogger(__name__)

_HEADING_MAX_CHARS = 60
_HEADING_MIN_SIZE_RATIO = 1.12
_MAX_HEADING_LEVEL = 4


@dataclass
class Heading:
    level: int
    text: str


@dataclass
class PageText:
    page_number: int
    text: str
    headings: list[Heading] = field(default_factory=list)
    ocr_used: bool = False


def _extract_headings(page) -> list[Heading]:
    """Detect headings from font size/weight via the PDF text layout.

    Level 1 is the largest heading; deeper levels indicate subsections, which
    lets the graph understand the document's section hierarchy. Falls back to
    an empty list when the page has no structured text.
    """
    raw = page.get_text("dict")
    sizes: list[float] = []
    candidates: list[tuple[float, str, bool]] = []
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue
            max_size = max(s.get("size", 0) for s in spans)
            sizes.append(max_size)
            flags = spans[0].get("flags", 0)
            bold = bool(flags & 16)
            if len(text) <= _HEADING_MAX_CHARS and not text.endswith((".", ";", ",", ":")):
                candidates.append((max_size, text, bold))
    if not candidates:
        return []
    body = statistics.median(sizes) if sizes else 11.0
    return _rank_headings(candidates, body)


def _rank_headings(candidates: list[tuple[float, str, bool]], body: float) -> list[Heading]:
    picked = [
        (size, text)
        for size, text, bold in candidates
        if size >= body * _HEADING_MIN_SIZE_RATIO or (bold and len(text) <= 40)
    ]
    # unique sizes sorted descending -> level by rank
    unique_sizes = sorted({s for s, _ in picked}, reverse=True)
    size_rank = {s: i + 1 for i, s in enumerate(unique_sizes)}
    headings: list[Heading] = []
    seen: set[str] = set()
    for size, text in picked:
        if text.isdigit():
            continue
        level = size_rank[size]
        if level > _MAX_HEADING_LEVEL:
            continue
        if text in seen:
            continue
        seen.add(text)
        headings.append(Heading(level=level, text=text))
    return headings


def _render_page_png(page) -> bytes:
    """Render a page to grayscale PNG bytes for OCR input."""
    pix = page.get_pixmap(matrix=fitz.Matrix(OCR_SCALE, OCR_SCALE), colorspace=fitz.csGRAY)
    return pix.tobytes("png")


def _ocr_page(page, ocr: OcrEngine) -> str:
    """OCR a single page; returns recognized text or '' (never raises)."""
    try:
        return ocr.recognize(_render_page_png(page))
    except Exception as exc:  # noqa: BLE001 - a single page must not kill ingestion
        logger.warning("OCR failed on page %s: %s", getattr(page, "number", "?"), exc)
        return ""


def extract_pages(
    content: bytes,
    ocr: OcrEngine | None = None,
    ocr_enabled: bool = True,
) -> list[PageText]:
    """Extract text per page (plus detected headings) from a PDF.

    Uses PyMuPDF selectable text by default. Pages that fail a quality heuristic
    (scanned / image-only / sparse-noisy) are rendered to an image and OCR'd via
    RapidOCR as a fallback. OCR text reuses the same cleaning/chunking pipeline.
    Raises on malformed or non-PDF input.
    """
    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Could not parse PDF: {exc}") from exc

    pages: list[PageText] = []
    try:
        for page_index, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            ocr_used = False
            if ocr_enabled:
                has_image = bool(page.get_images(full=True))
                if needs_ocr(text, has_image):
                    engine = ocr or get_ocr_engine()
                    ocr_text = _ocr_page(page, engine)
                    if ocr_text.strip():
                        ocr_used = True
                        text = ocr_text
            pages.append(
                PageText(
                    page_number=page_index,
                    text=text or "",
                    headings=_extract_headings(page),
                    ocr_used=ocr_used,
                )
            )
    finally:
        doc.close()
    return pages


def page_count(content: bytes) -> int:
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        count = doc.page_count
        doc.close()
        return count
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Could not parse PDF: {exc}") from exc