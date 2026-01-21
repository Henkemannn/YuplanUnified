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
        if version is None or ident != dept_id or kind != "dept" or ns != "admin":
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
        if version is None or ident != dept_id or kind != "dept" or ns != "admin":
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
        if version is None or ident != dept_id or kind != "dept" or ns != "admin":
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
        if version is None or kind != "alt2" or ns != "admin" or ident != f"week:{week}":
            raise ValueError("invalid_if_match")
        # Concurrency check (collection etag) – site-scoped
        # Determine single site_id scope from items; reject mixed sites
        scope_site_id: str | None = None
        try:
            from .db import get_session
            from sqlalchemy import text as _text
            _db = get_session()
            try:
                _sites: set[str] = set()
                for it in items:
                    _dept_id = str(it.get("department_id") or "").strip()
                    if not _dept_id:
                        raise ValueError("department_id_required")
                    _row = _db.execute(_text("SELECT site_id FROM departments WHERE id=:id"), {"id": _dept_id}).fetchone()
                    if not _row:
                        raise ValueError("department_not_found")
                    _sites.add(str(_row[0]))
                if len(_sites) != 1:
                    raise ValueError("mixed_site_ids")
                scope_site_id = next(iter(_sites))
            finally:
                _db.close()
        except Exception:
            scope_site_id = None
        if not scope_site_id:
            raise ValueError("site_scope_required")
        current_v = self.alt2_repo.collection_version(week, scope_site_id)
        if version != current_v:
            raise ConcurrencyError("stale collection version")
        # Infer site_id for each department (first lookup; all departments in seed share one site)
        sanitized: list[dict] = []
        from .db import get_session
        from sqlalchemy import text as _text
        db = get_session()
        try:
            site_cache: dict[str, str] = {}
            for it in items:
                dept_id = str(it.get("department_id") or "").strip()
                if not dept_id:
                    raise ValueError("department_id_required")
                weekday = int(it.get("weekday", -1))
                if weekday < 1 or weekday > 7:
                    raise ValueError("weekday_out_of_range")
                enabled = bool(it.get("enabled", True))
                site_id = site_cache.get(dept_id)
                if site_id is None:
                    row = db.execute(_text("SELECT site_id FROM departments WHERE id=:id"), {"id": dept_id}).fetchone()
                    if not row:
                        raise ValueError("department_not_found")
                    site_id = str(row[0])
                    site_cache[dept_id] = site_id
                sanitized.append({"site_id": site_id, "department_id": dept_id, "week": week, "weekday": weekday, "enabled": enabled})
        finally:
            db.close()
        # Upsert flags with real site ids
        updated = self.alt2_repo.bulk_upsert(sanitized)
        new_coll_version = self.alt2_repo.collection_version(week, scope_site_id)
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

    def get_alt2_collection_etag(self, week: int, site_id: str) -> str:
        v = self.alt2_repo.collection_version(week, site_id)
        return make_etag("admin", "alt2", f"week:{week}", v)

    # --- Department Settings (Phase 1) ---
    def get_department_settings(self, department_id: str) -> dict:
        """Build VM for department settings: base residents, diet defaults, and notes."""
        from .db import get_session
        from sqlalchemy import text as _text
        db = get_session()
        try:
            row = db.execute(
                _text(
                    "SELECT d.id, d.site_id, d.name, d.resident_count_fixed, COALESCE(d.notes,'') FROM departments d WHERE d.id=:id"
                ),
                {"id": department_id},
            ).fetchone()
            if not row:
                raise ValueError("department_not_found")
            dept = {
                "department_id": str(row[0]),
                "site_id": str(row[1]),
                "department_name": str(row[2]),
                "residents_base_count": int(row[3] or 0),
                "notes": str(row[4] or ""),
            }
            # Diet defaults
            defaults = self.diet_repo.list_for_department(department_id)
            dept["diet_defaults"] = [
                {
                    "diet_type_id": it["diet_type_id"],
                    "planned_count": int(it.get("default_count") or 0),
                    "always_mark": bool(it.get("always_mark") or False),
                }
                for it in defaults
            ]
            return dept
        finally:
            db.close()

    def save_department_settings(self, department_id: str, payload: dict) -> None:
        """Persist base residents count, notes, and diet defaults.

        This updates defaults (not marks). Uses optimistic concurrency via department version.
        """
        # Get current etag/version
        current_etag = self.get_department_current_etag(department_id)
        ns, kind, ident, version = parse_if_match(current_etag)
        if version is None or ident != department_id or kind != "dept" or ns != "admin":
            # Fallback: fetch version directly
            version = self.depts_repo.get_version(department_id) or 0
        # Update department base fields
        fields = {}
        if "residents_base_count" in payload and payload["residents_base_count"] is not None:
            rcf = int(payload["residents_base_count"]) if str(payload["residents_base_count"]).strip() != "" else 0
            if rcf < 0:
                raise ValueError("resident_count_fixed_negative")
            fields["resident_count_fixed"] = rcf
        if "notes" in payload:
            fields["notes"] = str(payload.get("notes") or "")
        if fields:
            self.depts_repo.update_department(department_id, int(version), **fields)
            # refresh version after update
            version = self.depts_repo.get_version(department_id) or int(version)
        # Update diet defaults list
        items = []
        for it in (payload.get("diet_defaults") or []):
            diet_type_id = str(it.get("diet_type_id") or "").strip()
            if not diet_type_id:
                raise ValueError("diet_type_id_required")
            planned = int(it.get("planned_count") or 0)
            if planned < 0:
                raise ValueError("default_count_negative")
            items.append({"diet_type_id": diet_type_id, "default_count": planned})
        if items:
            self.depts_repo.upsert_department_diet_defaults(department_id, int(version), items)
