from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO
import re
import posixpath
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

try:  # pragma: no cover - optional dependency guard
    import openpyxl  # type: ignore
except Exception:  # noqa: BLE001
    openpyxl = None  # type: ignore

from .base_types import RawRow, UnsupportedFormatError
from ..upload_limits import (
    InvalidUpload,
    UploadPolicy,
    UploadTooLarge,
    get_upload_policy,
    validate_cell_text,
    validate_zip_payload,
)

__all__ = [
    "XLSXImportResult",
    "WorksheetDimensions",
    "parse_xlsx",
    "validate_xlsx_payload",
]


_CELL_REFERENCE = re.compile(r"^[A-Z]+[1-9][0-9]*$")


@dataclass(frozen=True)
class WorksheetDimensions:
    path: str
    max_row: int
    max_column: int


def _cell_coordinates(reference: str) -> tuple[int, int]:
    match = _CELL_REFERENCE.fullmatch(reference)
    if match is None:
        raise InvalidUpload("invalid worksheet cell coordinate")
    letters = reference.rstrip("0123456789")
    row = int(reference[len(letters) :])
    number = 0
    for letter in letters:
        number = number * 26 + ord(letter) - ord("A") + 1
    return number, row


def _validate_worksheet_structure(
    data: bytes, policy: UploadPolicy
) -> tuple[WorksheetDimensions, ...]:
    """Bound worksheet dimensions before openpyxl creates row-sized tuples."""
    dimensions: list[WorksheetDimensions] = []
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
            workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
            rels_root = ET.fromstring(
                archive.read("xl/_rels/workbook.xml.rels")
            )
            relationships: dict[str, tuple[str, str]] = {}
            for relationship in rels_root:
                rel_id = relationship.attrib.get("Id")
                target = relationship.attrib.get("Target")
                rel_type = relationship.attrib.get("Type", "")
                if not rel_id or not target:
                    raise InvalidUpload("incomplete workbook relationship")
                if rel_id in relationships:
                    raise InvalidUpload("duplicate workbook relationship ID")
                relationships[rel_id] = (target, rel_type)

            worksheet_names: list[str] = []
            relationship_attribute = (
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            for sheet in workbook_root.iter():
                if sheet.tag.rsplit("}", 1)[-1] != "sheet":
                    continue
                rel_id = sheet.attrib.get(relationship_attribute)
                if rel_id not in relationships:
                    raise InvalidUpload("worksheet relationship is missing")
                target, rel_type = relationships[rel_id]
                if not rel_type.endswith("/worksheet"):
                    raise InvalidUpload("worksheet relationship has invalid type")
                target_path = posixpath.normpath(
                    target.lstrip("/")
                    if target.startswith("/xl/")
                    else posixpath.join("xl", target)
                )
                if (
                    target_path in worksheet_names
                    or target_path not in names
                    or not target_path.startswith("xl/worksheets/")
                ):
                    raise InvalidUpload("worksheet relationship is inconsistent")
                worksheet_names.append(target_path)

            actual_parts = {
                name
                for name in names
                if name.startswith("xl/worksheets/") and name.endswith(".xml")
            }
            if not worksheet_names or set(worksheet_names) != actual_parts:
                raise InvalidUpload("worksheet relationship is incomplete")
            if len(worksheet_names) > policy.xlsx_sheets:
                raise UploadTooLarge("workbook contains too many sheets")

            rows_total = 0
            cells_total = 0
            for name in worksheet_names:
                current_row: dict[str, int] | None = None
                max_row = 0
                max_column = 0
                with archive.open(name) as worksheet:
                    for event, element in ET.iterparse(worksheet, events=("start", "end")):
                        tag = element.tag.rsplit("}", 1)[-1]
                        if event == "start" and tag == "row":
                            rows_total += 1
                            if rows_total > policy.rows_total:
                                raise UploadTooLarge("workbook contains too many rows")
                            row_number = int(element.attrib.get("r", rows_total))
                            if row_number > policy.rows_total:
                                raise UploadTooLarge("workbook contains too many rows")
                            max_row = max(max_row, row_number)
                            current_row = {"max_column": 0}
                        elif event == "end" and tag == "c":
                            if current_row is None:
                                raise InvalidUpload("cell is outside a worksheet row")
                            reference = element.attrib.get("r", "")
                            column, row_number = _cell_coordinates(reference)
                            if row_number > policy.rows_total:
                                raise UploadTooLarge("workbook contains too many rows")
                            if column > policy.columns_per_row:
                                raise UploadTooLarge(
                                    "worksheet row contains too many columns"
                                )
                            current_row["max_column"] = max(
                                current_row["max_column"], column
                            )
                            max_row = max(max_row, row_number)
                            max_column = max(max_column, column)
                            element.clear()
                        elif event == "end" and tag == "row":
                            if current_row is not None:
                                current_row = None
                            element.clear()
                cells_total += max_row * max_column
                if cells_total > policy.cells_total:
                    raise UploadTooLarge("workbook contains too many cells")
                dimensions.append(
                    WorksheetDimensions(
                        path=name, max_row=max_row, max_column=max_column
                    )
                )
        return tuple(dimensions)
    except UploadTooLarge:
        raise
    except InvalidUpload:
        raise
    except (OSError, ValueError, ET.ParseError, KeyError, zipfile.BadZipFile) as exc:
        raise InvalidUpload("invalid xlsx structure") from exc


def validate_xlsx_payload(
    data: bytes, *, policy: UploadPolicy | None = None
) -> tuple[WorksheetDimensions, ...]:
    active = policy or get_upload_policy()
    validate_zip_payload(data, policy=active)
    if openpyxl is None:
        raise UnsupportedFormatError("openpyxl is not installed")
    workbook = None
    try:
        dimensions = _validate_worksheet_structure(data, active)
        workbook = openpyxl.load_workbook(  # type: ignore[attr-defined]
            BytesIO(data), read_only=True, data_only=True
        )
        if len(workbook.worksheets) > active.xlsx_sheets:
            raise UploadTooLarge("workbook contains too many sheets")
        rows_total = 0
        cells_total = 0
        text_total = 0
        if len(workbook.worksheets) != len(dimensions):
            raise InvalidUpload("workbook worksheet count is inconsistent")
        for worksheet, dimension in zip(workbook.worksheets, dimensions, strict=True):
            if not dimension.max_row or not dimension.max_column:
                continue
            for row in worksheet.iter_rows(
                min_row=1,
                max_row=dimension.max_row,
                min_col=1,
                max_col=dimension.max_column,
                values_only=True,
            ):
                rows_total += 1
                if rows_total > active.rows_total:
                    raise UploadTooLarge("workbook contains too many rows")
                if len(row) > active.columns_per_row:
                    raise UploadTooLarge("worksheet row contains too many columns")
                cells_total += len(row)
                if cells_total > active.cells_total:
                    raise UploadTooLarge("workbook contains too many cells")
                for cell in row:
                    value = validate_cell_text(cell, policy=active)
                    text_total += len(value.encode("utf-8"))
                    if text_total > active.text_bytes:
                        raise UploadTooLarge("workbook text exceeds the allowed size")
    except UploadTooLarge:
        raise
    except InvalidUpload:
        raise
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise InvalidUpload("invalid xlsx file") from exc
    finally:
        if workbook is not None:
            workbook.close()
    return dimensions


@dataclass(slots=True)
class XLSXImportResult:
    rows: list[RawRow]
    headers: Sequence[str]


def parse_xlsx(data: bytes) -> XLSXImportResult:
    """Parse an XLSX file (first sheet) into raw rows.

    Rules mirror CSV/DOCX importers:
    - First row considered headers.
    - Blank rows skipped (all empty or None after str+strip).
    - Short rows padded, long rows truncated to header length.
    """
    if openpyxl is None:  # pragma: no cover - environment branch
        raise UnsupportedFormatError("openpyxl is not installed")

    dimensions = validate_xlsx_payload(data)

    from io import BytesIO

    wb = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)  # type: ignore[attr-defined]
    try:
        if not wb.sheetnames:
            return XLSXImportResult(rows=[], headers=[])
        ws = wb[wb.sheetnames[0]]

        dimension = (
            dimensions[0]
            if dimensions
            else WorksheetDimensions(path="", max_row=0, max_column=0)
        )
        if dimension.max_row <= 0 or dimension.max_column <= 0:
            return XLSXImportResult(rows=[], headers=[])
        rows_iter = ws.iter_rows(
            min_row=1,
            max_row=dimension.max_row,
            min_col=1,
            max_col=dimension.max_column,
            values_only=True,
        )
        try:
            raw_headers = next(rows_iter)
        except StopIteration:
            return XLSXImportResult(rows=[], headers=[])

        headers = [(_cell_to_str(c)) for c in raw_headers]

        rows: list[RawRow] = []
        for r in rows_iter:
            values = [(_cell_to_str(c)) for c in r[: len(headers)]]
            if all(v == "" for v in values):
                continue
            if len(values) < len(headers):
                values.extend(["" for _ in range(len(headers) - len(values))])
            mapped: RawRow = {}
            for h, v in zip(headers, values, strict=False):
                mapped[h] = v
            rows.append(mapped)

        return XLSXImportResult(rows=rows, headers=headers)
    finally:
        wb.close()


def _cell_to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().strip("\ufeff")
