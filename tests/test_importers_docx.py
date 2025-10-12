from __future__ import annotations

import io

import pytest

from core.importers.docx_table_importer import UnsupportedFormatError, parse_docx
from core.importers.validate import ImportValidationError, validate_and_normalize

try:  # pragma: no cover - runtime branch
    import docx  # type: ignore
except Exception:  # noqa: BLE001
    docx = None  # type: ignore


def _build_docx(headers: list[str], rows: list[list[str]]) -> bytes:
    if docx is None:  # pragma: no cover
        pytest.skip("python-docx not installed")
    buf = io.BytesIO()
    document = docx.Document()  # type: ignore[attr-defined]
    table = document.add_table(rows=1 + len(rows), cols=len(headers))
    for ci, h in enumerate(headers):
        table.rows[0].cells[ci].text = h
    for ri, r in enumerate(rows, start=1):
        for ci, val in enumerate(r):
            table.rows[ri].cells[ci].text = val
    document.save(buf)
    return buf.getvalue()


@pytest.mark.skipif(docx is None, reason="python-docx not installed")
def test_docx_happy():
    data = _build_docx(
        ["title", "description", "priority"], [["A", "Alpha", "1"], ["B", "Beta", "2"]]
    )
    result = parse_docx(data)
    assert result.headers == ["title", "description", "priority"]
    normalized = validate_and_normalize(result.rows)
    assert len(normalized) == 2


@pytest.mark.skipif(docx is None, reason="python-docx not installed")
def test_docx_empty_table():
    data = _build_docx(["title", "description", "priority"], [])
    result = parse_docx(data)
    assert result.rows == []


@pytest.mark.skipif(docx is None, reason="python-docx not installed")
def test_docx_missing_required():
    data = _build_docx(["title", "description"], [["A", "Alpha"]])
    result = parse_docx(data)
    with pytest.raises(ImportValidationError):
        validate_and_normalize(result.rows)


def test_docx_missing_library():
    if docx is not None:
        pytest.skip("python-docx installed")
    with pytest.raises(UnsupportedFormatError):
        parse_docx(b"fake")
