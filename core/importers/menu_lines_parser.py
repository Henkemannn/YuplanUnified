from __future__ import annotations

"""Format-agnostic menu parser

Consumes a list of text lines and produces structured weeks/days/meals.
Strictly recognizes week headers, day headers, and labeled meal lines.
Implements footer detection to stop parsing inside a week.
"""

import re
from typing import List, Tuple

from .base import ImportedMenuItem, MenuImportResult, WeekImport


_WEEK_RE = re.compile(r"^\s*v\.?\s*(\d{1,2})\s*$", re.IGNORECASE)

_FOOTER_TOKENS = [
    "med reservation",
    "ni når oss",
    "allt med röd text",
]
_PHONE_RE = re.compile(r"\b0?7\d[\d\s-]{6,}\b")

_DAY_MAP = {
    # Swedish (full) → canonical short codes used by API/UI
    "måndag": "mon",
    "tisdag": "tue",
    "onsdag": "wed",
    "torsdag": "thu",
    "fredag": "fri",
    "lördag": "sat",
    "söndag": "sun",
    # Swedish (abbrev)
    "mån": "mon",
    "tis": "tue",
    "ons": "wed",
    "tor": "thu",
    "fre": "fri",
    "lör": "sat",
    "sön": "sun",
    # English (full)
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}


def _is_footer_line(line: str) -> bool:
    low = line.strip().lower()
    if any(tok in low for tok in _FOOTER_TOKENS):
        return True
    if _PHONE_RE.search(low):
        return True
    return False


def _detect_week(line: str) -> int | None:
    m = _WEEK_RE.match(line)
    if not m:
        return None
    w = int(m.group(1))
    if 1 <= w <= 53:
        return w
    return None


def _detect_day_header(line: str) -> Tuple[str | None, str]:
    """Return (canonical_day, remainder_after_colon_or_word).

    Accepts Swedish and English day names with optional trailing colon.
    """
    s = line.strip()
    if not s:
        return None, ""
    # Split on the first colon to get a clean remainder if present
    if ":" in s:
        prefix, rest = s.split(":", 1)
        token = prefix.strip().lower()
        day = _DAY_MAP.get(token)
        if day:
            return day, rest.strip()
    # Fallback: first word token
    token = s.split()[0].strip().lower()
    day = _DAY_MAP.get(token)
    if day:
        remainder = s[len(s.split()[0]) :].strip()
        return day, remainder
    return None, ""


_RGX_LUNCH = re.compile(r"^\s*lunch\s*:\s*(.+)$", re.IGNORECASE)
_RGX_MIDDAG = re.compile(r"^\s*middag\s*:\s*(.+)$", re.IGNORECASE)
_RGX_KVALL = re.compile(r"^\s*kväll\s*:\s*(.+)$", re.IGNORECASE)
_RGX_ALT1 = re.compile(r"^\s*(alt\s*1|alternativ\s*1)\s*:\s*(.+)$", re.IGNORECASE)
_RGX_ALT2 = re.compile(r"^\s*(alt\s*2|alternativ\s*2)\s*:\s*(.+)$", re.IGNORECASE)
_RGX_DESSERT = re.compile(r"^\s*dessert\s*:\s*(.+)$", re.IGNORECASE)


def parse_lines(lines: List[str]) -> MenuImportResult:
    """Parse plain text lines into structured weeks/days/meals.

    Strictly recognized content only:
    - Week headers: ^\s*v\.?\s*(\d{1,2})\s*$
    - Day headers: Swedish/English tokens with optional colon
    - Meal lines: Lunch, Kväll, Middag, Alt 1/2, Dessert
    - Footer: stops parsing for current week (continue scanning for next week)
    - After Sunday: only recognized patterns allowed; ignore untyped lines
    """
    weeks: List[WeekImport] = []
    items: List[ImportedMenuItem] = []
    current_week: int | None = None
    current_day: str | None = None
    stop_week: bool = False
    sunday_seen: bool = False

    def _flush_week() -> None:
        nonlocal items, current_week
        if current_week is not None:
            weeks.append(WeekImport(year=_current_year(), week=current_week, items=items))
        items = []

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        w = _detect_week(line)
        if w is not None:
            # Start new week
            if current_week is not None:
                _flush_week()
            current_week = w
            current_day = None
            stop_week = False
            sunday_seen = False
            continue

        # Skip content until a week header appears
        if current_week is None:
            continue

        # Footer detection: hard stop for this week
        if _is_footer_line(line):
            stop_week = True
            continue

        if stop_week:
            # Ignore until next week header
            continue

        # Day header detection
        day, remainder = _detect_day_header(line)
        if day:
            current_day = day
            sunday_seen = sunday_seen or (day == "sunday")
            # If remainder contains a recognized meal line, process it too
            if remainder:
                _maybe_add_item(items, current_day, remainder)
            continue

        # Require an active day context
        if not current_day:
            continue

        # End-of-week guard: after Sunday, only accept recognized patterns
        _maybe_add_item(items, current_day, line)

    # Final flush
    if current_week is not None:
        _flush_week()

    return MenuImportResult(weeks=weeks)


def _maybe_add_item(items: List[ImportedMenuItem], day: str, text: str) -> None:
    s = text.strip()
    if not s:
        return
    # Recognized meal and variant patterns only
    m = _RGX_LUNCH.match(s)
    if m:
        dish = m.group(1).strip()
        if dish:
            items.append(
                ImportedMenuItem(
                    day=day, meal="lunch", variant_type="alt1", dish_name=dish, category="main", source_labels=["lunch"]
                )
            )
        return
    m = _RGX_MIDDAG.match(s)
    if m:
        dish = m.group(1).strip()
        if dish:
            items.append(
                ImportedMenuItem(
                    day=day, meal="dinner", variant_type="evening", dish_name=dish, category="evening", source_labels=["middag"]
                )
            )
        return
    m = _RGX_KVALL.match(s)
    if m:
        dish = m.group(1).strip()
        if dish:
            items.append(
                ImportedMenuItem(
                    day=day, meal="dinner", variant_type="evening", dish_name=dish, category="evening", source_labels=["kväll"]
                )
            )
        return
    m = _RGX_ALT1.match(s)
    if m:
        dish = m.group(2).strip()
        if dish:
            items.append(
                ImportedMenuItem(
                    day=day, meal="lunch", variant_type="alt1", dish_name=dish, category="main", source_labels=["alt1"]
                )
            )
        return
    m = _RGX_ALT2.match(s)
    if m:
        dish = m.group(2).strip()
        if dish:
            items.append(
                ImportedMenuItem(
                    day=day, meal="lunch", variant_type="alt2", dish_name=dish, category="main", source_labels=["alt2"]
                )
            )
        return
    m = _RGX_DESSERT.match(s)
    if m:
        dish = m.group(1).strip()
        if dish:
            items.append(
                ImportedMenuItem(
                    day=day, meal="lunch", variant_type="dessert", dish_name=dish, category="dessert", source_labels=["dessert"]
                )
            )
        return
    # Strict mode: ignore unrecognized lines
    return


def _current_year() -> int:
    import datetime

    return datetime.date.today().year
