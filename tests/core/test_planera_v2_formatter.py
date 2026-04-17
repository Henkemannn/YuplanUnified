from __future__ import annotations

from core.planera_v2.domain import Deviation, PlanRequest
from core.planera_v2.engine import compute_plan
from core.planera_v2.formatter import format_plan_result, format_plan_result_clean


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


def test_format_plan_result_clean_hides_zero_rows_and_keeps_non_zero_values() -> None:
    request = PlanRequest(
        baseline=20,
        deviations=[
            Deviation(form="Timbal", category_keys=["Ej Fisk"], quantity=2, unit_id="avd_a"),
            Deviation(form="Grovpate", category_keys=["Diabetes"], quantity=0, unit_id="avd_b"),
            Deviation(form="Flytande", category_keys=["Laktosfri"], quantity=3, unit_id="avd_c"),
        ],
    )
    result = compute_plan(request)

    output = format_plan_result_clean(result)

    assert "Totals:" in output
    assert "  Baseline: 20" in output
    assert "  Deviations: 5" in output
    assert "  Normal: 15" in output

    assert "Production by form:" in output
    assert "  - timbal: 2" in output
    assert "  - flytande: 3" in output
    assert "grovpate" not in output

    assert "Production by combination:" in output
    assert "  - timbal__ej_fisk: 2" in output
    assert "  - flytande__laktosfri: 3" in output
    assert "grovpate__diabetes" not in output

    assert "Production by unit:" in output
    assert "  - avd_a: 2" in output
    assert "  - avd_c: 3" in output
    assert "avd_b" not in output


def test_format_plan_result_clean_keeps_relevant_warnings() -> None:
    request = PlanRequest(
        baseline=5,
        deviations=[
            Deviation(form="Timbal", category_keys=[], quantity=2, unit_id="avd_a"),
        ],
    )
    result = compute_plan(request)

    output = format_plan_result_clean(result)

    assert "Warnings:" in output
    assert "missing category_key" in output
