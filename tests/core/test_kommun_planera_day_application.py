from __future__ import annotations

import inspect
from copy import deepcopy
from datetime import date

import pytest

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.db import get_session
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.kommun_planera_day_application import compare_kommun_day_payloads, run_kommun_day_application
from core.planera_v2.adapters.kommun_day_projection import KommunDayProjectionError
from core.planera_v2.day_context_resolver import KommunDayContextResolverError, resolve_kommun_day_business_context
from core.planera_v2.day_orchestration import (
    KommunDayBusinessContext,
    KommunDepartmentProjectionContext,
)
from core.planera_v2.kommun_day_application import run_canonical_kommun_day
from core.weekview.repo import WeekviewRepo
from sqlalchemy import text

pytestmark = pytest.mark.usefixtures("app_session")


def _seed_site(name: str = "Planera app site") -> dict:
    db = get_session()
    try:
        db.execute(text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(1, 'Tenant 1', 1)"))
        db.commit()
    finally:
        db.close()
    site, _ = SitesRepo().create_site(name, tenant_id=1)
    return site


def _seed_department(site_id: str, name: str, fixed: int = 10) -> dict:
    department, _ = DepartmentsRepo().create_department(
        site_id=site_id,
        name=name,
        resident_count_mode="fixed",
        resident_count_fixed=fixed,
    )
    return department


def _seed_weekview_counts(department_id: str, service_date: str, *, lunch: int, dinner: int) -> None:
    year, week, weekday = date.fromisoformat(service_date).isocalendar()
    WeekviewRepo().set_residents_counts(
        tenant_id=1,
        year=year,
        week=week,
        department_id=department_id,
        items=[
            {"day_of_week": weekday, "meal": "lunch", "count": lunch},
            {"day_of_week": weekday, "meal": "dinner", "count": dinner},
        ],
    )


def _seed_requirement_group(site_id: str, department_id: str, *, label: str, requirement_name: str, quantity: int) -> str:
    requirement_id = DietTypesRepo().create(site_id=site_id, name=requirement_name, default_select=False, semantics="atomic")
    group = DepartmentRequirementGroupsRepo().create_group(department_id, quantity, [requirement_id], label=label)
    return str(group["id"])


class _RecordingLegacyService:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = deepcopy(payload)
        self.calls: list[dict[str, object]] = []

    def compute_day(
        self,
        tenant_id: int | str,
        site_id: str,
        iso_date: str,
        departments: list[tuple[str, str]],
    ) -> dict[str, object]:
        self.calls.append(
            {
                "tenant_id": tenant_id,
                "site_id": site_id,
                "iso_date": iso_date,
                "departments": list(departments),
            }
        )
        return deepcopy(self.payload)


class _RecordingLogger:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def info(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("info", args, kwargs))

    def warning(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("warning", args, kwargs))

    def exception(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("exception", args, kwargs))


class _ContextProbe:
    def __init__(self, context: KommunDayBusinessContext) -> None:
        self.context = context
        self.calls = 0

    def __call__(self, **kwargs: object) -> KommunDayBusinessContext:
        self.calls += 1
        return self.context


def _route_payload_from_context(context: KommunDayBusinessContext, legacy_shape: dict[str, object]) -> dict[str, object]:
    return {
        "site_id": context.site_id,
        "site_name": context.site_name,
        "date": context.service_date,
        "meal_labels": {"lunch": context.meal_labels["lunch"], "dinner": context.meal_labels["dinner"]},
        "departments": legacy_shape["departments"],
        "totals": legacy_shape["totals"],
    }


def test_legacy_mode_returns_current_contract_and_assembles_from_resolved_context(monkeypatch: pytest.MonkeyPatch) -> None:
    context = KommunDayBusinessContext(
        tenant_id=1,
        site_id="site-1",
        site_name="Resolved Site",
        service_date="2026-09-07",
        departments=(
            KommunDepartmentProjectionContext(department_id="dep-a", department_name="Alpha"),
        ),
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        lunch_baselines={"dep-a": 10},
        dinner_baselines={"dep-a": 8},
        requirement_projection_by_group_id={},
    )
    resolved_contexts: list[KommunDayBusinessContext] = []

    def _resolve(**kwargs: object) -> KommunDayBusinessContext:
        resolved_contexts.append(context)
        return context

    monkeypatch.setattr("core.kommun_planera_day_application.resolve_kommun_day_business_context", _resolve)

    legacy_service = _RecordingLegacyService(
        {
            "meal_labels": {"lunch": "Wrong Lunch", "dinner": "Wrong Dinner"},
            "departments": [
                {
                    "department_id": "dep-a",
                    "department_name": "Alpha",
                    "meals": {
                        "lunch": {"residents_total": 10, "special_diets": [], "normal_diet_count": 10},
                        "dinner": {"residents_total": 8, "special_diets": [], "normal_diet_count": 8},
                    },
                }
            ],
            "totals": {
                "lunch": {"residents_total": 10, "special_diets": [], "normal_diet_count": 10},
                "dinner": {"residents_total": 8, "special_diets": [], "normal_diet_count": 8},
            },
        }
    )

    result = run_kommun_day_application(
        mode="legacy",
        tenant_id=1,
        site_id="site-1",
        service_date="2026-09-07",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        department_id="dep-a",
        legacy_service=legacy_service,
    )

    expected = _route_payload_from_context(context, legacy_service.payload)
    assert result == expected
    assert result["meal_labels"] == {"lunch": "Lunch", "dinner": "Kvällsmat"}
    assert resolved_contexts == [context]
    assert legacy_service.calls == [
        {
            "tenant_id": 1,
            "site_id": "site-1",
            "iso_date": "2026-09-07",
            "departments": [("dep-a", "Alpha")],
        }
    ]


def test_shadow_mode_returns_legacy_payload_and_reuses_same_context(monkeypatch: pytest.MonkeyPatch) -> None:
    context = KommunDayBusinessContext(
        tenant_id=1,
        site_id="site-1",
        site_name="Shadow Site",
        service_date="2026-09-07",
        departments=(
            KommunDepartmentProjectionContext(department_id="dep-a", department_name="Alpha"),
        ),
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        lunch_baselines={"dep-a": 10},
        dinner_baselines={"dep-a": 8},
        requirement_projection_by_group_id={},
    )
    resolve_probe = _ContextProbe(context)
    canonical_calls: list[KommunDayBusinessContext] = []
    legacy_service = _RecordingLegacyService(
        {
            "departments": [
                {
                    "department_id": "dep-a",
                    "department_name": "Alpha",
                    "meals": {
                        "lunch": {"residents_total": 10, "special_diets": [], "normal_diet_count": 10},
                        "dinner": {"residents_total": 8, "special_diets": [], "normal_diet_count": 8},
                    },
                }
            ],
            "totals": {
                "lunch": {"residents_total": 10, "special_diets": [], "normal_diet_count": 10},
                "dinner": {"residents_total": 8, "special_diets": [], "normal_diet_count": 8},
            },
        }
    )
    logger = _RecordingLogger()

    def _canonical(candidate: KommunDayBusinessContext) -> dict[str, object]:
        canonical_calls.append(candidate)
        assert candidate is context
        return _route_payload_from_context(context, legacy_service.payload)

    monkeypatch.setattr("core.kommun_planera_day_application.resolve_kommun_day_business_context", resolve_probe)
    monkeypatch.setattr("core.kommun_planera_day_application.run_canonical_kommun_day", _canonical)

    result = run_kommun_day_application(
        mode="shadow",
        tenant_id=1,
        site_id="site-1",
        service_date="2026-09-07",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        legacy_service=legacy_service,
        logger=logger,
    )

    expected = _route_payload_from_context(context, legacy_service.payload)
    assert result == expected
    assert resolve_probe.calls == 1
    assert canonical_calls == [context]
    assert any(call[0] == "info" for call in logger.calls)


def test_shadow_mode_canonical_failure_does_not_change_legacy_response(monkeypatch: pytest.MonkeyPatch) -> None:
    context = KommunDayBusinessContext(
        tenant_id=1,
        site_id="site-1",
        site_name="Failure Site",
        service_date="2026-09-07",
        departments=(
            KommunDepartmentProjectionContext(department_id="dep-a", department_name="Alpha"),
        ),
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        lunch_baselines={"dep-a": 10},
        dinner_baselines={"dep-a": 8},
        requirement_projection_by_group_id={},
    )
    legacy_service = _RecordingLegacyService(
        {
            "departments": [
                {
                    "department_id": "dep-a",
                    "department_name": "Alpha",
                    "meals": {
                        "lunch": {"residents_total": 10, "special_diets": [], "normal_diet_count": 10},
                        "dinner": {"residents_total": 8, "special_diets": [], "normal_diet_count": 8},
                    },
                }
            ],
            "totals": {
                "lunch": {"residents_total": 10, "special_diets": [], "normal_diet_count": 10},
                "dinner": {"residents_total": 8, "special_diets": [], "normal_diet_count": 8},
            },
        }
    )
    logger = _RecordingLogger()

    def _resolve(**kwargs: object) -> KommunDayBusinessContext:
        return context

    def _boom(candidate: KommunDayBusinessContext) -> dict[str, object]:
        raise KommunDayProjectionError("missing_group_projection", "canonical shadow failed")

    monkeypatch.setattr("core.kommun_planera_day_application.resolve_kommun_day_business_context", _resolve)
    monkeypatch.setattr("core.kommun_planera_day_application.run_canonical_kommun_day", _boom)

    result = run_kommun_day_application(
        mode="shadow",
        tenant_id=1,
        site_id="site-1",
        service_date="2026-09-07",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        legacy_service=legacy_service,
        logger=logger,
    )

    assert result == _route_payload_from_context(context, legacy_service.payload)
    assert any(call[0] == "exception" for call in logger.calls)


def test_shadow_numerical_parity_passes_on_real_canonical_data() -> None:
    site = _seed_site("Real parity site")
    alpha = _seed_department(site["id"], "Alpha", fixed=10)
    service_date = "2026-09-07"
    _seed_weekview_counts(alpha["id"], service_date, lunch=11, dinner=9)
    _seed_requirement_group(site["id"], alpha["id"], label="Glutenfri", requirement_name="Glutenfri", quantity=1)

    legacy_service = _RecordingLegacyService(
        {
            "departments": [
                {
                    "department_id": alpha["id"],
                    "department_name": alpha["name"],
                    "meals": {
                        "lunch": {
                            "residents_total": 11,
                            "special_diets": [{"diet_type_id": "legacy-special", "diet_name": "Legacy special", "count": 1}],
                            "normal_diet_count": 10,
                        },
                        "dinner": {
                            "residents_total": 9,
                            "special_diets": [{"diet_type_id": "legacy-special", "diet_name": "Legacy special", "count": 1}],
                            "normal_diet_count": 8,
                        },
                    },
                }
            ],
            "totals": {
                "lunch": {
                    "residents_total": 11,
                    "special_diets": [{"diet_type_id": "legacy-special", "diet_name": "Legacy special", "count": 1}],
                    "normal_diet_count": 10,
                },
                "dinner": {
                    "residents_total": 9,
                    "special_diets": [{"diet_type_id": "legacy-special", "diet_name": "Legacy special", "count": 1}],
                    "normal_diet_count": 8,
                },
            },
        }
    )

    legacy_payload = run_kommun_day_application(
        mode="legacy",
        tenant_id=1,
        site_id=site["id"],
        service_date=service_date,
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        legacy_service=legacy_service,
    )
    canonical_context = resolve_kommun_day_business_context(
        tenant_id=1,
        site_id=site["id"],
        service_date=service_date,
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
    )
    canonical_payload = run_canonical_kommun_day(canonical_context)

    comparison = compare_kommun_day_payloads(legacy_payload, canonical_payload)

    assert comparison.matched is True
    assert comparison.meals["lunch"].matched is True
    assert comparison.meals["dinner"].matched is True
    assert comparison.meals["lunch"].totals["deviation_total"].matched is True


def test_compare_helper_ignores_special_diet_labels_and_ids() -> None:
    legacy_payload = {
        "departments": [
            {
                "department_id": "dept-a",
                "department_name": "Dept A",
                "meals": {
                    "lunch": {
                        "residents_total": 10,
                        "special_diets": [{"diet_type_id": "legacy-id", "diet_name": "Legacy label", "count": 2}],
                        "normal_diet_count": 8,
                    },
                    "dinner": {"residents_total": 6, "special_diets": [], "normal_diet_count": 6},
                },
            }
        ],
        "totals": {
            "lunch": {
                "residents_total": 10,
                "special_diets": [{"diet_type_id": "legacy-id", "diet_name": "Legacy label", "count": 2}],
                "normal_diet_count": 8,
            },
            "dinner": {"residents_total": 6, "special_diets": [], "normal_diet_count": 6},
        },
    }
    canonical_payload = {
        "departments": [
            {
                "department_id": "dept-a",
                "department_name": "Dept A",
                "meals": {
                    "lunch": {
                        "residents_total": 10,
                        "special_diets": [{"diet_type_id": "canonical-id", "diet_name": "Canonical label", "count": 2}],
                        "normal_diet_count": 8,
                    },
                    "dinner": {"residents_total": 6, "special_diets": [], "normal_diet_count": 6},
                },
            }
        ],
        "totals": {
            "lunch": {
                "residents_total": 10,
                "special_diets": [{"diet_type_id": "canonical-id", "diet_name": "Canonical label", "count": 2}],
                "normal_diet_count": 8,
            },
            "dinner": {"residents_total": 6, "special_diets": [], "normal_diet_count": 6},
        },
    }

    comparison = compare_kommun_day_payloads(legacy_payload, canonical_payload)

    assert comparison.matched is True
    assert comparison.meals["lunch"].per_department["dept-a"]["deviation_total"].matched is True


def test_optional_department_scope_preserved() -> None:
    site = _seed_site("Scoped app site")
    alpha = _seed_department(site["id"], "Alpha")
    _seed_department(site["id"], "Beta")
    service_date = "2026-09-07"
    _seed_weekview_counts(alpha["id"], service_date, lunch=11, dinner=9)
    legacy_payload = run_kommun_day_application(
        mode="legacy",
        tenant_id=1,
        site_id=site["id"],
        service_date=service_date,
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        department_id=alpha["id"],
    )

    assert [department["department_id"] for department in legacy_payload["departments"]] == [alpha["id"]]


def test_wrong_tenant_fails_before_legacy_service_call() -> None:
    site = _seed_site("Tenant guard site")
    _seed_department(site["id"], "Alpha")
    legacy_service = _RecordingLegacyService({"departments": [], "totals": {"lunch": {}, "dinner": {}}})

    with pytest.raises(KommunDayContextResolverError, match="site_not_owned"):
        run_kommun_day_application(
            mode="legacy",
            tenant_id=2,
            site_id=site["id"],
            service_date="2026-09-07",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            legacy_service=legacy_service,
        )

    assert legacy_service.calls == []


def test_invalid_mode_fails_before_resolver_or_service(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver_called: list[bool] = []
    service_called: list[bool] = []

    def _resolve(**kwargs: object) -> KommunDayBusinessContext:
        resolver_called.append(True)
        raise AssertionError("resolver should not be called")

    class _FailingService:
        def compute_day(self, *args: object, **kwargs: object) -> dict[str, object]:
            service_called.append(True)
            raise AssertionError("service should not be called")

    monkeypatch.setattr("core.kommun_planera_day_application.resolve_kommun_day_business_context", _resolve)

    with pytest.raises(ValueError, match="unsupported application mode"):
        run_kommun_day_application(
            mode="legacy-unknown",  # type: ignore[arg-type]
            tenant_id=1,
            site_id="site-1",
            service_date="2026-09-07",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            legacy_service=_FailingService(),
        )

    assert resolver_called == []
    assert service_called == []


def test_context_resolves_once_in_shadow_and_canonical_gets_same_object(monkeypatch: pytest.MonkeyPatch) -> None:
    context = KommunDayBusinessContext(
        tenant_id=1,
        site_id="site-1",
        site_name="Shadow Site",
        service_date="2026-09-07",
        departments=(
            KommunDepartmentProjectionContext(department_id="dep-a", department_name="Alpha"),
        ),
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        lunch_baselines={"dep-a": 10},
        dinner_baselines={"dep-a": 8},
        requirement_projection_by_group_id={},
    )
    resolve_calls: list[KommunDayBusinessContext] = []
    canonical_calls: list[KommunDayBusinessContext] = []
    legacy_service = _RecordingLegacyService(
        {
            "departments": [
                {
                    "department_id": "dep-a",
                    "department_name": "Alpha",
                    "meals": {
                        "lunch": {"residents_total": 10, "special_diets": [], "normal_diet_count": 10},
                        "dinner": {"residents_total": 8, "special_diets": [], "normal_diet_count": 8},
                    },
                }
            ],
            "totals": {
                "lunch": {"residents_total": 10, "special_diets": [], "normal_diet_count": 10},
                "dinner": {"residents_total": 8, "special_diets": [], "normal_diet_count": 8},
            },
        }
    )

    def _resolve(**kwargs: object) -> KommunDayBusinessContext:
        resolve_calls.append(context)
        return context

    def _canonical(candidate: KommunDayBusinessContext) -> dict[str, object]:
        canonical_calls.append(candidate)
        assert candidate is context
        return _route_payload_from_context(context, legacy_service.payload)

    monkeypatch.setattr("core.kommun_planera_day_application.resolve_kommun_day_business_context", _resolve)
    monkeypatch.setattr("core.kommun_planera_day_application.run_canonical_kommun_day", _canonical)

    result = run_kommun_day_application(
        mode="shadow",
        tenant_id=1,
        site_id="site-1",
        service_date="2026-09-07",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        legacy_service=legacy_service,
    )

    assert result == _route_payload_from_context(context, legacy_service.payload)
    assert resolve_calls == [context]
    assert canonical_calls == [context]


def test_new_canonical_runtime_modules_do_not_import_planera_service() -> None:
    import core.planera_v2.adapters.kommun_day_projection as projection_module
    import core.planera_v2.day_context_resolver as resolver_module
    import core.planera_v2.day_orchestration as orchestration_module
    import core.planera_v2.kommun_day_application as application_module

    for module in (projection_module, resolver_module, orchestration_module, application_module):
        source = inspect.getsource(module)
        assert "PlaneraService" not in source


def test_module_has_no_feature_flag_or_alt_references() -> None:
    source = inspect.getsource(__import__("core.kommun_planera_day_application", fromlist=["*"]))
    assert "feature_registry" not in source
    assert "feature_enabled" not in source
    assert "ff." not in source
    assert "Alt1" not in source
    assert "Alt2" not in source
