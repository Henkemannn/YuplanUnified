from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from datetime import date as _today_date
from typing import Any

from sqlalchemy import text

from .db import get_session


_WEEKDAY_NAMES = {
    1: "måndag",
    2: "tisdag",
    3: "onsdag",
    4: "torsdag",
    5: "fredag",
    6: "lördag",
    7: "söndag",
}

_MONTH_NAMES = [
    "januari",
    "februari",
    "mars",
    "april",
    "maj",
    "juni",
    "juli",
    "augusti",
    "september",
    "oktober",
    "november",
    "december",
]


@dataclass(frozen=True, slots=True)
class RequirementCountViolation:
    group_id: str
    group_name: str
    quantity: int
    resident_count: int
    scope: str
    service_date: _date | None = None
    weekday: int | None = None
    meal_key: str | None = None


class RequirementCountExceededError(ValueError):
    def __init__(self, violation: RequirementCountViolation):
        self.violation = violation
        super().__init__("requirement_count_exceeds_resident_count")


def _department_fixed_resident_count(db, department_id: str) -> int:
    row = db.execute(
        text("SELECT COALESCE(resident_count_fixed, 0) FROM departments WHERE id=:id LIMIT 1"),
        {"id": str(department_id)},
    ).fetchone()
    return int(row[0] or 0) if row else 0


def _group_display_name(group: dict[str, Any]) -> str:
    label = str(group.get("label") or "").strip()
    if label:
        return label
    requirement_names = [str(item.get("name") or "").strip() for item in group.get("requirements") or [] if str(item.get("name") or "").strip()]
    if requirement_names:
        return " + ".join(requirement_names)
    return "Registrerat behov"


def _meal_label(meal_key: str | None) -> str:
    return "kväll" if str(meal_key or "").strip().lower() == "dinner" else "lunch"


def _weekday_label(weekday: int | None) -> str:
    return _WEEKDAY_NAMES.get(int(weekday or 0), str(weekday or ""))


def _exact_date_label(service_date: _date | None) -> str:
    if service_date is None:
        return ""
    return f"{service_date.day} {_MONTH_NAMES[service_date.month - 1]}"


def format_requirement_count_violation(violation: RequirementCountViolation) -> str:
    group_name = violation.group_name or "Registrerat behov"
    if violation.scope == "total":
        if violation.service_date is not None or violation.weekday is not None or violation.meal_key is not None:
            day_label = _weekday_label(violation.weekday or (violation.service_date.isoweekday() if violation.service_date is not None else 0))
            meal_label = _meal_label(violation.meal_key)
            return (
                f"På {day_label} {meal_label} är {int(violation.quantity)} personer registrerade med kostbehov, men avdelningen har "
                f"{int(violation.resident_count)} boende."
            )
        return (
            f"Registrerade kostbehov blir totalt {int(violation.quantity)} personer, men avdelningen har "
            f"{int(violation.resident_count)} boende."
        )
    if violation.scope in {"default", "fixed"}:
        return f"Antalet för {group_name} kan inte vara högre än avdelningens {int(violation.resident_count)} boende."
    if violation.scope == "exact" and violation.service_date is not None:
        return (
            f"Antalet för {group_name} kan inte vara högre än {int(violation.resident_count)} boende "
            f"den {_exact_date_label(violation.service_date)} {_meal_label(violation.meal_key)}."
        )
    if violation.service_date is not None:
        return (
            f"Antalet för {group_name} kan inte vara högre än {int(violation.resident_count)} boende "
            f"på {_weekday_label(violation.weekday or violation.service_date.isoweekday())} {_meal_label(violation.meal_key)}."
        )
    if violation.weekday is not None:
        return (
            f"Antalet för {group_name} kan inte vara högre än {int(violation.resident_count)} boende "
            f"på {_weekday_label(violation.weekday)} {_meal_label(violation.meal_key)}."
        )
    return f"Antalet för {group_name} kan inte vara högre än avdelningens {int(violation.resident_count)} boende."


def _raise_violation(*, group: dict[str, Any], quantity: int, resident_count: int, scope: str, service_date: _date | None = None, weekday: int | None = None, meal_key: str | None = None) -> None:
    raise RequirementCountExceededError(
        RequirementCountViolation(
            group_id=str(group.get("id") or ""),
            group_name=_group_display_name(group),
            quantity=int(quantity),
            resident_count=int(resident_count),
            scope=scope,
            service_date=service_date,
            weekday=weekday,
            meal_key=meal_key,
        )
    )


def assert_group_default_quantity_within_department(group: dict[str, Any], resident_count: int) -> None:
    if int(group.get("default_quantity") or 0) > int(resident_count):
        _raise_violation(group=group, quantity=int(group.get("default_quantity") or 0), resident_count=resident_count, scope="default")


def assert_weekday_quantity_within_department(group: dict[str, Any], *, weekday: int, meal_key: str, quantity: int, resident_count: int) -> None:
    if int(quantity) > int(resident_count):
        _raise_violation(
            group=group,
            quantity=int(quantity),
            resident_count=resident_count,
            scope="weekday",
            weekday=int(weekday),
            meal_key=str(meal_key),
        )


def assert_exact_quantity_within_department(group: dict[str, Any], *, service_date: _date, meal_key: str, quantity: int, resident_count: int) -> None:
    if int(quantity) > int(resident_count):
        _raise_violation(
            group=group,
            quantity=int(quantity),
            resident_count=resident_count,
            scope="exact",
            service_date=service_date,
            meal_key=str(meal_key),
        )


def collect_active_group_violations_against_fixed_count(department_id: str, resident_count: int) -> list[RequirementCountViolation]:
    from .department_requirement_group_repo import DepartmentRequirementGroupsRepo
    from .department_requirement_group_service_overrides_repo import DepartmentRequirementGroupServiceOverridesRepo
    from .department_requirement_group_weekday_overrides_repo import DepartmentRequirementGroupWeekdayOverridesRepo

    groups = [group for group in DepartmentRequirementGroupsRepo().list_for_department(department_id) if bool(group.get("is_active"))]
    violations: list[RequirementCountViolation] = []
    weekday_repo = DepartmentRequirementGroupWeekdayOverridesRepo()
    exact_repo = DepartmentRequirementGroupServiceOverridesRepo()
    for group in groups:
        if int(group.get("default_quantity") or 0) > int(resident_count):
            violations.append(
                RequirementCountViolation(
                    group_id=str(group.get("id") or ""),
                    group_name=_group_display_name(group),
                    quantity=int(group.get("default_quantity") or 0),
                    resident_count=int(resident_count),
                    scope="default",
                )
            )
            continue
        for row in weekday_repo.list_for_group(str(group.get("id") or "")):
            quantity = int(row.get("quantity") or 0)
            if quantity > int(resident_count):
                violations.append(
                    RequirementCountViolation(
                        group_id=str(group.get("id") or ""),
                        group_name=_group_display_name(group),
                        quantity=quantity,
                        resident_count=int(resident_count),
                        scope="weekday",
                        weekday=int(row.get("weekday") or 0),
                        meal_key=str(row.get("meal_key") or ""),
                    )
                )
                break
        if violations:
            continue
        for row in exact_repo.list_for_group(str(group.get("id") or "")):
            quantity = int(row.get("quantity") or 0)
            if quantity > int(resident_count):
                service_date = _date.fromisoformat(str(row.get("service_date") or ""))
                violations.append(
                    RequirementCountViolation(
                        group_id=str(group.get("id") or ""),
                        group_name=_group_display_name(group),
                        quantity=quantity,
                        resident_count=int(resident_count),
                        scope="exact",
                        service_date=service_date,
                        meal_key=str(row.get("meal_key") or ""),
                    )
                )
                break
        if violations:
            continue
    return violations


def _weekday_group_quantity_in_session(db, group_id: str, weekday: int, meal_key: str) -> int:
    group_row = db.execute(
        text(
            """
            SELECT default_quantity, is_active
            FROM department_requirement_groups
            WHERE id=:group_id
            """
        ),
        {"group_id": str(group_id)},
    ).fetchone()
    if group_row is None or not bool(group_row[1]):
        return 0
    override_row = db.execute(
        text(
            """
            SELECT quantity
            FROM department_requirement_group_weekday_overrides
            WHERE group_id=:group_id AND weekday=:weekday AND meal_key=:meal_key
            """
        ),
        {"group_id": str(group_id), "weekday": int(weekday), "meal_key": str(meal_key)},
    ).fetchone()
    if override_row is not None:
        return int(override_row[0] or 0)
    return int(group_row[0] or 0)


def _resident_counts_for_context_in_session(db, *, department_id: str, year: int, week: int, weekday: int) -> dict[str, int]:
    try:
        week_rows = db.execute(
            text(
                """
                SELECT weekday, meal, count
                FROM department_residents_schedule
                WHERE department_id=:department_id AND week=:week
                """
            ),
            {"department_id": str(department_id), "week": int(week)},
        ).fetchall()
    except Exception:
        week_rows = []
    week_map: dict[tuple[int, str], int] = {}
    for row in week_rows:
        try:
            week_map[(int(row[0]), str(row[1]))] = int(row[2] or 0)
        except Exception:
            continue
    try:
        forever_rows = db.execute(
            text(
                """
                SELECT weekday, meal, count
                FROM department_residents_schedule
                WHERE department_id=:department_id AND week IS NULL
                """
            ),
            {"department_id": str(department_id)},
        ).fetchall()
    except Exception:
        forever_rows = []
    forever_map: dict[tuple[int, str], int] = {}
    for row in forever_rows:
        try:
            forever_map[(int(row[0]), str(row[1]))] = int(row[2] or 0)
        except Exception:
            continue
    row = db.execute(
        text("SELECT COALESCE(resident_count_fixed,0) FROM departments WHERE id=:department_id"),
        {"department_id": str(department_id)},
    ).fetchone()
    fixed = int(row[0] or 0) if row else 0
    try:
        week_override = db.execute(
            text(
                """
                SELECT residents_lunch, residents_dinner
                FROM department_residents_weekly
                WHERE department_id=:department_id AND year=:year AND week=:week
                """
            ),
            {"department_id": str(department_id), "year": int(year), "week": int(week)},
        ).fetchone()
    except Exception:
        week_override = None
    lunch = int((week_override[0] if week_override else None) or fixed)
    dinner = int((week_override[1] if week_override else None) or fixed)
    if (weekday, "lunch") in week_map or (weekday, "dinner") in week_map:
        return {"lunch": int(week_map.get((weekday, "lunch"), 0)), "dinner": int(week_map.get((weekday, "dinner"), 0))}
    if (weekday, "lunch") in forever_map or (weekday, "dinner") in forever_map:
        return {"lunch": int(forever_map.get((weekday, "lunch"), 0)), "dinner": int(forever_map.get((weekday, "dinner"), 0))}
    return {"lunch": lunch, "dinner": dinner}


def collect_active_group_context_violations_in_session(db, department_id: str) -> list[RequirementCountViolation]:
    from .department_requirement_group_quantity_resolver import resolve_effective_quantity_in_session

    group_rows = db.execute(
        text(
            """
            SELECT id, default_quantity, is_active, label
            FROM department_requirement_groups
            WHERE department_id=:department_id
            ORDER BY id ASC
            """
        ),
        {"department_id": str(department_id)},
    ).fetchall()
    active_groups = [row for row in group_rows if bool(row[2])]
    if not active_groups:
        return []

    violations: list[RequirementCountViolation] = []
    fixed_resident_count = _department_fixed_resident_count(db, department_id)
    fixed_total = sum(int(row[1] or 0) for row in active_groups)
    if fixed_total > fixed_resident_count:
        violations.append(
            RequirementCountViolation(
                group_id="",
                group_name="Registrerade kostbehov",
                quantity=int(fixed_total),
                resident_count=int(fixed_resident_count),
                scope="total",
            )
        )

    current_year = _today_date.today().isocalendar()[0]
    try:
        schedule_rows = db.execute(
            text("SELECT DISTINCT week FROM department_residents_schedule WHERE department_id=:department_id AND week IS NOT NULL"),
            {"department_id": str(department_id)},
        ).fetchall()
    except Exception:
        schedule_rows = []
    schedule_weeks = {
        int(row[0])
        for row in schedule_rows
        if row and row[0] is not None
    }
    try:
        weekly_rows = db.execute(
            text("SELECT DISTINCT year, week FROM department_residents_weekly WHERE department_id=:department_id"),
            {"department_id": str(department_id)},
        ).fetchall()
    except Exception:
        weekly_rows = []
    weekly_contexts = {
        (int(row[0]), int(row[1]))
        for row in weekly_rows
        if row and row[0] is not None and row[1] is not None
    }
    if not schedule_weeks and not weekly_contexts:
        schedule_weeks = {int(_today_date.today().isocalendar()[1])}

    def _week_contexts() -> list[tuple[int, int]]:
        contexts: list[tuple[int, int]] = [(current_year, week) for week in sorted(schedule_weeks)]
        contexts.extend(sorted(weekly_contexts))
        return contexts

    for year, week in _week_contexts():
        for weekday in range(1, 8):
            residents = _resident_counts_for_context_in_session(db, department_id=department_id, year=year, week=week, weekday=weekday)
            service_date = _date.fromisocalendar(int(year), int(week), int(weekday))
            for meal_key in ("lunch", "dinner"):
                proposed_total = 0
                for row in active_groups:
                    proposed_total += _weekday_group_quantity_in_session(db, str(row[0]), weekday, meal_key)
                if proposed_total > int(residents.get(meal_key) or 0):
                    violations.append(
                        RequirementCountViolation(
                            group_id="",
                            group_name="Registrerade kostbehov",
                            quantity=int(proposed_total),
                            resident_count=int(residents.get(meal_key) or 0),
                            scope="total",
                            service_date=service_date,
                            weekday=weekday,
                            meal_key=meal_key,
                        )
                    )
                    break

    exact_rows = db.execute(
        text(
            """
            SELECT DISTINCT o.service_date, o.meal_key
            FROM department_requirement_group_service_overrides o
            JOIN department_requirement_groups g ON g.id = o.group_id
            WHERE g.department_id=:department_id AND g.is_active=1
            ORDER BY o.service_date ASC, o.meal_key ASC
            """
        ),
        {"department_id": str(department_id)},
    ).fetchall()
    for row in exact_rows:
        try:
            service_date = _date.fromisoformat(str(row[0]))
        except Exception:
            continue
        meal_key = str(row[1])
        year, week, weekday = service_date.isocalendar()
        resident_counts = _resident_counts_for_context_in_session(db, department_id=department_id, year=year, week=week, weekday=weekday)
        proposed_total = 0
        for group_row in active_groups:
            proposed_total += int(
                resolve_effective_quantity_in_session(
                    db,
                    str(group_row[0]),
                    service_date,
                    meal_key,
                )
            )
        if proposed_total > int(resident_counts.get(meal_key) or 0):
            violations.append(
                RequirementCountViolation(
                    group_id="",
                    group_name="Registrerade kostbehov",
                    quantity=int(proposed_total),
                    resident_count=int(resident_counts.get(meal_key) or 0),
                    scope="total",
                    service_date=service_date,
                    weekday=weekday,
                    meal_key=meal_key,
                )
            )

    return violations


def format_requirement_count_violations(violations: list[RequirementCountViolation]) -> str:
    if not violations:
        return ""
    if len(violations) == 1:
        return format_requirement_count_violation(violations[0])
    lines = [f"Ändringen skapar konflikter i {len(violations)} måltider."]
    for violation in violations[:4]:
        if violation.service_date is not None:
            context_label = f"{_weekday_label(violation.weekday or violation.service_date.isoweekday())} {_meal_label(violation.meal_key)}"
        elif violation.weekday is not None:
            context_label = f"{_weekday_label(violation.weekday)} {_meal_label(violation.meal_key)}"
        else:
            context_label = "Normalläge"
        lines.append(f"{context_label}: {int(violation.quantity)} kostbehov · {int(violation.resident_count)} boende")
    if len(violations) > 4:
        lines.append(f"… och {len(violations) - 4} till.")
    return "<br>".join(lines)


def collect_active_group_violations_for_week(department_id: str, *, year: int, week: int) -> list[RequirementCountViolation]:
    from .department_requirement_group_quantity_resolver import resolve_effective_quantity
    from .department_requirement_group_repo import DepartmentRequirementGroupsRepo
    from .weekview.service import resolve_effective_resident_counts_for_day

    groups = [group for group in DepartmentRequirementGroupsRepo().list_for_department(department_id) if bool(group.get("is_active"))]
    violations: list[RequirementCountViolation] = []
    for weekday in range(1, 8):
        day_context = resolve_effective_resident_counts_for_day(department_id, year, week, weekday)
        resident_counts = {
            "lunch": int(day_context.get("lunch") or 0),
            "dinner": int(day_context.get("dinner") or 0),
        }
        service_date = _date.fromisocalendar(int(year), int(week), weekday)
        for group in groups:
            group_id = str(group.get("id") or "")
            for meal_key in ("lunch", "dinner"):
                actual = int(resolve_effective_quantity(group_id, service_date, meal_key) or 0)
                allowed = int(resident_counts[meal_key])
                if actual > allowed:
                    violations.append(
                        RequirementCountViolation(
                            group_id=group_id,
                            group_name=_group_display_name(group),
                            quantity=actual,
                            resident_count=allowed,
                            scope="week",
                            service_date=service_date,
                            weekday=weekday,
                            meal_key=meal_key,
                        )
                    )
                    return violations
    return violations


def resident_count_violation_message(violation: RequirementCountViolation) -> str:
    return format_requirement_count_violation(violation)


def department_fixed_resident_count(department_id: str) -> int:
    db = get_session()
    try:
        return _department_fixed_resident_count(db, department_id)
    finally:
        db.close()


def resolve_effective_special_diet_total_in_session(
    db,
    department_id: str,
    *,
    service_date: _date | None = None,
    year: int | None = None,
    week: int | None = None,
    weekday: int | None = None,
    meal_key: str | None = None,
    overrides: dict[str, int] | None = None,
) -> int:
    from .department_requirement_group_quantity_resolver import resolve_effective_quantity_in_session

    if service_date is None and year is not None and week is not None and weekday is not None:
        service_date = _date.fromisocalendar(int(year), int(week), int(weekday))

    rows = db.execute(
        text(
            """
            SELECT id, default_quantity, is_active, label
            FROM department_requirement_groups
            WHERE department_id=:department_id
            ORDER BY id ASC
            """
        ),
        {"department_id": str(department_id)},
    ).fetchall()
    total = 0
    override_map = {str(key): int(value) for key, value in (overrides or {}).items()}
    for row in rows:
        group_id = str(row[0])
        if not bool(row[2]):
            continue
        if group_id in override_map:
            total += int(override_map[group_id])
            continue
        if service_date is None:
            total += int(row[1] or 0)
        else:
            total += int(
                    resolve_effective_quantity_in_session(db, group_id, service_date, meal_key)
            )
    return total


def validate_special_diet_total_in_session(
    db,
    department_id: str,
    *,
    resident_count: int,
    expected_total: int | None = None,
    service_date: _date | None = None,
    year: int | None = None,
    week: int | None = None,
    weekday: int | None = None,
    meal_key: str | None = None,
    overrides: dict[str, int] | None = None,
) -> None:
    total = int(expected_total) if expected_total is not None else resolve_effective_special_diet_total_in_session(
        db,
        department_id,
        service_date=service_date,
        year=year,
        week=week,
        weekday=weekday,
        meal_key=meal_key,
        overrides=overrides,
    )
    if total > int(resident_count):
        raise RequirementCountExceededError(
            RequirementCountViolation(
                group_id="",
                group_name="Registrerade kostbehov",
                quantity=int(total),
                resident_count=int(resident_count),
                scope="total",
                service_date=service_date,
                weekday=weekday,
                meal_key=meal_key,
            )
        )
