"""Turn an uploaded document into text.

Library choice is deliberate: `pdfminer.six` rather than `pypdf` because it
reconstructs runs instead of emitting one spaced glyph at a time. Measured
on a real Chinese résumé, `pypdf` in its default mode produced 215 isolated
single-character tokens ("保 持 务 实") and split "Cyclic" into "C y c l ic";
`pdfminer.six` produced 6 and 0. Text that broken cannot be searched or
deduplicated.

PyMuPDF would extract better still, but it is AGPL and this project is MIT.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from docx import Document
from pdfminer.high_level import extract_text as pdfminer_extract

# Below this, the file is almost certainly an image scan rather than text.
MIN_USEFUL_CHARS = 80

SUPPORTED_SUFFIXES = (".pdf", ".docx", ".md", ".markdown", ".txt")

_FORM_FEED = re.compile(r"\x0c")

# PDF text is positioned glyph by glyph, so a wide gap between two Chinese
# characters arrives as an ordinary space: "主 导从", "针 对". Chinese does
# not space between characters, so any such space is an artefact. The cost
# is that a separator written as a space ("昆仑巢 独立开发者") is joined too;
# for a tool whose job is search and dedupe, a missing separator is cheaper
# than a word the index cannot find.
_CJK = "\u3400-\u4dbf\u4e00-\u9fff"
_CJK_PUNCT = "\u3000-\u303f\uff01-\uff0f\uff1a-\uff20\u2014\u2026\u00b7"
_CJK_JOIN = re.compile(rf"(?<=[{_CJK}])[ \t]+(?=[{_CJK}])")
_PUNCT_JOIN = re.compile(
    rf"(?<=[{_CJK}])[ \t]+(?=[{_CJK_PUNCT}])|(?<=[{_CJK_PUNCT}])[ \t]+(?=[{_CJK}])"
)
_BLANK_RUN = re.compile(r"\n{3,}")
_TRAILING = re.compile(r"[ \t]+$", re.MULTILINE)


class UnsupportedDocument(ValueError):
    """The file type is not one we can read."""


class EmptyDocument(ValueError):
    """The file parsed but carries no text — usually a scan."""


def extract_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise UnsupportedDocument(
            f"{suffix or 'no extension'} is not supported; "
            f"accepted: {', '.join(SUPPORTED_SUFFIXES)}"
        )

    if suffix == ".pdf":
        text = _from_pdf(data)
    elif suffix == ".docx":
        text = _from_docx(data)
    else:
        text = _from_plain(data)

    text = normalise(text)
    if len(text) < MIN_USEFUL_CHARS:
        raise EmptyDocument(
            "no usable text was extracted — a scanned or image-only document "
            "needs OCR, which is not supported"
        )
    return text


def normalise(text: str) -> str:
    text = _FORM_FEED.sub("\n", text)
    text = _CJK_JOIN.sub("", text)
    text = _PUNCT_JOIN.sub("", text)
    text = _TRAILING.sub("", text)
    text = _BLANK_RUN.sub("\n\n", text)
    return text.strip()


def _from_pdf(data: bytes) -> str:
    try:
        return pdfminer_extract(io.BytesIO(data))
    except Exception as error:  # pdfminer raises a variety of parser errors
        raise UnsupportedDocument(f"could not read the PDF: {error}") from error


def _from_docx(data: bytes) -> str:
    try:
        document = Document(io.BytesIO(data))
    except Exception as error:
        raise UnsupportedDocument(f"could not read the DOCX: {error}") from error

    lines = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            lines.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(lines)


def _from_plain(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise UnsupportedDocument("the file is not UTF-8 text") from error
