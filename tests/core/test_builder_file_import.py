from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
import pytest
from werkzeug.datastructures import FileStorage

from core.builder.file_import import parse_builder_import_file


def _file(name: str, raw: bytes) -> FileStorage:
    return FileStorage(stream=BytesIO(raw), filename=name)


def _xlsx_bytes(rows: list[list[str]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)

    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def test_parse_txt_file_to_normalized_lines() -> None:
    preview = parse_builder_import_file(
        _file("library.txt", b"Kottbullar med potatismos\n\n Fiskgratang  \n"),
    )

    assert preview.file_type == "txt"
    assert preview.lines == ["Kottbullar med potatismos", "Fiskgratang"]


def test_parse_csv_file_detects_likely_text_column() -> None:
    preview = parse_builder_import_file(
        _file(
            "library.csv",
            b"dish_name,category\nKottbullar med potatismos,main\nFiskgratang,main\n",
        ),
    )

    assert preview.file_type == "csv"
    assert preview.lines == ["Kottbullar med potatismos", "Fiskgratang"]
    assert preview.csv_column == "dish_name"
    assert preview.csv_column_index == 0


def test_parse_csv_file_supports_explicit_column_name() -> None:
    preview = parse_builder_import_file(
        _file(
            "library.csv",
            b"id,text,flag\n1,Kottbullar med potatismos,x\n2,Fiskgratang,y\n",
        ),
        csv_column="text",
    )

    assert preview.lines == ["Kottbullar med potatismos", "Fiskgratang"]
    assert preview.csv_column == "text"
    assert preview.csv_column_index == 1


def test_parse_csv_file_uses_first_column_when_no_text_header_found() -> None:
    preview = parse_builder_import_file(
        _file("library.csv", b"Kottbullar med potatismos,main\nFiskgratang,main\n"),
    )

    assert preview.lines == ["Kottbullar med potatismos", "Fiskgratang"]
    assert preview.csv_column_index == 0


def test_parse_xlsx_file_detects_likely_text_column() -> None:
    preview = parse_builder_import_file(
        _file(
            "library.xlsx",
            _xlsx_bytes(
                [
                    ["dish_name", "category"],
                    ["Kottbullar med potatismos", "main"],
                    ["Fiskgratang", "main"],
                ]
            ),
        ),
    )

    assert preview.file_type == "xlsx"
    assert preview.lines == ["Kottbullar med potatismos", "Fiskgratang"]
    assert preview.csv_column == "dish_name"
    assert preview.csv_column_index == 0


def test_parse_xlsx_file_supports_explicit_column_name() -> None:
    preview = parse_builder_import_file(
        _file(
            "library.xlsx",
            _xlsx_bytes(
                [
                    ["id", "text", "flag"],
                    ["1", "Kottbullar med potatismos", "x"],
                    ["2", "Fiskgratang", "y"],
                ]
            ),
        ),
        csv_column="text",
    )

    assert preview.file_type == "xlsx"
    assert preview.lines == ["Kottbullar med potatismos", "Fiskgratang"]
    assert preview.csv_column == "text"
    assert preview.csv_column_index == 1


def test_parse_rejects_unsupported_extension() -> None:
    with pytest.raises(ValueError, match="unsupported file type"):
        parse_builder_import_file(_file("library.pdf", b"x"))


def test_parse_txt_ignores_alt_markers_and_headings() -> None:
    preview = parse_builder_import_file(
        _file(
            "library.txt",
            b"Week 12\nAlt 1\nAlt 2\nMonday\nKottbullar med potatismos\n",
        ),
    )

    assert preview.importable_lines == ["Kottbullar med potatismos"]
    ignored_texts = [item.normalized_text for item in preview.ignored_lines]
    assert "Alt 1" in ignored_texts
    assert "Alt 2" in ignored_texts
    assert "Week 12" in ignored_texts
    assert "Monday" in ignored_texts


def test_parse_xlsx_ignores_markers_and_labels() -> None:
    preview = parse_builder_import_file(
        _file(
            "library.xlsx",
            _xlsx_bytes(
                [
                    ["text"],
                    ["Week 12"],
                    ["Alt 1"],
                    ["Lunch"],
                    ["Fiskgratang"],
                ]
            ),
        ),
    )

    assert preview.importable_lines == ["Fiskgratang"]
    ignored_reasons = {item.reason for item in preview.ignored_lines}
    assert "heading" in ignored_reasons
    assert "alt_marker" in ignored_reasons
    assert "label" in ignored_reasons


def test_parse_txt_keeps_valid_dishes_and_ignores_labels() -> None:
    preview = parse_builder_import_file(
        _file(
            "library.txt",
            b"Lunch\nFiskgratang\nMeny\nKottbullar med graddsas\n",
        ),
    )

    assert preview.importable_lines == ["Fiskgratang", "Kottbullar med graddsas"]
    ignored_reasons = {item.reason for item in preview.ignored_lines}
    assert "label" in ignored_reasons
