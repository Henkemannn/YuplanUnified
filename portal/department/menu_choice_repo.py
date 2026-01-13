from __future__ import annotations

"""Menu choice repository abstraction for Department Portal.

Currently choices are persisted via Alt2Repo (alt2_flags table) enabling Alt2 for given weekday.
This repo maps explicit selected_alt (Alt1/Alt2) onto that storage.
Future: replace with dedicated menu_choice table if introduced.
"""
from typing import Optional
from sqlalchemy import text
from core.db import get_session
from core.admin_repo import Alt2Repo
from core.menu_choice_api import _current_signature as _menu_choice_sig, _DAY_MAP as _MENU_DAY_MAP

class MenuChoiceRepo:
    def __init__(self):
        self.alt2_repo = Alt2Repo()

    def get_signature(self, department_id: str, year: int, week: int) -> str:
        # Match service etag format: portal-menu-choice:{department_id}:{year}-{week}:v<sig>
        return f'W/"portal-menu-choice:{department_id}:{year}-{week}:v{_menu_choice_sig(department_id, week)}"'

    def set_choice(self, department_id: str, week: int, weekday: int, selected_alt: str) -> None:
        """Persist choice for given weekday.
        Alt2 storage: enabled=1 means Alt2 chosen; 0 means Alt1.
        """
        enabled = 1 if selected_alt == "Alt2" else 0
        # Alt2Repo has upsert capability via direct table operations; perform minimal update
        db = get_session()
        try:
            db.execute(text("CREATE TABLE IF NOT EXISTS alt2_flags(site_id TEXT, department_id TEXT, week INTEGER, weekday INTEGER, enabled INTEGER, version INTEGER, UNIQUE(site_id,department_id,week,weekday))"))
            db.execute(text("INSERT OR REPLACE INTO alt2_flags(site_id,department_id,week,weekday,enabled,version) VALUES('site',:d,:w,:wd,:en,1)"), {"d": department_id, "w": week, "wd": weekday, "en": enabled})
            db.commit()
        finally:
            db.close()

    def derive_map(self, department_id: str, week: int) -> dict[str, str]:
        rows = self.alt2_repo.list_for_department_week(department_id, week)
        m = {v: "Alt1" for v in _MENU_DAY_MAP.values()}
        for r in rows:
            if r.get("enabled"):
                wk = int(r.get("weekday") or 0)
                dk = _MENU_DAY_MAP.get(wk)
                if dk:
                    m[dk] = "Alt2"
        return m

__all__ = ["MenuChoiceRepo"]
