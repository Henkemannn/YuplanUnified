from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

from openpyxl import load_workbook

from werkzeug.datastructures import FileStorage

_SUPPORTED_EXTENSIONS = {".txt", ".csv", ".xlsx"}
_TEXT_HEADER_TOKENS = {
    "text",
    "line",
    "name",
    "dish",
    "dish_name",
    "composition",
    "composition_name",
    "title",
    "ratt",
    "ratt_namn",
}
_HEADING_PREFIXES = (
    "week",
    "vecka",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "mandag",
    "tisdag",
    "onsdag",
    "torsdag",
    "fredag",
    "lordag",
    "sondag",
)
_LABEL_TOKENS = {
    "menu",
    "meny",
    "lunch",
    "middag",
    "dinner",
    "breakfast",
    "frukost",
    "kvallsmat",
    "kvallsmat",
    "special",
    "specialkost",
}


@dataclass(frozen=True)
class BuilderFileImportLine:
    raw_text: str
    normalized_text: str
    classification: str
    reason: str | None = None


@dataclass(frozen=True)
class BuilderFileImportPreview:
    file_type: str
    lines: list[str]
    importable_lines: list[str]
    ignored_lines: list[BuilderFileImportLine]
    classified_lines: list[BuilderFileImportLine]
    csv_column: str | None = None
    csv_column_index: int | None = None


def parse_builder_import_file(
    file_storage: FileStorage,
    *,
    csv_column: str | None = None,
) -> BuilderFileImportPreview:
    filename = str(getattr(file_storage, "filename", "") or "").strip()
    if not filename:
        raise ValueError("file name is required")

    lower_name = filename.lower()
    if not any(lower_name.endswith(ext) for ext in _SUPPORTED_EXTENSIONS):
        raise ValueError("unsupported file type; use .txt, .csv, or .xlsx")

    raw_bytes = file_storage.read()
    if not raw_bytes:
        raise ValueError("file is empty")

    if lower_name.endswith(".txt"):
        return _build_preview(file_type="txt", lines=_parse_txt_lines(raw_bytes))

    if lower_name.endswith(".xlsx"):
        lines, used_column, used_index = _parse_xlsx_lines(raw_bytes, csv_column=csv_column)
        return _build_preview(
            file_type="xlsx",
            lines=lines,
            csv_column=used_column,
            csv_column_index=used_index,
        )

    lines, used_column, used_index = _parse_csv_lines(raw_bytes, csv_column=csv_column)
    return _build_preview(
        file_type="csv",
        lines=lines,
        csv_column=used_column,
        csv_column_index=used_index,
    )


def _build_preview(
    *,
    file_type: str,
    lines: list[str],
    csv_column: str | None = None,
    csv_column_index: int | None = None,
) -> BuilderFileImportPreview:
    classified = classify_builder_import_lines(lines)
    importable = [item.normalized_text for item in classified if item.classification == "importable_dish"]
    ignored = [item for item in classified if item.classification == "ignored_noise"]
    if not importable:
        raise ValueError("file contains no importable dish lines")

    return BuilderFileImportPreview(
        file_type=file_type,
        lines=importable,
        importable_lines=importable,
        ignored_lines=ignored,
        classified_lines=classified,
        csv_column=csv_column,
        csv_column_index=csv_column_index,
    )


def _decode_utf8_text(raw_bytes: bytes) -> str:
    try:
        return raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("file must be UTF-8 encoded") from exc


def _normalize_non_empty_lines(values: list[str]) -> list[str]:
    normalized = [str(item or "").strip() for item in values]
    return [item for item in normalized if item]


def _parse_txt_lines(raw_bytes: bytes) -> list[str]:
    text = _decode_utf8_text(raw_bytes)
    lines = [str(item or "").strip() for item in text.splitlines()]
    if not lines:
        raise ValueError("file contains no importable lines")
    return lines


def _parse_csv_lines(
    raw_bytes: bytes,
    *,
    csv_column: str | None,
) -> tuple[list[str], str | None, int]:
    text = _decode_utf8_text(raw_bytes)
    reader = csv.reader(io.StringIO(text, newline=""))
    rows = [row for row in reader if any(str(cell or "").strip() for cell in row)]
    if not rows:
        raise ValueError("file contains no importable rows")

    extracted, used_column, used_index = _extract_lines_from_tabular_rows(rows, csv_column=csv_column)

    if not extracted:
        raise ValueError("file contains no importable lines")

    return extracted, used_column, used_index


def _parse_xlsx_lines(
    raw_bytes: bytes,
    *,
    csv_column: str | None,
) -> tuple[list[str], str | None, int]:
    workbook = None
    try:
        workbook = load_workbook(filename=io.BytesIO(raw_bytes), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError("invalid xlsx file") from exc

    if not workbook.worksheets:
        raise ValueError("file contains no importable rows")

    rows: list[list[str]] = []
    try:
        worksheet = workbook.worksheets[0]
        for row in worksheet.iter_rows(values_only=True):
            normalized_row = [str(cell or "").strip() for cell in row]
            if any(cell for cell in normalized_row):
                rows.append(normalized_row)
    finally:
        if workbook is not None:
            workbook.close()

    if not rows:
        raise ValueError("file contains no importable rows")

    extracted, used_column, used_index = _extract_lines_from_tabular_rows(rows, csv_column=csv_column)

    if not extracted:
        raise ValueError("file contains no importable lines")

    return extracted, used_column, used_index


def _extract_lines_from_tabular_rows(
    rows: list[list[str]],
    *,
    csv_column: str | None,
) -> tuple[list[str], str | None, int]:
    header_row = [str(cell or "").strip() for cell in rows[0]]
    header_tokens = [cell.lower() for cell in header_row]

    selected_index = 0
    selected_column = None
    skip_header = False

    csv_column_value = str(csv_column or "").strip()
    if csv_column_value:
        if csv_column_value.isdigit():
            selected_index = int(csv_column_value)
            if selected_index < 0:
                raise ValueError("csv_column index must be >= 0")
            selected_column = str(selected_index)
            skip_header = any(token in _TEXT_HEADER_TOKENS for token in header_tokens)
        else:
            match_index = next(
                (
                    idx
                    for idx, token in enumerate(header_tokens)
                    if token == csv_column_value.lower()
                ),
                None,
            )
            if match_index is None:
                raise ValueError("csv_column not found in header")
            selected_index = match_index
            selected_column = header_row[selected_index]
            skip_header = True
    else:
        detected_index = next(
            (
                idx
                for idx, token in enumerate(header_tokens)
                if token in _TEXT_HEADER_TOKENS
            ),
            None,
        )
        if detected_index is not None:
            selected_index = detected_index
            selected_column = header_row[selected_index]
            skip_header = True
        else:
            selected_index = 0
            selected_column = header_row[0] if header_row else "0"
            skip_header = False

    extracted: list[str] = []
    start_row = 1 if skip_header else 0
    for row in rows[start_row:]:
        value = row[selected_index] if selected_index < len(row) else ""
        normalized = str(value or "").strip()
        if normalized:
            extracted.append(normalized)

    return extracted, selected_column, selected_index


def classify_builder_import_lines(lines: list[str]) -> list[BuilderFileImportLine]:
    classified: list[BuilderFileImportLine] = []
    for line in lines:
        normalized = str(line or "").strip()
        classification, reason = _classify_single_line(normalized)
        classified.append(
            BuilderFileImportLine(
                raw_text=str(line or ""),
                normalized_text=normalized,
                classification=classification,
                reason=reason,
            )
        )
    return classified


def _classify_single_line(normalized: str) -> tuple[str, str | None]:
    if not normalized:
        return "ignored_noise", "blank"

    collapsed = re.sub(r"\s+", " ", normalized).strip()
    lower = collapsed.lower().strip(" :.-")
    alnum = re.sub(r"[^a-z0-9]+", "", lower)

    if re.fullmatch(r"alt\s*[12]", lower):
        return "ignored_noise", "alt_marker"

    if lower in {"alt", "alt1", "alt2"}:
        return "ignored_noise", "alt_marker"

    if any(lower == prefix or lower.startswith(prefix + " ") or lower.startswith(prefix + ":") for prefix in _HEADING_PREFIXES):
        return "ignored_noise", "heading"

    if lower in _LABEL_TOKENS:
        return "ignored_noise", "label"

    if len(alnum) <= 1:
        return "ignored_noise", "near_blank"

    return "importable_dish", None


__all__ = [
    "BuilderFileImportLine",
    "BuilderFileImportPreview",
    "classify_builder_import_lines",
    "parse_builder_import_file",
]
