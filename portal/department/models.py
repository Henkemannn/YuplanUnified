"""Department Portal Week Payload Models

This module defines the typed structures for the Department Portal
composite week payload documented in `docs/department_portal_week_schema.md`.

Phase 1 is read-only: no mutation logic is implemented here.
The mutation contract is pre-defined for future phases.
"""

from typing import TypedDict, Literal, List, Dict, Optional

SelectedAlt = Optional[Literal["Alt1", "Alt2"]]


class DietSummaryItem(TypedDict):
    diet_type_id: str
    diet_name: str
    count: int


class ResidentsSummary(TypedDict):
    lunch: int
    dinner: int


class DietsSummary(TypedDict):
    lunch: List[DietSummaryItem]
    dinner: List[DietSummaryItem]


class DayMenu(TypedDict):
    lunch_alt1: Optional[str]
    lunch_alt2: Optional[str]
    dessert: Optional[str]
    dinner: Optional[str]


class DayChoice(TypedDict):
    selected_alt: SelectedAlt


class DayFlags(TypedDict):
    alt2_lunch: bool


class PortalDay(TypedDict):
    date: str
    weekday_name: str
    menu: DayMenu
    choice: DayChoice
    flags: DayFlags
    residents: ResidentsSummary
    diets_summary: DietsSummary


class PortalFacts(TypedDict, total=False):
    note: Optional[str]
    residents_default_lunch: Optional[int]
    residents_default_dinner: Optional[int]


class PortalProgress(TypedDict):
    days_with_choice: int
    total_days: int


class PortalEtagMap(TypedDict):
    menu_choice: str
    weekview: str


class DepartmentPortalWeekPayload(TypedDict):
    """Composite payload returned by GET /portal/department/week.

    See docs/department_portal_week_schema.md for the authoritative
    contract. This structure is intentionally decoupled from existing
    weekview/planera internal models to allow portal-specific evolution.
    """

    department_id: str
    department_name: str
    site_id: str
    site_name: str
    year: int
    week: int
    facts: PortalFacts
    progress: PortalProgress
    etag_map: PortalEtagMap
    days: List[PortalDay]


def validate_portal_week_payload(payload: DepartmentPortalWeekPayload) -> None:
    """Basic structural validation for DepartmentPortalWeekPayload.

    Phase 1 performs minimal checks; deeper semantic validation will be
    added when the endpoint implementation materializes.
    Raises ValueError if required top-level keys are missing.
    """

    required_keys = {
        "department_id",
        "department_name",
        "site_id",
        "site_name",
        "year",
        "week",
        "facts",
        "progress",
        "etag_map",
        "days",
    }
    missing = required_keys.difference(payload.keys())
    if missing:
        raise ValueError(
            f"Missing keys in DepartmentPortalWeekPayload: {', '.join(sorted(missing))}"  # noqa: E501
        )
