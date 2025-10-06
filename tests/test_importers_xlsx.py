from __future__ import annotations

import io

import pytest

from core.importers.validate import ImportValidationError, validate_and_normalize
from core.importers.xlsx_importer import UnsupportedFormatError, parse_xlsx

try:  # pragma: no cover - optional dependency
    import openpyxl  # type: ignore
except Exception:  # noqa: BLE001
    openpyxl = None  # type: ignore


def _build_wb(headers: list[str], rows: list[list[str]]):
    if openpyxl is None:  # pragma: no cover
        pytest.skip("openpyxl not installed")
    from openpyxl import Workbook  # type: ignore

    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for r in rows:
        ws.append(r)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


@pytest.mark.skipif(openpyxl is None, reason="openpyxl not installed")
def test_xlsx_happy():
    data = _build_wb(["title", "description", "priority"], [["A", "Alpha", "1"], ["B", "Beta", "2"]])
    result = parse_xlsx(data)
    assert result.headers == ["title", "description", "priority"]
    norm = validate_and_normalize(result.rows)
    assert len(norm) == 2


@pytest.mark.skipif(openpyxl is None, reason="openpyxl not installed")
def test_xlsx_empty_sheet():
    data = _build_wb(["title", "description", "priority"], [])
    result = parse_xlsx(data)
    assert result.rows == []


@pytest.mark.skipif(openpyxl is None, reason="openpyxl not installed")
def test_xlsx_missing_column():
    data = _build_wb(["title", "description"], [["A", "Alpha"]])
    result = parse_xlsx(data)
    with pytest.raises(ImportValidationError):
        validate_and_normalize(result.rows)


@pytest.mark.skipif(openpyxl is None, reason="openpyxl not installed")
def test_xlsx_invalid_int():
    data = _build_wb(["title", "description", "priority"], [["A", "Alpha", "zzz"]])
    result = parse_xlsx(data)
    with pytest.raises(ImportValidationError):
        validate_and_normalize(result.rows)


@pytest.mark.skipif(openpyxl is None, reason="openpyxl not installed")
def test_xlsx_unicode_and_extra():
    data = _build_wb(["title", "description", "priority", "extra"], [["Å", "βγ", "3", "X"]])
    result = parse_xlsx(data)
    with pytest.raises(ImportValidationError) as exc:
        validate_and_normalize(result.rows)
    errors = exc.value.errors
    assert any(e["code"] == "unexpected_extra_column" and e["column"] == "extra" for e in errors)


def test_xlsx_missing_library():
    if openpyxl is not None:
        pytest.skip("openpyxl installed")
    with pytest.raises(UnsupportedFormatError):
        parse_xlsx(b"fake")
