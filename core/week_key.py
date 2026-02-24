from __future__ import annotations

import re
from datetime import date as _date

_WEEK_KEY_RE = re.compile(r"^(?P<year>\d{4})-W?(?P<week>\d{1,2})$")


def build_week_key(year: int, week: int) -> str:
    if week < 1 or week > 53:
        raise ValueError("week out of range")
    return f"{int(year):04d}-W{int(week):02d}"


def parse_week_key(week_key: str) -> tuple[int, int]:
    m = _WEEK_KEY_RE.match(str(week_key or "").strip())
    if not m:
        raise ValueError("invalid week_key")
    year = int(m.group("year"))
    week = int(m.group("week"))
    if year < 2000 or year > 2100 or week < 1 or week > 53:
        raise ValueError("invalid week_key")
    return year, week


def normalize_week_key(week_key: str) -> str:
    year, week = parse_week_key(week_key)
    return build_week_key(year, week)


def week_key_from_date(dt: _date) -> str:
    iso = dt.isocalendar()
    return build_week_key(int(iso[0]), int(iso[1]))


__all__ = ["build_week_key", "parse_week_key", "normalize_week_key", "week_key_from_date"]
