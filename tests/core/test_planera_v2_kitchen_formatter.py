from __future__ import annotations

from core.planera_v2.domain import Deviation, PlanRequest, UnitInput
from core.planera_v2.engine import compute_plan
from core.planera_v2.formatter import format_plan_result_kitchen_view


def test_kitchen_formatter_shows_units_grouping_totals_and_hides_zero_rows() -> None:
    request = PlanRequest(
        baseline=40,
        deviations=[
            Deviation(form="Timbal", category_keys=["Ej Fisk"], quantity=3, unit_id="avd_a"),
            Deviation(form="Flytande", category_keys=["Laktosfri"], quantity=2, unit_id="avd_a"),
            Deviation(form="Grovpate", category_keys=["Diabetes"], quantity=0, unit_id="avd_b"),
            Deviation(form="Timbal", category_keys=["Laktosfri"], quantity=4, unit_id="avd_c"),
            Deviation(form="Flytande", category_keys=["Ej Fisk"], quantity=1, unit_id="avd_c"),
            Deviation(form="Timbal", category_keys=[], quantity=2, unit_id="avd_c"),
        ],
    )
    result = compute_plan(request)

    output = format_plan_result_kitchen_view(result)

    assert "Unit: avd_a" in output
    assert "Unit: avd_c" in output
    assert "Unit: avd_b" not in output

    assert "  Normalkost:" in output
    assert "    total: not available yet" in output
    assert "  Specialkost:" in output

    assert "    timbal:" in output
    assert "    flytande:" in output
    assert "      ej_fisk: 3" in output
    assert "      laktosfri: 2" in output
    assert "      laktosfri: 4" in output
    assert "      ej_fisk: 1" in output

    assert "TOTAL" in output
    assert "  Normalkost: 30" in output
    assert "  Specialkost: 10" in output
    assert "  Total: 40" in output

    assert "  Total: not available yet" in output

    assert "grovpate__diabetes" not in output
    assert "diabetes: 0" not in output

    assert "Warnings:" in output
    assert "missing category_key" in output


def test_kitchen_formatter_uses_exact_unit_breakdown_not_any_proportional_allocation() -> None:
    request = PlanRequest(
        baseline=100,
        deviations=[
            Deviation(form="Timbal", category_keys=["Ej Fisk"], quantity=6, unit_id="unit_1"),
            Deviation(form="Timbal", category_keys=["Ej Fisk"], quantity=1, unit_id="unit_2"),
        ],
    )
    result = compute_plan(request)

    output = format_plan_result_kitchen_view(result)

    assert "Unit: unit_1" in output
    assert "Unit: unit_2" in output
    assert "      ej_fisk: 6" in output
    assert "      ej_fisk: 1" in output
    assert "      ej_fisk: 4" not in output
    assert "      ej_fisk: 3" not in output


def test_kitchen_formatter_shows_exact_unit_normal_when_baseline_available() -> None:
    request = PlanRequest(
        baseline=30,
        units=[
            UnitInput(unit_id="unit_1", baseline_total=10),
            UnitInput(unit_id="unit_2", baseline_total=8),
        ],
        deviations=[
            Deviation(form="Timbal", category_keys=["Ej Fisk"], quantity=3, unit_id="unit_1"),
            Deviation(form="Flytande", category_keys=["Laktosfri"], quantity=2, unit_id="unit_2"),
            Deviation(form="Timbal", category_keys=["Laktosfri"], quantity=1, unit_id="unit_3"),
        ],
    )
    result = compute_plan(request)

    output = format_plan_result_kitchen_view(result)

    assert "Unit: unit_1" in output
    assert "Unit: unit_2" in output
    assert "Unit: unit_3" in output

    assert "    total: 7" in output
    assert "    total: 6" in output
    assert "    total: not available yet" in output

    assert "  Total: 10" in output
    assert "  Total: 8" in output
    assert "  Total: not available yet" in output
