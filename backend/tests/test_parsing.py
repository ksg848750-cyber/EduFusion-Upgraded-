import os

import pytest

from app.parsing.chunker import chunk_document
from app.parsing.cleaning import clean_page_text
from app.parsing.pdf import extract_pages, page_count

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "Computer_Architecture_Notes.pdf")


@pytest.fixture
def pdf_bytes():
    with open(FIXTURE, "rb") as fh:
        return fh.read()


def test_page_count(pdf_bytes):
    assert page_count(pdf_bytes) == 1


def test_extract_pages_retains_text(pdf_bytes):
    pages = extract_pages(pdf_bytes)
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "Instruction Pipeline" in pages[0].text


def test_extract_pages_rejects_non_pdf():
    with pytest.raises(ValueError):
        extract_pages(b"this is not a pdf")


def test_clean_page_text_fixes_hygiene():
    dirty = "pipel-\nine\n\n\n\n   stage"
    cleaned = clean_page_text(dirty)
    assert "pipeline" in cleaned
    assert "\n\n\n" not in cleaned


def test_chunk_document_assigns_headings_and_pages(pdf_bytes):
    pages = extract_pages(pdf_bytes)
    chunks = chunk_document(pages)
    assert len(chunks) >= 2
    assert all(c.page_number == 1 for c in chunks)
    titles = [c.section_title for c in chunks]
    assert any("Hazards" in (t or "") for t in titles)
    assert any("Data Forwarding" in (t or "") for t in titles)
    # hierarchy: subsection heading path nests under its parent section
    nested = [c.heading_path for c in chunks if c.section_title == "1.1 Stage throughput"]
    assert nested and nested[0][-2:] == ["1. The Instruction Pipeline", "1.1 Stage throughput"]


def test_chunk_document_respects_max_size():
    from app.parsing.pdf import PageText

    pages = [PageText(page_number=1, text="word " * 2000)]
    chunks = chunk_document(pages, max_chars=300, overlap_chars=50)
    assert len(chunks) > 1
    assert all(len(c.text) <= 300 for c in chunks)