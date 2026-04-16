from __future__ import annotations

from core.planera_v2.domain import Deviation, PlanRequest, Totals, UnitBreakdown
from core.planera_v2.engine import compute_plan


def test_realistic_fixture_with_mixed_units_forms_categories_and_edges() -> None:
    request = PlanRequest(
        baseline=40,
        deviations=[
            Deviation(form="Timbal", category_keys=["Ej Fisk"], quantity=3, unit_id="unit_a"),
            Deviation(
                form="FLYTANDE",
                category_keys=["Laktosfri", "Ej Fisk"],
                quantity=2,
                unit_id="unit_a",
            ),
            Deviation(form="GrovPate", category_keys=["Not Fri"], quantity=4, unit_id="unit_b"),
            Deviation(
                form="timbal",
                category_keys=["EJ FISK", "lAkToSfRi"],
                quantity=1,
                unit_id="unit_b",
            ),
            Deviation(form="grovpate", category_keys=["Diabetes"], quantity=0, unit_id="unit_c"),
            Deviation(form="timbal", category_keys=[], quantity=2, unit_id="unit_c"),
            Deviation(form="flytande", category_keys=["ej_fisk"], quantity=5, unit_id="unit_c"),
        ],
    )

    result = compute_plan(request)

    assert result.totals == Totals(baseline_total=40, deviation_total=15, normal_total=25)
    assert result.per_form == {
        "flytande": 7,
        "grovpate": 4,
        "timbal": 4,
    }
    assert result.per_combination == {
        "flytande__ej_fisk": 5,
        "flytande__ej_fisk__laktosfri": 2,
        "grovpate__diabetes": 0,
        "grovpate__not_fri": 4,
        "timbal__ej_fisk": 3,
        "timbal__ej_fisk__laktosfri": 1,
    }
    assert result.per_unit == {
        "unit_a": 5,
        "unit_b": 5,
        "unit_c": 5,
    }
    assert result.per_unit_breakdown == {
        "unit_a": UnitBreakdown(
            baseline_total=0,
            deviation_total=5,
            normal_total=0,
            per_combination={
                "flytande__ej_fisk__laktosfri": 2,
                "timbal__ej_fisk": 3,
            },
            per_form={
                "flytande": 2,
                "timbal": 3,
            },
        ),
        "unit_b": UnitBreakdown(
            baseline_total=0,
            deviation_total=5,
            normal_total=0,
            per_combination={
                "grovpate__not_fri": 4,
                "timbal__ej_fisk__laktosfri": 1,
            },
            per_form={
                "grovpate": 4,
                "timbal": 1,
            },
        ),
        "unit_c": UnitBreakdown(
            baseline_total=0,
            deviation_total=5,
            normal_total=0,
            per_combination={
                "flytande__ej_fisk": 5,
                "grovpate__diabetes": 0,
            },
            per_form={
                "flytande": 5,
                "grovpate": 0,
            },
        ),
    }
    assert any("missing category_key" in warning for warning in result.warnings)
