from __future__ import annotations

from core.planera_v2.domain import Deviation, PlanRequest
from core.planera_v2.engine import compute_plan
from core.planera_v2.formatter import format_plan_result


def test_format_plan_result_contains_expected_sections_and_values() -> None:
    request = PlanRequest(
        baseline=10,
        deviations=[
            Deviation(form="Timbal", category_keys=["Ej Fisk"], quantity=2, unit_id="avd_a"),
            Deviation(form="Flytande", category_keys=["Laktosfri"], quantity=1, unit_id="avd_b"),
        ],
    )
    result = compute_plan(request)

    output = format_plan_result(result)

    assert "Totals:" in output
    assert "  baseline_total: 10" in output
    assert "  deviation_total: 3" in output
    assert "  normal_total: 7" in output

    assert "Per form:" in output
    assert "  flytande: 1" in output
    assert "  timbal: 2" in output

    assert "Per combination:" in output
    assert "  flytande__laktosfri: 1" in output
    assert "  timbal__ej_fisk: 2" in output

    assert "Per unit:" in output
    assert "  avd_a: 2" in output
    assert "  avd_b: 1" in output

    assert "Warnings:" in output
    assert "  (none)" in output
