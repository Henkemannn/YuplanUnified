from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .adapters.kommun_day_projection import (
    KommunDepartmentProjectionContext,
    RequirementGroupProjection,
    project_canonical_kommun_day,
)
from .shadow import ProductionShadowRun, run_canonical_requirement_groups_in_production_shadow


@dataclass(frozen=True, slots=True)
class KommunGroupCompatibilityMetadata:
    group_id: str
    diet_name: str


@dataclass(frozen=True, slots=True)
class KommunDayBusinessContext:
    tenant_id: int | str
    site_id: str
    site_name: str
    service_date: str
    departments: tuple[KommunDepartmentProjectionContext, ...]
    meal_labels: Mapping[str, str]
    lunch_baselines: Mapping[str, int]
    dinner_baselines: Mapping[str, int]
    requirement_projection_by_group_id: Mapping[str, KommunGroupCompatibilityMetadata]

    def __post_init__(self) -> None:
        object.__setattr__(self, "site_id", str(self.site_id).strip())
        object.__setattr__(self, "site_name", str(self.site_name).strip())
        object.__setattr__(self, "service_date", str(self.service_date).strip())
        object.__setattr__(self, "departments", tuple(self.departments))
        object.__setattr__(self, "meal_labels", MappingProxyType(dict(self.meal_labels)))
        object.__setattr__(self, "lunch_baselines", MappingProxyType(dict(self.lunch_baselines)))
        object.__setattr__(self, "dinner_baselines", MappingProxyType(dict(self.dinner_baselines)))
        object.__setattr__(
            self,
            "requirement_projection_by_group_id",
            MappingProxyType(dict(self.requirement_projection_by_group_id)),
        )


class KommunDayOrchestrationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = str(code)
        self.message = str(message)
        super().__init__(f"{self.code}: {self.message}")


def _normalize_id(value: object) -> str:
    return str(value or "").strip()


def _ordered_expected_unit_ids(
    departments: Sequence[KommunDepartmentProjectionContext],
) -> tuple[str, ...]:
    expected_unit_ids: list[str] = []
    seen: set[str] = set()
    for department in departments:
        department_id = _normalize_id(department.department_id)
        if not department_id:
            raise KommunDayOrchestrationError("missing_department_id", "department id is blank")
        if department_id in seen:
            raise KommunDayOrchestrationError("duplicate_department_id", f"duplicate department id: {department_id}")
        seen.add(department_id)
        expected_unit_ids.append(department_id)
    return tuple(expected_unit_ids)


def _require_meal_labels(meal_labels: Mapping[str, str]) -> dict[str, str]:
    lunch_label = _normalize_id(meal_labels.get("lunch"))
    dinner_label = _normalize_id(meal_labels.get("dinner"))
    if not lunch_label:
        raise KommunDayOrchestrationError("missing_meal_label", "lunch label missing")
    if not dinner_label:
        raise KommunDayOrchestrationError("missing_meal_label", "dinner label missing")
    return {"lunch": lunch_label, "dinner": dinner_label}


def _build_requirement_projections(
    requirement_projection_by_group_id: Mapping[str, KommunGroupCompatibilityMetadata],
) -> dict[str, RequirementGroupProjection]:
    projections: dict[str, RequirementGroupProjection] = {}
    for group_id, metadata in requirement_projection_by_group_id.items():
        normalized_group_id = _normalize_id(group_id)
        if not normalized_group_id:
            raise KommunDayOrchestrationError("missing_group_id", "compatibility group id is blank")
        if not isinstance(metadata, KommunGroupCompatibilityMetadata):
            raise KommunDayOrchestrationError("missing_group_label", f"invalid compatibility metadata for group {normalized_group_id}")
        if _normalize_id(metadata.group_id) != normalized_group_id:
            raise KommunDayOrchestrationError("missing_group_id", f"compatibility metadata group id mismatch for {normalized_group_id}")
        diet_name = _normalize_id(metadata.diet_name)
        if not diet_name:
            raise KommunDayOrchestrationError("missing_group_label", f"missing display label for group {normalized_group_id}")
        projections[normalized_group_id] = RequirementGroupProjection(
            group_id=normalized_group_id,
            diet_type_id=f"group:{normalized_group_id}",
            diet_name=diet_name,
        )
    return projections


def _shadow_run(
    *,
    context: KommunDayBusinessContext,
    meal_key: str,
    expected_unit_ids: tuple[str, ...],
    baselines: Mapping[str, int],
) -> ProductionShadowRun:
    return run_canonical_requirement_groups_in_production_shadow(
        site_id=context.site_id,
        service_date=context.service_date,
        meal_key=meal_key,
        unit_baselines=dict(baselines),
        expected_unit_ids=expected_unit_ids,
    )


def run_canonical_kommun_day(context: KommunDayBusinessContext) -> dict[str, object]:
    expected_unit_ids = _ordered_expected_unit_ids(context.departments)
    meal_labels = _require_meal_labels(context.meal_labels)
    requirement_projection_by_group_id = _build_requirement_projections(context.requirement_projection_by_group_id)

    lunch_run = _shadow_run(
        context=context,
        meal_key="lunch",
        expected_unit_ids=expected_unit_ids,
        baselines=context.lunch_baselines,
    )
    dinner_run = _shadow_run(
        context=context,
        meal_key="dinner",
        expected_unit_ids=expected_unit_ids,
        baselines=context.dinner_baselines,
    )

    return project_canonical_kommun_day(
        site_id=context.site_id,
        site_name=context.site_name,
        service_date=context.service_date,
        meal_labels=meal_labels,
        departments=context.departments,
        meal_runs={"lunch": lunch_run, "dinner": dinner_run},
        requirement_projection_by_group_id=requirement_projection_by_group_id,
    )


__all__ = [
    "KommunDayBusinessContext",
    "KommunDayOrchestrationError",
    "KommunDepartmentProjectionContext",
    "KommunGroupCompatibilityMetadata",
    "RequirementGroupProjection",
    "run_canonical_kommun_day",
]
