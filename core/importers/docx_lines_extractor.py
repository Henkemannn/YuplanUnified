from __future__ import annotations

"""DOCX Lines Extractor (format-specific)

Produces a flat list of non-empty, stripped text lines from a Word (.docx) file.
Preserves reading order across paragraphs and tables.
"""

from typing import List

try:  # pragma: no cover - optional dependency guard
    import docx  # type: ignore
except Exception:  # noqa: BLE001
    docx = None  # type: ignore[assignment]


def extract_lines_docx(data: bytes) -> List[str]:
    """Return plain text lines from DOCX.

    Rules:
    - Read document paragraphs first, then tables.
    - Split on embedded newlines within paragraph/cell texts.
    - Strip whitespace; skip empty lines.
    """
    if docx is None:  # pragma: no cover
        raise RuntimeError("python-docx not installed")

    from io import BytesIO

    document = docx.Document(BytesIO(data))  # type: ignore[attr-defined]
    lines: List[str] = []

    def _emit(text: str) -> None:
        t = text.strip()
        if not t:
            return
        for part in t.split("\n"):
            p = part.strip()
            if p:
                lines.append(p)

    for p in document.paragraphs:
        _emit(p.text)

    for table in getattr(document, "tables", []):
        for row in getattr(table, "rows", []):
            for cell in getattr(row, "cells", []):
                _emit(cell.text)

    return lines
