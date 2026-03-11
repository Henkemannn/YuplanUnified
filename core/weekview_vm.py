from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from flask import session

from .db import get_session
from .weekview.service import WeekviewService
from .admin_repo import Alt2Repo, DietDefaultsRepo, DietTypesRepo


def build_weekview_vm(site_id: str, year: int, week: int, tenant_id: int | None = None) -> dict[str, Any]:
    """Build a weekview VM using the same data logic as kitchen/week."""
    tid = int(tenant_id) if tenant_id is not None else int(session.get("tenant_id") or 1)

    db = get_session()
    try:
        row_s = db.execute(text("SELECT name FROM sites WHERE id=:i"), {"i": site_id}).fetchone()
        site_name = str(row_s[0]) if row_s else ""
        rows = db.execute(
            text(
                "SELECT id, name, COALESCE(resident_count_fixed,0), COALESCE(notes,'') "
                "FROM departments "
                "WHERE site_id=:s "
                "ORDER BY COALESCE(display_order, 2147483647), name"
            ),
            {"s": site_id},
        ).fetchall()
        departments = [
            {
                "id": str(r[0]),
                "name": str(r[1] or ""),
                "resident_count": int(r[2] or 0),
                "info_text": (str(r[3] or "").strip()),
            }
            for r in rows
        ]
    finally:
        db.close()

    svc = WeekviewService()
    deps_out: list[dict[str, Any]] = []
    for dep in departments:
        dep_id = dep["id"]
        payload, _ = svc.fetch_weekview(tenant_id=tid, year=year, week=week, department_id=dep_id, site_id=site_id)
        summaries = payload.get("department_summaries") or []
        s = summaries[0] if summaries else {}
        days = s.get("days") or []
        alt2_days = set(s.get("alt2_days") or [])
        try:
            alt2_rows = Alt2Repo().list_for_department_week(dep_id, week)
            alt2_days.update({int(r.get("weekday")) for r in alt2_rows if bool(r.get("enabled"))})
        except Exception:
            pass
        try:
            db_alt2 = get_session()
            rows = db_alt2.execute(
                text(
                    "SELECT day_of_week FROM weekview_alt2_flags "
                    "WHERE site_id=:s AND department_id=:d AND year=:y AND week=:w AND enabled=1"
                ),
                {"s": site_id, "d": dep_id, "y": year, "w": week},
            ).fetchall()
            alt2_days.update({int(r[0]) for r in rows})
        except Exception:
            pass
        finally:
            try:
                db_alt2.close()
            except Exception:
                pass
        try:
            for d in days:
                if not d.get("alt2_lunch"):
                    dow_val = int(d.get("day_of_week") or 0)
                    if dow_val in alt2_days:
                        d["alt2_lunch"] = True
        except Exception:
            pass
        raw_marks = s.get("marks") or []
        marked_idx = set()
        try:
            for m in raw_marks:
                if bool(m.get("marked")):
                    marked_idx.add((int(m.get("day_of_week")), str(m.get("meal")), str(m.get("diet_type"))))
        except Exception:
            marked_idx = set()
        defaults = []
        try:
            defaults = DietDefaultsRepo().list_for_department(dep_id)
            types = DietTypesRepo().list_all(site_id=site_id)
            name_by_id = {str(it["id"]): str(it["name"]) for it in types}
            allowed_diet_ids = {str(it["id"]) for it in types}
            preselected_ids = {str(it["id"]) for it in types if bool(it.get("default_select"))}
        except Exception:
            name_by_id = {}
            allowed_diet_ids = set()
            preselected_ids = set()
        defaults_pos = [it for it in (defaults or []) if int(it.get("default_count", 0) or 0) > 0]
        default_count_by_id = {
            str(it.get("diet_type_id")): int(it.get("default_count") or 0)
            for it in defaults_pos
        }
        default_ids = [str(it.get("diet_type_id")) for it in defaults_pos]
        if allowed_diet_ids:
            default_ids = [dtid for dtid in default_ids if dtid in allowed_diet_ids]
        diet_rows = []
        if default_ids:
            for dtid in default_ids:
                cells = []
                for dow in range(1, 8):
                    day_obj = next((x for x in days if int(x.get("day_of_week")) == dow), None)
                    diets_l = ((day_obj.get("diets") or {}).get("lunch") if day_obj else []) or []
                    diets_d = ((day_obj.get("diets") or {}).get("dinner") if day_obj else []) or []
                    rl = 0
                    rd = 0
                    ol = False
                    od = False
                    if diets_l:
                        for it in diets_l:
                            if str(it.get("diet_type_id")) == str(dtid):
                                rl = int(it.get("resident_count") or 0)
                                ol = bool(it.get("has_override"))
                                break
                    else:
                        rl = int(default_count_by_id.get(str(dtid), 0) or 0)
                    for it in diets_d:
                        if str(it.get("diet_type_id")) == str(dtid):
                            rd = int(it.get("resident_count") or 0)
                            od = bool(it.get("has_override"))
                            break
                    ml = ((dow, "lunch", str(dtid)) in marked_idx) or (str(dtid) in preselected_ids and rl > 0)
                    md = ((dow, "dinner", str(dtid)) in marked_idx) or (str(dtid) in preselected_ids and rd > 0)
                    is_alt2 = False
                    try:
                        is_alt2 = bool(day_obj.get("alt2_lunch")) if day_obj else False
                        if not is_alt2 and dow in alt2_days:
                            is_alt2 = True
                    except Exception:
                        is_alt2 = False
                    cells.append(
                        {
                            "day_index": dow,
                            "meal": "lunch",
                            "count": rl,
                            "is_override": ol,
                            "is_done": ml,
                            "is_alt2": is_alt2,
                            "diet_type_id": str(dtid),
                        }
                    )
                    cells.append(
                        {
                            "day_index": dow,
                            "meal": "dinner",
                            "count": rd,
                            "is_override": od,
                            "is_done": md,
                            "is_alt2": False,
                            "diet_type_id": str(dtid),
                        }
                    )
                diet_name = name_by_id.get(str(dtid), str(dtid))
                diet_rows.append({"diet_type_id": str(dtid), "diet_type_name": diet_name, "cells": cells})
        info_text = (dep.get("info_text") or "").strip()
        deps_out.append(
            {
                "id": dep_id,
                "name": dep["name"],
                "resident_count": dep["resident_count"],
                "info_text": (info_text if info_text else None),
                "notes": (info_text if info_text else None),
                "no_diets": (not default_ids),
                "diet_rows": diet_rows,
                "days": days,
            }
        )

    try:
        monday = date.fromisocalendar(year, week, 1)
    except Exception:
        monday = date.today()
    prev_date = monday - timedelta(days=7)
    next_date = monday + timedelta(days=7)
    prev_iso = prev_date.isocalendar()
    next_iso = next_date.isocalendar()

    return {
        "site_id": site_id,
        "site_name": site_name,
        "year": year,
        "week": week,
        "prev_year": int(prev_iso[0]),
        "prev_week": int(prev_iso[1]),
        "next_year": int(next_iso[0]),
        "next_week": int(next_iso[1]),
        "departments": deps_out,
    }
