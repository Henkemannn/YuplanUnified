import io

import pytest
from docx import Document

from core.importers.composite import CompositeMenuImporter
from core.importers.docx_importer import DocxMenuImporter
from core.importers.excel_importer import ExcelMenuImporter
from core.menu_import_service import MenuImportService


def make_docx(lines):
    buf = io.BytesIO()
    doc = Document()
    for line in lines:
        p = doc.add_paragraph()
        p.add_run(line)
    doc.save(buf)
    return buf.getvalue()


def make_table_docx(weeks):
    buf = io.BytesIO()
    doc = Document()
    headers = ["Dag", "Lunch alt 1", "Lunch alt 2", "Dessert", "Kvällsmat"]
    weekdays = ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"]
    for index, (week, year) in enumerate(weeks):
        if index:
            doc.add_paragraph("")
        doc.add_paragraph(f"Vecka {week} · {year}")
        table = doc.add_table(rows=8, cols=5)
        for column, header in enumerate(headers):
            table.cell(0, column).text = header
        for row, day in enumerate(weekdays, start=1):
            values = [
                day,
                f"Köttbullar, {day}!",
                "-" if day in {"Lördag", "Söndag"} else f"Fiskgratäng ({day})",
                "Äppelpaj med vaniljsås",
                "Soppa & bröd",
            ]
            for column, value in enumerate(values):
                table.cell(row, column).text = value
    doc.save(buf)
    return buf.getvalue()


def test_docx_basic_alt_detection():
    content = ["Vecka 12", "Mån: Alt1: Fiskgratäng", "Tis: Alt2: Köttfärssås", "Ons: Kväll: Soppa"]
    data = make_docx(content)
    imp = DocxMenuImporter()
    res = imp.parse(data, "meny.docx")
    assert res.weeks, "Should parse at least one week"
    week = res.weeks[0]
    names = {i.dish_name for i in week.items}
    assert "Fiskgratäng" in names
    assert "Köttfärssås" in names
    assert "Soppa" in names
    # Evening variant should map to meal dinner and variant_type main
    evening = [i for i in week.items if i.meal == "dinner"]
    assert evening and evening[0].variant_type == "main"


def test_docx_one_week_table_imports_26_items_and_maps_slots():
    result = DocxMenuImporter().parse(make_table_docx([(45, 2026)]), "week.docx")

    assert [(week.year, week.week, len(week.items)) for week in result.weeks] == [(2026, 45, 26)]
    monday = {item.variant_type: item for item in result.weeks[0].items if item.day == "monday"}
    assert monday["alt1"].meal == "lunch"
    assert monday["alt2"].dish_name == "Fiskgratäng (Måndag)"
    assert monday["dessert"].dish_name == "Äppelpaj med vaniljsås"
    assert monday["main"].meal == "dinner"
    assert monday["main"].dish_name == "Soppa & bröd"
    assert all(item.day != "saturday" or item.variant_type != "alt2" for item in result.weeks[0].items)


def test_docx_table_day_cells_can_include_dates():
    data = make_table_docx([(45, 2026)]).replace(b"M\xc3\xa5ndag", "Måndag\n2/11".encode())

    result = DocxMenuImporter().parse(data, "dated-week.docx")

    assert len(result.weeks) == 1
    monday_items = [item for item in result.weeks[0].items if item.day == "monday"]
    assert len(monday_items) == 4
    assert all("2/11" not in item.dish_name for item in monday_items)


def test_docx_ten_week_table_import_preserves_order_and_counts():
    weeks = [(week, 2026) for week in range(45, 54)] + [(1, 2027)]

    result = DocxMenuImporter().parse(make_table_docx(weeks), "ten-weeks.docx")

    assert [(week.year, week.week) for week in result.weeks] == [
        (2026, week) for week in range(45, 54)
    ] + [(2027, 1)]
    assert sum(len(week.items) for week in result.weeks) == 260


def test_docx_table_validates_week_53_and_week_1_years():
    result = DocxMenuImporter().parse(
        make_table_docx([(53, 2026), (1, 2027)]),
        "cross-year.docx",
    )

    assert [(week.year, week.week) for week in result.weeks] == [(2026, 53), (2027, 1)]


def test_empty_docx_import_fails_before_menu_persistence():
    result = DocxMenuImporter().parse(make_docx(["Vecka 45 · 2026"]), "empty.docx")

    assert result.weeks == []
    assert result.errors == ["No menu items recognized; no menus were created."]
    with pytest.raises(ValueError, match="No menu items recognized"):
        MenuImportService(object()).apply(1, "site-a", result)


def test_composite_unknown():
    comp = CompositeMenuImporter([DocxMenuImporter(), ExcelMenuImporter()])
    bogus = b"not a valid menu format"
    res = comp.parse(bogus, "foo.txt", "text/plain")
    assert res.errors and "No importer accepted file" in res.errors[0]
