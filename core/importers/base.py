from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Protocol


# Canonical normalized item
@dataclass
class ImportedMenuItem:
    day: str          # monday..sunday (lowercase english)
    meal: str         # lunch|dinner|evening (future: breakfast?)
    variant_type: str # main|alt1|alt2|dessert|evening
    dish_name: str
    category: Optional[str] = None
    source_labels: List[str] = field(default_factory=list)

@dataclass
class WeekImport:
    year: int
    week: int
    items: List[ImportedMenuItem]

@dataclass
class MenuImportResult:
    weeks: List[WeekImport]
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

class MenuImporter(Protocol):
    """Importer protocol. Each importer should:
    - can_handle(...) quick sniff
    - parse(...) return MenuImportResult (may contain multiple weeks)
    """
    def can_handle(self, filename: str, mimetype: str | None, first_bytes: bytes) -> bool: ...
    def parse(self, file_bytes: bytes, filename: str) -> MenuImportResult: ...

# Utilities
_day_map = {
    # Swedish (full)
    'måndag': 'monday',
    'tisdag': 'tuesday',
    'onsdag': 'wednesday',
    'torsdag': 'thursday',
    'fredag': 'friday',
    'lördag': 'saturday',
    'söndag': 'sunday',
    # Swedish (abbrev)
    'mån': 'monday',
    'tis': 'tuesday',
    'ons': 'wednesday',
    'tor': 'thursday',
    'fre': 'friday',
    'lör': 'saturday',
    'sön': 'sunday',
    # Norwegian
    'mandag': 'monday',
    'tirsdag': 'tuesday',
    # (onsdag, torsdag, fredag already covered above with same spelling)
    'lørdag': 'saturday',
    'søndag': 'sunday',
}

def normalize_day(token: str) -> str | None:
    t = token.strip().lower()
    return _day_map.get(t)

DEFAULT_YEAR_PROVIDER = None  # placeholder; could inject current year
