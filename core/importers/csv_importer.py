from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from io import StringIO

from .base_types import RawRow

__all__ = ["CSVImportResult", "parse_csv"]


@dataclass(slots=True)
class CSVImportResult:
    rows: list[RawRow]
    headers: Sequence[str]


def _strip(s: str) -> str:
    return s.strip("\ufeff ")  # also strip any BOM left in-line


def parse_csv(text: str) -> CSVImportResult:
    """Parse CSV text into raw rows.

    - Skips rows that are completely empty (all cells blank after strip).
    - Retains original header order.
    - Converts all values to stripped strings.
    """

    # Normalize newlines for csv module determinism.
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    sio = StringIO(normalized)
    reader = csv.reader(sio)

    try:
        headers = next(reader)
    except StopIteration:
        return CSVImportResult(rows=[], headers=[])

    headers = [_strip(h) for h in headers]

    rows: list[RawRow] = []
    for _raw_idx, raw_row in enumerate(reader, start=1):  # 1-based for data lines
        if not raw_row:
            continue
        stripped = [_strip(cell) for cell in raw_row]
        if all(c == "" for c in stripped):  # skip fully blank line
            continue
        # Pad or trim the row to header length (extra cells kept with synthetic names?)
        # Decision: Extra cells beyond headers we ignore for now (validation layer can add error later if needed).
        if len(stripped) < len(headers):
            # Pad with empty strings so mapping always works (missing columns handled in validation later).
            stripped.extend(["" for _ in range(len(headers) - len(stripped))])
        mapped: RawRow = {}
        for h, v in zip(headers, stripped, strict=False):
            mapped[h] = v
        rows.append(mapped)

    return CSVImportResult(rows=rows, headers=headers)
