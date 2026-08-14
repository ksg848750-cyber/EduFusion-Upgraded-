import re

_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_BLANK = re.compile(r"\n{3,}")

_LEADING_GLYPHS = re.compile(r"^[\s\u2022\u25aa\u25cf\u25b8\u25c2\u25a0\u00b7\uf0d8\u25e6\u2023\u2043\u2219*+\-•·◦\u25aa\u25cf]+")


def _dehyphenate(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.rstrip().endswith("-") and i + 1 < len(lines):
            joined = line.rstrip()[:-1] + lines[i + 1].lstrip()
            out.append(joined)
            i += 2
        else:
            out.append(line)
            i += 1
    return "\n".join(out)


def strip_leading_glyphs(text: str) -> str:
    """Remove leading bullet/list glyphs (e.g. '\uf0d8', '•', '-') from a line.

    These are formatting markers, not semantic content; stripping them keeps
    headings and body lines clean and prevents them from leaking into concepts.
    """
    return _LEADING_GLYPHS.sub("", text)


def clean_page_text(text: str) -> str:
    """Light, generic structural cleaning of extracted page text.

    Fixes hyphenation across line breaks, collapses excessive whitespace and
    blank lines, and strips leading bullet glyphs. Does NOT remove content:
    uploaded documents are untrusted passive data and are never executed.
    """
    text = _dehyphenate(text)
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_BLANK.sub("\n\n", text)
    return text.strip()