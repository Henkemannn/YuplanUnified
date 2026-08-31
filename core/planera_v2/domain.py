from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Deviation:
    form: str
    category_keys: list[str] = field(default_factory=list)
    quantity: int = 0
    unit_id: str | None = None


@dataclass(frozen=True)
class UnitInput:
    unit_id: str
    baseline_total: int = 0


@dataclass(frozen=True)
class PlanRequest:
    baseline: int = 0
    units: list[UnitInput] = field(default_factory=list)
    deviations: list[Deviation] = field(default_factory=list)
    context: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlanningSlice:
    baseline: int = 0
    units: tuple[UnitInput, ...] = ()
    deviations: tuple[Deviation, ...] = ()
    context: dict[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    compatibility_status: str = "resolved"

    def to_plan_request(self) -> PlanRequest:
        context = dict(self.context)
        context["compatibility_status"] = self.compatibility_status
        context["compatibility_warnings"] = list(self.warnings)
        return PlanRequest(
            baseline=int(self.baseline),
            units=list(self.units),
            deviations=list(self.deviations),
            context=context,
        )


@dataclass(frozen=True)
class Totals:
    baseline_total: int = 0
    deviation_total: int = 0
    normal_total: int = 0


@dataclass(frozen=True)
class UnitBreakdown:
    baseline_total: int = 0
    deviation_total: int = 0
    normal_total: int = 0
    per_combination: dict[str, int] = field(default_factory=dict)
    per_form: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class PlanResult:
    totals: Totals
    per_form: dict[str, int] = field(default_factory=dict)
    per_combination: dict[str, int] = field(default_factory=dict)
    per_unit: dict[str, int] = field(default_factory=dict)
    per_unit_breakdown: dict[str, UnitBreakdown] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
