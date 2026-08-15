"""Unit tests for OCR fallback in the PDF ingestion pipeline.

Coverage targets:
1. Normal text page -> OCR NOT invoked.
2. Empty/image-only page -> OCR invoked.
3. Sparse/noisy page -> OCR invoked.
4. Mixed PDF -> only weak pages invoke OCR.
5. OCR output preserves page number.
6. OCR output reaches the existing chunking pipeline.
7. Existing heading hierarchy does not regress.
8. OCR failure is handled safely.
9. Existing normal-PDF parsing tests still pass (regression suite).
10. Existing graph-quality tests still pass (regression suite).
"""

import io
import os

import pytest

from app.parsing.chunker import ExtractedChunk, chunk_document
from app.parsing.ocr import needs_ocr
from app.parsing.pdf import PageText, extract_pages

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "Computer_Architecture_Notes.pdf")


class FakeOcr:
    """Deterministic OCR double: returns canned text, records which pages were OCR'd."""

    def __init__(self, text="OCR RESULT line one\nline two"):
        self.text = text
        self.calls: list[int] = []

    def recognize(self, image_bytes: bytes) -> str:
        # Page number isn't passed to the engine; pdf.py logs it separately. We
        # use call ordering to detect which pages were OCR'd.
        self.calls.append(len(self.calls) + 1)
        return self.text


class FailingOcr(FakeOcr):
    def recognize(self, image_bytes: bytes) -> str:
        self.calls.append(len(self.calls) + 1)
        raise RuntimeError("OCR engine crashed")


def _text_page(text: str) -> PageText:
    return PageText(page_number=1, text=text)


# --- needs_ocr heuristic ---------------------------------------------------

def test_needs_ocr_rich_text_is_not_ocr():
    assert needs_ocr("This is a normal paragraph with plenty of words.", False) is False


def test_needs_ocr_empty_with_image_is_ocr():
    assert needs_ocr("", True) is True


def test_needs_ocr_empty_without_image_is_not_ocr():
    assert needs_ocr("", False) is False


def test_needs_ocr_sparse_noisy_text_is_ocr():
    # A page number + stray glyphs, no real words -> noisy -> OCR even w/o image.
    assert needs_ocr("42 \u2022 \u25aa \u25cf ---", False) is True


def test_needs_ocr_short_clean_title_without_image_is_not_ocr():
    # Few words but clean and no image -> keep text as-is.
    assert needs_ocr("Computer Architecture", False) is False


def test_needs_ocr_short_with_image_is_ocr():
    # Few words but has a raster image (looks like a scan) -> OCR.
    assert needs_ocr("42", True) is True


# --- extract_pages integration ---------------------------------------------

@pytest.fixture
def pdf_bytes():
    with open(FIXTURE, "rb") as fh:
        return fh.read()


def test_normal_text_page_does_not_invoke_ocr(pdf_bytes):
    ocr = FakeOcr()
    pages = extract_pages(pdf_bytes, ocr=ocr)
    assert not ocr.calls
    assert all(p.ocr_used is False for p in pages)
    assert "Instruction Pipeline" in pages[0].text


def test_mixed_pdf_only_weak_pages_invoke_ocr(pdf_bytes):
    """Build a 2-page PDF: page1 = normal text, page2 = an embedded scan image."""
    import pymupdf as fitz

    src = fitz.open(stream=pdf_bytes, filetype="pdf")
    src_page = src[0]
    # render page1 to a full-page image -> a realistic "scanned" page
    pix = src_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
    png = pix.tobytes("png")

    doc = fitz.open()
    doc.new_page(width=src_page.rect.width, height=src_page.rect.height)  # page1 blank
    doc.new_page(width=src_page.rect.width, height=src_page.rect.height)  # page2
    doc[1].insert_image(src_page.rect, stream=png)
    pdf = doc.tobytes()
    doc.close()
    src.close()

    # Overlay real text on page1 so it reads as a normal text page.
    good = fitz.open(stream=pdf, filetype="pdf")
    good[0].insert_text((72, 72), "This page has plenty of selectable body text.")
    pdf = good.tobytes()
    good.close()

    ocr = FakeOcr()
    pages = extract_pages(pdf, ocr=ocr)
    assert len(pages) == 2
    # only the image-only page triggered OCR
    assert pages[0].ocr_used is False
    assert pages[1].ocr_used is True
    assert pages[1].page_number == 2


def test_ocr_output_preserves_page_number(pdf_bytes):
    import pymupdf as fitz

    src = fitz.open(stream=pdf_bytes, filetype="pdf")
    src_page = src[0]
    pix = src_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
    png = pix.tobytes("png")
    doc = fitz.open()
    doc.new_page(width=src_page.rect.width, height=src_page.rect.height)
    doc[0].insert_image(src_page.rect, stream=png)
    pdf = doc.tobytes()
    doc.close()
    src.close()

    ocr = FakeOcr()
    pages = extract_pages(pdf, ocr=ocr)
    assert pages[0].ocr_used is True
    assert pages[0].page_number == 1
    assert "OCR RESULT" in pages[0].text


def test_ocr_output_reaches_chunking_pipeline():
    pages = [PageText(page_number=1, text="", ocr_used=True)]
    # replace page text with OCR output as extract_pages would
    pages[0].text = "OCR RESULT heading\nOCR RESULT body sentence here."
    chunks = chunk_document(pages)
    assert chunks
    assert any("OCR RESULT" in c.text for c in chunks)
    assert any(c.page_number == 1 for c in chunks)


def test_ocr_provenance_flows_to_chunk():
    pages = [PageText(page_number=1, text="scanned body content", ocr_used=True)]
    chunks = chunk_document(pages)
    assert chunks
    assert any(c.ocr_page_numbers == [1] for c in chunks)


def test_non_ocr_chunk_has_empty_ocr_provenance(pdf_bytes):
    pages = extract_pages(pdf_bytes)
    chunks = chunk_document(pages)
    assert chunks
    assert all(c.ocr_page_numbers == [] for c in chunks)


def test_ocr_failure_is_handled_safely(pdf_bytes):
    import pymupdf as fitz

    src = fitz.open(stream=pdf_bytes, filetype="pdf")
    src_page = src[0]
    pix = src_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
    png = pix.tobytes("png")
    doc = fitz.open()
    doc.new_page(width=src_page.rect.width, height=src_page.rect.height)
    doc[0].insert_image(src_page.rect, stream=png)
    pdf = doc.tobytes()
    doc.close()
    src.close()

    ocr = FailingOcr()
    pages = extract_pages(pdf, ocr=ocr)
    # failure must not raise; page falls back to (empty) text, no crash
    assert pages[0].ocr_used is False
    assert pages[0].text == ""


def test_ocr_disabled_leaves_normal_text_untouched(pdf_bytes):
    pages = extract_pages(pdf_bytes, ocr_enabled=False)
    assert "Instruction Pipeline" in pages[0].text
    assert all(p.ocr_used is False for p in pages)


# --- regression: existing heading hierarchy ---------------------------------

def test_existing_heading_hierarchy_does_not_regress(pdf_bytes):
    pages = extract_pages(pdf_bytes)
    chunks = chunk_document(pages)
    nested = [c.heading_path for c in chunks if c.section_title == "1.1 Stage throughput"]
    assert nested and nested[0][-2:] == ["1. The Instruction Pipeline", "1.1 Stage throughput"]