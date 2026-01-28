from __future__ import annotations

from core.importers.menu_lines_parser import parse_lines


def test_footer_lines_do_not_become_meals_and_multiweek_continues():
    lines = [
        "v. 8",
        "Söndag :",
        "Lunch: Biff Lindström med sås & potatis",
        "Dessert: Smördegsbakade äpplen med vaniljsås",
        "Kväll: Mannagrynspudding med sylt & grädde",
        "Med reservation för ändringar. Ni når oss på telefon: 0701486879",
        "Allt med röd text tillhandahåller ni.",
        "v. 9",
        "Måndag :",
        "Alt 1: Korv med mos",
    ]

    result = parse_lines(lines)
    assert result.weeks, "No weeks parsed"

    # Find week 8 and assert Sunday lunch content
    wk8 = next((w for w in result.weeks if w.week == 8), None)
    assert wk8 is not None, "Week 8 not parsed"
    # Collect Sunday lunch items
    sunday_lunch = [i for i in wk8.items if i.day == "sunday" and i.meal == "lunch"]
    assert sunday_lunch, "No Sunday lunch items in week 8"
    # Check dish contains expected main text
    assert any("Biff Lindström" in i.dish_name for i in sunday_lunch)
    # Ensure footer strings are not present in any dish
    forbidden_substrings = [
        "Med reservation",
        "Ni når oss",
        "0701486879",
        "Allt med röd text",
    ]
    for it in wk8.items:
        for bad in forbidden_substrings:
            assert bad not in it.dish_name

    # Parser should continue to week 9 and recognize Monday Alt 1
    wk9 = next((w for w in result.weeks if w.week == 9), None)
    assert wk9 is not None, "Week 9 not parsed"
    mon_lunch_alt1 = [
        i for i in wk9.items if i.day == "monday" and i.meal == "lunch" and i.variant_type == "alt1"
    ]
    assert mon_lunch_alt1, "Week 9 Monday Alt 1 not parsed"
    assert any("Korv med mos" in i.dish_name for i in mon_lunch_alt1)
