from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import zipfile

try:  # pragma: no cover - optional dependency guard
    import docx
except Exception:  # noqa: BLE001
    docx = None  # type: ignore[assignment]

from .base_types import RawRow, UnsupportedFormatError
from ..upload_limits import (
    InvalidUpload,
    UploadPolicy,
    UploadTooLarge,
    get_upload_policy,
    validate_cell_text,
    validate_zip_payload,
)

__all__ = ["DOCXImportResult", "parse_docx", "validate_docx_payload"]


def _logical_row_width(row_element) -> int:
    width = 0
    for cell in row_element:
        if cell.tag.rsplit("}", 1)[-1] != "tc":
            continue
        span = 1
        for property_element in cell:
            if property_element.tag.rsplit("}", 1)[-1] != "tcPr":
                continue
            for child in property_element:
                if child.tag.rsplit("}", 1)[-1] == "gridSpan":
                    try:
                        span = max(1, int(child.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val", "1")))
                    except (TypeError, ValueError):
                        raise InvalidUpload("invalid DOCX cell span") from None
        width += span
    return width


def validate_docx_payload(data: bytes, *, policy: UploadPolicy | None = None) -> None:
    active = policy or get_upload_policy()
    validate_zip_payload(data, policy=active)
    if docx is None:
        raise UnsupportedFormatError("python-docx is not installed")
    from io import BytesIO

    try:
        document = docx.Document(BytesIO(data))  # type: ignore[attr-defined]
        if len(document.tables) > active.docx_tables:
            raise UploadTooLarge("document contains too many tables")
        rows_total = 0
        cells_total = 0
        text_total = 0

        body = document.element.body
        for element in body.iter():
            tag = element.tag.rsplit("}", 1)[-1]
            if tag == "p" and element.getparent() is body:
                rows_total += 1
            elif tag == "tr":
                rows_total += 1
                logical_width = _logical_row_width(element)
                if logical_width > active.columns_per_row:
                    raise UploadTooLarge("table row contains too many columns")
                cells_total += logical_width
                if cells_total > active.cells_total:
                    raise UploadTooLarge("document contains too many cells")
            if rows_total > active.rows_total:
                raise UploadTooLarge("document contains too many rows")

        def add_text(value: object) -> None:
            nonlocal text_total
            text = validate_cell_text(value, policy=active)
            text_total += len(text.encode("utf-8"))
            if text_total > active.text_bytes:
                raise UploadTooLarge("document text exceeds the allowed size")

        for paragraph in document.paragraphs:
            add_text(paragraph.text)
        for table in document.tables:
            for row in table.rows:
                if len(row.cells) > active.columns_per_row:
                    raise UploadTooLarge("table row contains too many columns")
                for cell in row.cells:
                    add_text(cell.text)
    except UploadTooLarge:
        raise
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        raise InvalidUpload("invalid docx file") from exc


@dataclass(slots=True)
class DOCXImportResult:
    rows: list[RawRow]
    headers: Sequence[str]


def parse_docx(data: bytes) -> DOCXImportResult:
    """Parse a simple DOCX table file into raw rows.

    Rules:
    - Use first table only. If none, return empty.
    - First row = headers (stripped).
    - Blank data rows (all empty cells) skipped.
    - Short rows padded with empty strings; long rows truncated.
    """
    if docx is None:  # pragma: no cover - environment branch
        raise UnsupportedFormatError("python-docx is not installed")

    validate_docx_payload(data)

    # python-docx expects a path or a file-like; wrap bytes in BytesIO.
    from io import BytesIO

    document = docx.Document(BytesIO(data))  # type: ignore[attr-defined]
    if not document.tables:
        return DOCXImportResult(rows=[], headers=[])
    table = document.tables[0]
    if not table.rows:
        return DOCXImportResult(rows=[], headers=[])

    def _clean(s: str) -> str:
        return s.strip().strip("\ufeff")

    headers = [_clean(c.text) for c in table.rows[0].cells]

    rows: list[RawRow] = []
    for r in table.rows[1:]:
        cells = [_clean(c.text) for c in r.cells]
        if all(c == "" for c in cells):
            continue
        if len(cells) < len(headers):
            cells.extend(["" for _ in range(len(headers) - len(cells))])
        mapped: RawRow = {}
        for h, v in zip(headers, cells, strict=False):
            mapped[h] = v
        rows.append(mapped)

    return DOCXImportResult(rows=rows, headers=headers)
