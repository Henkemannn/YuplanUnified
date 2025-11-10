from __future__ import annotations

from typing import Iterable

from .admin_repo import SitesRepo, DepartmentsRepo, DietDefaultsRepo
from .admin_repo import Alt2Repo
from .etag import make_etag, parse_if_match, ConcurrencyError


VALID_RESIDENT_COUNT_MODES = {"fixed", "per_day_meal"}


class AdminService:
    def __init__(self):
        self.sites_repo = SitesRepo()
        self.depts_repo = DepartmentsRepo()
        self.diet_repo = DietDefaultsRepo()
        self.alt2_repo = Alt2Repo()

    # --- Sites ---
    def create_site(self, name: str) -> tuple[dict, str]:
        if not name or len(name.strip()) == 0:
            raise ValueError("name_required")
        rec, ver = self.sites_repo.create_site(name.strip())
        etag = make_etag("admin", "site", rec["id"], ver)
        return rec, etag

    # --- Departments ---
    def create_department(
        self,
        site_id: str,
        name: str,
        resident_count_mode: str,
        resident_count_fixed: int | None,
    ) -> tuple[dict, str]:
        if resident_count_mode not in VALID_RESIDENT_COUNT_MODES:
            raise ValueError("invalid_resident_count_mode")
        if resident_count_mode == "fixed" and (resident_count_fixed or 0) < 0:
            raise ValueError("resident_count_fixed_negative")
        rec, ver = self.depts_repo.create_department(
            site_id, name.strip(), resident_count_mode, resident_count_fixed or 0
        )
        etag = make_etag("admin", "dept", rec["id"], ver)
        return rec, etag

    def update_department(self, dept_id: str, if_match: str | None, payload: dict) -> tuple[dict, str]:
        ns, kind, ident, version = parse_if_match(if_match)
        if not version or ident != dept_id or kind != "dept" or ns != "admin":
            raise ValueError("invalid_if_match")
        fields = {}
        if "name" in payload:
            nm = str(payload["name"]).strip()
            if nm:
                fields["name"] = nm
        if "resident_count_mode" in payload:
            mode = str(payload["resident_count_mode"]).strip()
            if mode and mode in VALID_RESIDENT_COUNT_MODES:
                fields["resident_count_mode"] = mode
        if "resident_count_fixed" in payload and payload["resident_count_fixed"] is not None:
            rcf = int(payload["resident_count_fixed"])
            if rcf < 0:
                raise ValueError("resident_count_fixed_negative")
            fields["resident_count_fixed"] = rcf
        try:
            new_version = self.depts_repo.update_department(dept_id, version, **fields)
        except ConcurrencyError as ce:
            raise ce
        etag = make_etag("admin", "dept", dept_id, new_version)
        # Compose minimal representation (Phase B keeps lean)
        rep = {"id": dept_id}
        rep.update(fields)
        return rep, etag

    def update_department_notes(self, dept_id: str, if_match: str | None, notes: str | None) -> tuple[dict, str]:
        ns, kind, ident, version = parse_if_match(if_match)
        if not version or ident != dept_id or kind != "dept" or ns != "admin":
            raise ValueError("invalid_if_match")
        try:
            new_version = self.depts_repo.update_department(dept_id, version, notes=notes or None)
        except ConcurrencyError as ce:
            raise ce
        etag = make_etag("admin", "dept", dept_id, new_version)
        return {"department_id": dept_id, "notes": notes}, etag

    def update_diet_defaults(
        self, dept_id: str, if_match: str | None, items: Iterable[dict]
    ) -> tuple[list[dict], str]:
        ns, kind, ident, version = parse_if_match(if_match)
        if not version or ident != dept_id or kind != "dept" or ns != "admin":
            raise ValueError("invalid_if_match")
        # Validation
        sanitized: list[dict] = []
        for it in items:
            diet_type_id = str(it.get("diet_type_id") or "").strip()
            if not diet_type_id:
                raise ValueError("diet_type_id_required")
            default_count = int(it.get("default_count") or 0)
            if default_count < 0:
                raise ValueError("default_count_negative")
            sanitized.append({"diet_type_id": diet_type_id, "default_count": default_count})
        try:
            new_version = self.depts_repo.upsert_department_diet_defaults(dept_id, version, sanitized)
        except ConcurrencyError as ce:
            raise ce
        etag = make_etag("admin", "dept", dept_id, new_version)
        return sanitized, etag

    # Alt2 bulk will be delegated to existing weekview service in Phase C – Phase B placeholder
    def update_alt2_bulk(
        self,
        if_match: str | None,
        week: int,
        items: list[dict],
    ) -> tuple[dict, str]:
        """Bulk upsert alt2 flags for given week across departments.

        If-Match uses collection etag: W/"admin:alt2:week:{week}:v{n}".
        """
        ns, kind, ident, version = parse_if_match(if_match)
        if not version or kind != "alt2" or ns != "admin" or ident != f"week:{week}":
            raise ValueError("invalid_if_match")
        # Concurrency check (collection etag)
        current_v = self.alt2_repo.collection_version(week)
        if version != current_v:
            raise ConcurrencyError("stale collection version")
        sanitized: list[dict] = []
        for it in items:
            dept_id = str(it.get("department_id") or "").strip()
            if not dept_id:
                raise ValueError("department_id_required")
            weekday = int(it.get("weekday", -1))
            if weekday < 1 or weekday > 7:
                raise ValueError("weekday_out_of_range")
            enabled = bool(it.get("enabled", True))
            # site_id is currently not passed – placeholder 'site' field or derive later; use dept_id as proxy for uniqueness
            sanitized.append({"site_id": "site-placeholder", "department_id": dept_id, "week": week, "weekday": weekday, "enabled": enabled})
        # Upsert flags
        updated = self.alt2_repo.bulk_upsert(sanitized)
        new_coll_version = self.alt2_repo.collection_version(week)
        etag = make_etag("admin", "alt2", f"week:{week}", new_coll_version)
        body = {
            "week": week,
            "items": [
                {
                    "department_id": r["department_id"],
                    "weekday": r["weekday"],
                    "enabled": r["enabled"],
                    "etag": make_etag("admin", "alt2", f"{r['department_id']}:{week}:{r['weekday']}", r["version"]),
                }
                for r in updated
            ],
        }
        return body, etag

    # Helpers for current ETag exposure on 412 responses
    def get_department_current_etag(self, dept_id: str) -> str | None:
        v = self.depts_repo.get_version(dept_id)
        if v is None:
            return None
        return make_etag("admin", "dept", dept_id, v)

    def get_alt2_collection_etag(self, week: int) -> str:
        v = self.alt2_repo.collection_version(week)
        return make_etag("admin", "alt2", f"week:{week}", v)
