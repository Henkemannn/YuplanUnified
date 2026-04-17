from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Deviation:
    form: str
    category_key: str | None = None
    category_keys: tuple[str, ...] = ()
    quantity: int = 0
    unit_id: str | None = None


@dataclass(frozen=True)
class PlanRequest:
    baseline: int = 0
    deviations: tuple[Deviation, ...] = ()
    context: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class PlanResult:
    totals: dict[str, int]
    per_form: dict[str, int]
    per_combination: dict[str, int]
    per_unit: dict[str, int]
    warnings: list[str]
