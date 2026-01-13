from __future__ import annotations

from .base import ImportedMenuItem, MenuImporter, MenuImportResult, WeekImport

try:  # Optional dependency
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - fallback when pandas missing
    pd = None  # type: ignore
import datetime
import io
import re

_DAYS_NO = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]
_DAY_MAP = {
    d.lower(): {
        "Mandag": "monday",
        "Tirsdag": "tuesday",
        "Onsdag": "wednesday",
        "Torsdag": "thursday",
        "Fredag": "friday",
        "Lørdag": "saturday",
        "Søndag": "sunday",
    }[d]
    for d in _DAYS_NO
}


class ExcelMenuImporter(MenuImporter):
    """Adapts offshore Excel format (multiple sheets: Uke 1..4)."""

    def can_handle(self, filename: str, mimetype: str | None, first_bytes: bytes) -> bool:
        return filename.lower().endswith(".xlsx") or filename.lower().endswith(".xls")

    def parse(self, file_bytes: bytes, filename: str) -> MenuImportResult:
        if pd is None:
            return MenuImportResult(
                weeks=[], errors=["pandas not installed"], warnings=["Excel import disabled"]
            )
        bio = io.BytesIO(file_bytes)
        xl = pd.ExcelFile(bio)
        weeks = []
        current_year = datetime.date.today().year
        for sheet in xl.sheet_names:
            sheet_name = str(sheet)
            m = re.match(r"Uke\s*(\d+)", sheet_name, re.IGNORECASE)
            if not m:
                continue
            week = int(m.group(1))
            df = xl.parse(sheet_name=sheet_name, header=None)
            items = self._extract(df, week)
            weeks.append(WeekImport(year=current_year, week=week, items=items))
        if not weeks:
            return MenuImportResult(
                weeks=[], errors=["No sheets matching 'Uke <n>' found"], warnings=[]
            )
        return MenuImportResult(weeks=weeks)

    def _extract(self, df, week: int):
        # Simplified: detect lunch rows (col 0 day, 1 category, 3 dish) and dinner rows using heuristic columns.
        items: list[ImportedMenuItem] = []
        current_day = None
        # Lunch
        for i in range(len(df)):
            day_cell = df.iat[i, 0] if df.shape[1] > 0 else None
            day = str(day_cell).strip() if day_cell is not None and str(day_cell).strip() else ""
            if day in _DAYS_NO:
                current_day = day
            elif current_day:
                day = current_day
            cat = df.iat[i, 1] if df.shape[1] > 1 else ""
            dish = df.iat[i, 3] if df.shape[1] > 3 else ""
            if self._valid_row(day, cat, dish):
                items.append(
                    ImportedMenuItem(
                        day=_DAY_MAP[day.lower()],
                        meal="lunch",
                        variant_type="main",
                        dish_name=str(dish).strip(),
                        category=str(cat).strip() or None,
                        source_labels=["lunch"],
                    )
                )
        # Dinner heuristic: search for columns containing 'Middag' marker? For now reuse other columns if present.
        # TODO: Map per-week varying columns like legacy script (MIDDAG_MAP) if needed.
        return items

    def _valid_row(self, day, cat, dish):
        if day not in _DAYS_NO:
            return False
        d = str(dish).strip()
        return not (
            not d
            or d.lower().startswith(("navn:", "oppskriftsreferanse", "kategori:", "kommentar"))
        )
