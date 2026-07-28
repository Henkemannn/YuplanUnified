from __future__ import annotations

from datetime import date

from core.offshore_demo_menu_seed import build_demo_menu_import_result, demo_menu_csv_path


def test_demo_menu_csv_builds_four_weeks() -> None:
    result = build_demo_menu_import_result(csv_path=demo_menu_csv_path(), anchor_day=date(2026, 7, 20))

    assert len(result.weeks) == 4
    assert [(week.year, week.week) for week in result.weeks] == [(2026, 30), (2026, 31), (2026, 32), (2026, 33)]
    assert [len(week.items) for week in result.weeks] == [42, 41, 41, 42]
    first_week = result.weeks[0]
    assert first_week.items[0].day == "monday"
    assert first_week.items[0].meal == "lunch"
    assert first_week.items[0].variant_type == "main"
    assert first_week.items[0].dish_name == "Pork sweetnsour"
