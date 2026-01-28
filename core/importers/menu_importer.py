from __future__ import annotations

"""Menu Importer Adapter

DOCX-first importer that uses the DOCX lines extractor and the
format-agnostic core parser to produce weeks/items.
"""

from typing import Any

from .base import MenuImportResult
from .docx_lines_extractor import extract_lines_docx
from .menu_lines_parser import parse_lines


class MenuImporter:
    def can_handle(self, filename: str, mimetype: str | None, first_bytes: bytes) -> bool:
        low = (filename or "").lower()
        return low.endswith(".docx") or (
            mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    def parse(self, file_bytes: bytes, filename: str, mime: str | None = None) -> MenuImportResult:
        lines = extract_lines_docx(file_bytes)
        result = parse_lines(lines)
        return result

__all__ = ["MenuImporter"]
