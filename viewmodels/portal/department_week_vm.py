from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class DepartmentDayVM:
    index: int = 0
    name: str
    date: str
    lunch_alt1: Optional[str] = None
    lunch_alt2: Optional[str] = None
    dinner: Optional[str] = None
    alt2_marked: bool = False
    is_complete: bool = False

@dataclass
class DepartmentWeekViewModel:
    week: int
    year: int
    department_name: str
    department_id: int
    residents: int
    status_text: str
    days: List[DepartmentDayVM] = field(default_factory=list)

@dataclass
class DepartmentDaySelectionVM:
    year: int
    week: int
    department_id: int
    department_name: str
    day_index: int
    date: str
    day_name: str
    lunch_alt1: Optional[str] = None
    lunch_alt2: Optional[str] = None
    dinner: Optional[str] = None
    alt2_selected: bool = False
    is_complete: bool = False
    flash_message: Optional[str] = None
    flash_level: Optional[str] = None
