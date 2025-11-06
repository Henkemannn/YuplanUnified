from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Item:
    id: str
    title: str
    notes: Optional[str] = None
    diet_type: Optional[str] = None
    status: Optional[str] = None  # planned|confirmed|canceled
    assigned_to: Optional[str] = None


@dataclass
class MealSlot:
    kind: str  # lunch|dinner
    items: List[Item] = field(default_factory=list)


@dataclass
class DayPlan:
    date: str  # ISO date
    day_of_week: int  # 1..7 ISO
    meals: List[MealSlot] = field(default_factory=list)


@dataclass
class DepartmentSummary:
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    department_notes: List[str] = field(default_factory=list)
    days: List[DayPlan] = field(default_factory=list)


@dataclass
class WeekView:
    year: int
    week: int
    week_start: Optional[str] = None  # ISO date
    week_end: Optional[str] = None  # ISO date
    department_summaries: List[DepartmentSummary] = field(default_factory=list)
