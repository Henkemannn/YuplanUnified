from __future__ import annotations

from typing import Mapping

from .day_context_resolver import resolve_kommun_day_business_context
from .day_orchestration import run_canonical_kommun_day


def run_resolved_canonical_kommun_day(
    *,
    tenant_id: int | str,
    site_id: str,
    service_date,
    meal_labels: Mapping[str, str],
    department_id: str | None = None,
) -> dict[str, object]:
    context = resolve_kommun_day_business_context(
        tenant_id=tenant_id,
        site_id=site_id,
        service_date=service_date,
        meal_labels=meal_labels,
        department_id=department_id,
    )
    return run_canonical_kommun_day(context)


__all__ = ["run_resolved_canonical_kommun_day"]