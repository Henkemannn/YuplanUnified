from __future__ import annotations

from collections import defaultdict
from csv import DictReader
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import re

from .importers.base import ImportedMenuItem, MenuImportResult, WeekImport


_DAY_ORDER = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_DAY_MAP = {
    "måndag": "monday",
    "mandag": "monday",
    "mån": "monday",
    "monday": "monday",
    "tisdag": "tuesday",
    "tirsdag": "tuesday",
    "tis": "tuesday",
    "tuesday": "tuesday",
    "onsdag": "wednesday",
    "ons": "wednesday",
    "wednesday": "wednesday",
    "torsdag": "thursday",
    "tor": "thursday",
    "thursday": "thursday",
    "fredag": "friday",
    "fre": "friday",
    "friday": "friday",
    "lördag": "saturday",
    "lørdag": "saturday",
    "lör": "saturday",
    "sat": "saturday",
    "saturday": "saturday",
    "söndag": "sunday",
    "søndag": "sunday",
    "sön": "sunday",
    "sun": "sunday",
    "sunday": "sunday",
}

_MEAL_MAP = {
    "lunch": "lunch",
    "middag": "dinner",
    "dinner": "dinner",
}

_CATEGORY_VARIANT_ORDER = {
    "kjott": ("main", 0),
    "kjøtt": ("main", 0),
    "fisk": ("alt1", 1),
    "suppe": ("alt2", 2),
}

_INTENTIONAL_GAPS = {
    (2, "sunday", "lunch"): {"suppe"},
    (3, "wednesday", "lunch"): {"kjott"},
}


@dataclass(frozen=True)
class _ParsedDemoMenuRow:
    week: int
    day: str
    meal: str
    category: str
    category_order: int
    variant_type: str
    dish_name: str


def demo_menu_csv_path() -> Path:
    return Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "meny_ai_long_uniform.csv"


def build_demo_menu_import_result(*, csv_path: Path, anchor_day: date) -> MenuImportResult:
    raw_weeks = _parse_demo_menu_csv(csv_path)
    if len(raw_weeks) != 4:
        raise ValueError(f"expected 4 weeks in demo CSV, got {len(raw_weeks)}")

    week_numbers = sorted(raw_weeks)
    weeks: list[WeekImport] = []
    for offset, csv_week in enumerate(week_numbers):
        target_day = anchor_day + timedelta(weeks=offset)
        iso_year, iso_week, *_ = target_day.isocalendar()
        items = sorted(raw_weeks[csv_week], key=_row_sort_key)
        weeks.append(
            WeekImport(
                year=int(iso_year),
                week=int(iso_week),
                items=[
                    ImportedMenuItem(
                        day=row.day,
                        meal=row.meal,
                        variant_type=row.variant_type,
                        dish_name=row.dish_name,
                        category=row.category,
                        source_labels=[f"CSV uke {csv_week}", row.category],
                    )
                    for row in items
                ],
            )
        )

    return MenuImportResult(weeks=weeks)


def _parse_demo_menu_csv(csv_path: Path) -> dict[int, list[_ParsedDemoMenuRow]]:
    if not csv_path.exists():
        raise FileNotFoundError(str(csv_path))

    buckets: dict[int, list[_ParsedDemoMenuRow]] = defaultdict(list)
    seen_keys: set[tuple[int, str, str, str]] = set()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = DictReader(handle)
        required_headers = {"uke", "dag", "måltid", "kategori", "rett"}
        if not reader.fieldnames:
            raise ValueError("demo csv missing header")
        normalized_headers = {str(field or "").strip().lower() for field in reader.fieldnames}
        if not required_headers.issubset(normalized_headers):
            missing = ", ".join(sorted(required_headers - normalized_headers))
            raise ValueError(f"demo csv missing required columns: {missing}")

        for row_index, row in enumerate(reader, start=2):
            normalized = {str(key or "").strip().lower(): str(value or "").strip() for key, value in row.items()}
            if not any(normalized.values()):
                continue

            week_value = _parse_week(normalized.get("uke"), row_index)
            day_value = _normalize_day(normalized.get("dag"), row_index)
            meal_value = _normalize_meal(normalized.get("måltid"), row_index)
            category_value = _normalize_category(normalized.get("kategori"), row_index)
            dish_name = str(normalized.get("rett") or "").strip()
            if not dish_name:
                raise ValueError(f"row {row_index}: rett must be non-empty")

            signature = (week_value, day_value, meal_value, category_value)
            if signature in seen_keys:
                raise ValueError(f"row {row_index}: duplicate row for uke/dag/måltid/kategori")
            seen_keys.add(signature)

            variant_type, category_order = _CATEGORY_VARIANT_ORDER[category_value]
            buckets[week_value].append(
                _ParsedDemoMenuRow(
                    week=week_value,
                    day=day_value,
                    meal=meal_value,
                    category=category_value,
                    category_order=category_order,
                    variant_type=variant_type,
                    dish_name=dish_name,
                )
            )

    if not buckets:
        raise ValueError("demo csv did not contain any rows")

    for week_value, rows in buckets.items():
        _validate_week_rows(week_value, rows)

    return buckets


def _validate_week_rows(week: int, rows: list[_ParsedDemoMenuRow]) -> None:
    by_day_meal: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        by_day_meal[(row.day, row.meal)].add(row.category)

    expected_categories = {"kjott", "fisk", "suppe"}
    expected_days = tuple(_DAY_ORDER)
    expected_meals = ("lunch", "dinner")
    for day in expected_days:
        for meal in expected_meals:
            categories = by_day_meal.get((day, meal), set())
            expected_for_slot = expected_categories - _INTENTIONAL_GAPS.get((week, day, meal), set())
            if categories != expected_for_slot:
                missing = sorted(expected_categories - categories)
                extra = sorted(categories - expected_categories)
                raise ValueError(
                    f"week {week}: {day} {meal} must contain categories {sorted(expected_for_slot)}; missing={missing} extra={extra}"
                )


def _row_sort_key(row: _ParsedDemoMenuRow) -> tuple[int, int, int, str]:
    return (
        _DAY_ORDER[row.day],
        0 if row.meal == "lunch" else 1,
        row.category_order,
        row.dish_name.lower(),
    )


def _parse_week(raw_value: str | None, row_index: int) -> int:
    try:
        week_value = int(str(raw_value or "").strip())
    except Exception as exc:
        raise ValueError(f"row {row_index}: uke must be an integer") from exc
    if week_value < 1:
        raise ValueError(f"row {row_index}: uke must be positive")
    return week_value


def _normalize_day(raw_value: str | None, row_index: int) -> str:
    normalized = str(raw_value or "").strip().lower()
    day_value = _DAY_MAP.get(normalized)
    if day_value is None:
        raise ValueError(f"row {row_index}: unsupported dag value {raw_value!r}")
    return day_value


def _normalize_meal(raw_value: str | None, row_index: int) -> str:
    normalized = str(raw_value or "").strip().lower()
    meal_value = _MEAL_MAP.get(normalized)
    if meal_value is None:
        raise ValueError(f"row {row_index}: unsupported måltid value {raw_value!r}")
    return meal_value


def _normalize_category(raw_value: str | None, row_index: int) -> str:
    normalized = str(raw_value or "").strip().lower()
    normalized = normalized.replace("å", "a").replace("ä", "a").replace("ö", "o").replace("ø", "o")
    if normalized == "kjot":
        normalized = "kjott"
    if normalized not in _CATEGORY_VARIANT_ORDER:
        raise ValueError(f"row {row_index}: unsupported kategori value {raw_value!r}")
    return normalized


def _category_role(raw_value: str | None) -> str | None:
    try:
        return _normalize_category(raw_value, 0)
    except Exception:
        return None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
    return slug.strip("-")
