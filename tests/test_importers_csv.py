from __future__ import annotations

import pytest

from core.importers.csv_importer import parse_csv
from core.importers.validate import ImportValidationError, validate_and_normalize


def test_csv_empty_file():
    result = parse_csv("")
    assert result.headers == []
    assert result.rows == []


def test_csv_only_headers():
    text = "title,description,priority\n"
    result = parse_csv(text)
    assert result.headers == ["title", "description", "priority"]
    assert result.rows == []


def test_csv_happy_path():
    text = "title,description,priority\nA,Alpha,1\nB,Beta,2\n"
    rows = parse_csv(text).rows
    normalized = validate_and_normalize(rows)
    assert len(normalized) == 2
    assert normalized[0]["title"] == "A"
    assert normalized[1]["priority"] == 2


def test_csv_blank_lines_and_whitespace():
    text = "title,description,priority\nA,Alpha,1\n\n   ,   ,   \nB , Beta , 2 \n"
    rows = parse_csv(text).rows
    assert len(rows) == 2  # blank & whitespace-only rows skipped


def test_csv_missing_required_column():
    text = "title,description\nA,Alpha\n"
    rows = parse_csv(text).rows
    with pytest.raises(ImportValidationError) as exc:
        validate_and_normalize(rows)
    errors = exc.value.errors
    assert any(e["code"] == "missing_column" and e["column"] == "priority" for e in errors)


def test_csv_empty_required_value():
    text = "title,description,priority\n,Alpha,1\n"
    rows = parse_csv(text).rows
    with pytest.raises(ImportValidationError) as exc:
        validate_and_normalize(rows)
    errors = exc.value.errors
    assert any(e["code"] == "empty_value" and e["column"] == "title" for e in errors)


def test_csv_invalid_int_priority():
    text = "title,description,priority\nA,Alpha,zzz\n"
    rows = parse_csv(text).rows
    with pytest.raises(ImportValidationError) as exc:
        validate_and_normalize(rows)
    errors = exc.value.errors
    assert any(e["code"] == "invalid_int" for e in errors)


def test_csv_unicode_values():
    text = "title,description,priority\nÅÄÖ,βγδ,3\n"
    rows = parse_csv(text).rows
    normalized = validate_and_normalize(rows)
    assert normalized[0]["title"] == "ÅÄÖ"
    assert normalized[0]["description"] == "βγδ"


def test_csv_extra_column_reports_error():
    text = "title,description,priority,extra\nA,Alpha,1,IGNORED\n"
    rows = parse_csv(text).rows
    with pytest.raises(ImportValidationError) as exc:
        validate_and_normalize(rows)
    errors = exc.value.errors
    assert any(e["code"] == "unexpected_extra_column" and e["column"] == "extra" for e in errors)
