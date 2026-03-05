from pathlib import Path


def test_planering_chip_selection_isolated_between_views_contract():
    js = Path("static/ui/kitchen_planering_v1.js").read_text(encoding="utf-8")

    # Separate in-memory state per view.
    assert "var selectedChipsNormal = { 1: new Set(), 2: new Set() };" in js
    assert "var selectedChipsSpecial = new Set();" in js

    # Single-bound handlers and delegated selectors scoped to each view.
    assert "var isSpecialChipHandlerBound = false;" in js
    assert "var isNormalChipHandlerBound = false;" in js
    assert "closest('.js-special-chip')" in js
    assert "closest('.js-normal-chip')" in js
    assert "closest('.specialkost-view')" in js
    assert "closest('.normalkost-view')" in js
    assert "closest('.diet-chip, .diet-btn')" not in js
    assert "function resetChipStateForMode(mode)" in js
    assert "clearNormalChipState();" in js
    assert "clearSpecialChipState();" in js
    assert "url.searchParams.delete('selected_diets');" in js

    # First click should update UI immediately in the active view.
    assert "renderSpecialSelectedList();" in js
    assert js.count("renderAllTotals();") >= 2


def test_planering_template_marks_normal_and_special_chip_views():
    tpl = Path("templates/ui/kitchen_planering_v1.html").read_text(encoding="utf-8")

    assert "js-special-chip" in tpl
    assert "js-normal-chip" in tpl
    assert 'data-mode="special"' in tpl
    assert 'class="kp-card kp-mb-12 specialkost-view"' in tpl
    assert 'class="kp-card kp-mb-12 normalkost-view"' in tpl
