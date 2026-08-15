"""Page-level OCR fallback for scanned / image-only PDF pages.

OCR is a *complement* to PyMuPDF text extraction, never a replacement. The
normal pipeline (PyMuPDF selectable text) is untouched; only pages that fail a
quality check are rendered to an image and recognized.

Engine: RapidOCR (``rapidocr-onnxruntime``) - a self-contained ONNX OCR that
requires no external binary and reuses the ``onnxruntime`` already pulled in by
fastembed. It targets printed text; handwriting is not supported.
"""

import io
import logging
import re
from typing import Protocol

logger = logging.getLogger(__name__)

# Quality heuristic thresholds (see needs_ocr).
MIN_MEANINGFUL_WORDS = 5
MIN_ALNUM_RATIO = 0.5

# Render scale for OCR input. Higher = better accuracy, slower.
OCR_SCALE = 2.0

_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")

# OCR often drops a space between an uppercase acronym and the following
# lowercase word ("C-LOOKscheduling") or a closing paren and the next word
# ("SSTF(shortestseektimefirst)algorithm"). Restore those boundaries so the
# LLM and chunker see cleaner tokens. Requires 2+ uppercase letters and a 3+
# letter lowercase tail, so normal words ("MacBook", "DVDs", "Don't") are left
# untouched.
_OCR_ACRONYM_GLUE = re.compile(r"([A-Z]{2,})([a-z]{3,})")
_OCR_PAREN_GLUE = re.compile(r"\)([a-z])")


def _restore_ocr_spacing(text: str) -> str:
    text = _OCR_ACRONYM_GLUE.sub(r"\1 \2", text)
    text = _OCR_PAREN_GLUE.sub(r") \1", text)
    return text


class OcrEngine(Protocol):
    def recognize(self, image_bytes: bytes) -> str:  # pragma: no cover - protocol
        """Return recognized text for a PNG image (bytes) or '' on no text."""


class RapidOcrEngine:
    """RapidOCR backed by onnxruntime. Lazy model load; models auto-download."""

    _instance: "RapidOcrEngine | None" = None

    def __init__(self) -> None:
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR  # imported lazily

            self._engine = RapidOCR()
        return self._engine

    def recognize(self, image_bytes: bytes) -> str:
        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)
        result, _elapse = self._get_engine()(arr)
        if not result:
            return ""
        return _restore_ocr_spacing("\n".join(item[1] for item in result))

    @classmethod
    def get_instance(cls) -> "RapidOcrEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


def get_ocr_engine() -> OcrEngine:
    """Return the shared OCR engine singleton."""
    return RapidOcrEngine.get_instance()


def needs_ocr(text: str, has_raster_image: bool) -> bool:
    """Decide whether a page should be OCR'd.

    Rules (explainable, not an arbitrary length cut-off):

    1. A page with at least ``MIN_MEANINGFUL_WORDS`` real words is treated as
       having usable selectable text -> never OCR'd.
    2. Otherwise the page is *sparse*. It is OCR'd when it also looks like a
       scan (contains a raster image) OR its extracted text is mostly noise
       (low alphanumeric-to-printable ratio, e.g. stray glyphs/page numbers).
    3. A page with no text at all is OCR'd only when it actually contains a
       raster image; a genuinely blank page is skipped.
    """
    if not text or not text.strip():
        return has_raster_image

    words = _WORD.findall(text)
    meaningful = [w for w in words if len(w) >= 2]
    if len(meaningful) >= MIN_MEANINGFUL_WORDS:
        return False

    printable = [c for c in text if not c.isspace()]
    if not printable:
        return has_raster_image
    ratio = sum(1 for c in printable if c.isalnum()) / len(printable)
    noisy = ratio < MIN_ALNUM_RATIO
    return has_raster_image or noisy