from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from flask import session

from .db import get_session
from .menu_service import MenuServiceDB
from .weekview.service import WeekviewService
from .admin_repo import DietDefaultsRepo, DietTypesRepo


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
        try:
            legacy_week_view = MenuServiceDB().get_week_view(tid, site_id, week, year)
            legacy_days = legacy_week_view.get("days", {}) if isinstance(legacy_week_view, dict) else {}
            day_keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            for idx, day in enumerate(days):
                if idx >= len(day_keys):
                    break
                legacy_day = legacy_days.get(day_keys[idx], {}) if isinstance(legacy_days, dict) else {}
                dinner_bucket = legacy_day.get("dinner") or legacy_day.get("Kväll") or legacy_day.get("kväll") or legacy_day.get("kvall") or {}
                dinner_text = ""
                if isinstance(dinner_bucket, dict):
                    for variant_key in ("main", "kvall", "dinner", "alt1", "alt2"):
                        variant_val = dinner_bucket.get(variant_key)
                        if isinstance(variant_val, dict):
                            dinner_text = str(variant_val.get("dish_name") or "").strip()
                            if dinner_text:
                                break
                if not dinner_text:
                    continue
                menu_texts = day.setdefault("menu_texts", {})
                dinner_obj = menu_texts.setdefault("dinner", {})
                if not dinner_obj.get("main"):
                    dinner_obj["main"] = dinner_text
                if not day.get("dinner_main"):
                    day["dinner_main"] = dinner_text
        except Exception:
            pass
        alt2_days = set(s.get("alt2_days") or [])
        try:
            for d in days:
                if not d.get("alt2_lunch"):
                    dow_val = int(d.get("day_of_week") or 0)
                    if dow_val in alt2_days:
                        d["alt2_lunch"] = True
        except Exception:
            pass
        defaults = []
        try:
            defaults = DietDefaultsRepo().list_for_department(dep_id)
            types = DietTypesRepo().list_all(site_id=site_id)
            name_by_id = {str(it["id"]): str(it["name"]) for it in types}
            allowed_diet_ids = {str(it["id"]) for it in types}
        except Exception:
            name_by_id = {}
            allowed_diet_ids = set()
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
                    lunch_marked = False
                    dinner_marked = False
                    if diets_l:
                        for it in diets_l:
                            if str(it.get("diet_type_id")) == str(dtid):
                                rl = int(it.get("resident_count") or 0)
                                ol = bool(it.get("has_override"))
                                lunch_marked = bool(it.get("marked"))
                                break
                    else:
                        rl = int(default_count_by_id.get(str(dtid), 0) or 0)
                    for it in diets_d:
                        if str(it.get("diet_type_id")) == str(dtid):
                            rd = int(it.get("resident_count") or 0)
                            od = bool(it.get("has_override"))
                            dinner_marked = bool(it.get("marked"))
                            break
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
                            "is_done": lunch_marked,
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
                            "is_done": dinner_marked,
                            "is_alt2": False,
                            "diet_type_id": str(dtid),
                        }
                    )
                diet_name = name_by_id.get(str(dtid), str(dtid))
                diet_rows.append({"diet_type_id": str(dtid), "diet_type_name": diet_name, "cells": cells})
        info_text = (dep.get("info_text") or "").strip()
        has_dinner = any(
            bool((day.get("menu_texts") or {}).get("dinner", {}).get(key))
            for day in days
            for key in ("main", "alt1", "alt2")
        )
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
                "has_dinner": has_dinner,
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
