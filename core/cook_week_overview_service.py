from __future__ import annotations

from typing import Any, Dict
from types import SimpleNamespace
from dataclasses import dataclass, field
from .weekview.service import WeekviewService

# Phase 8 Step 1: Unified copy of legacy veckovy context builder
# IMPORTANT: No imports from legacy Yuplan3.5 modules. Use only Unified services/repos when needed.

def build_cook_week_overview_context(
    tenant_id: int | None,
    site_id: int | None,
    year: int,
    week: int,
) -> Dict[str, Any]:
    """
    Build a context compatible with unified_cook_week_overview.html (ported from legacy veckovy.html).

    Returns keys used by the template:
      - avdelningar: list of department dicts, each with namn, id, faktaruta, kosttyper, antal_boende_per_dag
      - alt2_markeringar: dict[department_id][day_abbr] -> bool to paint lunch cells yellow
      - meny_data: dict keyed by day (mån, tis, ons, tors, fre, lör, sön) with menu items

    For Step 1 we provide a safe, minimal structure so route compiles and UI renders
    without altering existing behavior. Later steps can enrich via actual Unified services.
    """
    # Minimal, non-invasive defaults; populate incrementally in Step 2
    avdelningar: list[Any] = []
    alt2_markeringar: Dict[str, Dict[str, bool]] = {}
    meny_data: Dict[str, Dict[str, str]] = {}

    # Fetch aggregated week view for all departments (department_id=None)
    svc = WeekviewService()
    payload, _etag = svc.fetch_weekview(tenant_id or 0, year, week, None)
    summaries = payload.get("department_summaries", []) or []

    # Build Swedish day name/abbr maps
    day_map_idx_to_abbr = {1: "Mån", 2: "Tis", 3: "Ons", 4: "Tors", 5: "Fre", 6: "Lör", 7: "Sön"}
    day_key_to_swe = {"mon": "mån", "tue": "tis", "wed": "ons", "thu": "tors", "fri": "fre", "sat": "lör", "sun": "sön"}

    # Menu data (week-level, not per department)
    try:
        days = payload.get("days", {}) or {}
        for k, v in days.items():
            swe_key = day_key_to_swe.get(str(k), str(k))
            meny_data[swe_key] = {
                "alt1": (v.get("lunch") or {}).get("alt1", ""),
                "alt2": (v.get("lunch") or {}).get("alt2", ""),
                "dessert": (v.get("lunch") or {}).get("dessert", ""),
                "kväll": (v.get("dinner") or {}).get("text", ""),
            }
    except Exception:
        meny_data = {}

    # Build departments list with residents counts and alt2 flags
    for s in summaries:
        dep_id = str(s.get("department_id") or "").strip()
        dep_name = s.get("department_name") or dep_id
        notes = s.get("notes") or ""
        counts = s.get("residents_counts", []) or []
        alt2_days = set(s.get("alt2_days", []) or [])
        marks = s.get("marks", []) or []

        # antal_boende_per_dag keyed by (Swedish abbr, 'Lunch'|'Kväll') -> (count, False)
        abd: Dict[tuple[str, str], tuple[int, bool]] = {}
        try:
            for r in counts:
                idx = int(r.get("day_of_week"))
                meal = str(r.get("meal"))
                abbr = day_map_idx_to_abbr.get(idx, str(idx))
                if meal == "lunch":
                    abd[(abbr, "Lunch")] = (int(r.get("count", 0)), False)
                elif meal == "dinner":
                    abd[(abbr, "Kväll")] = (int(r.get("count", 0)), False)
        except Exception:
            abd = {}

        # alt2 flags per Swedish abbr for lunch
        alt2_flags: Dict[str, bool] = {}
        try:
            for d in range(1, 8):
                abbr = day_map_idx_to_abbr.get(d, str(d))
                alt2_flags[abbr] = (d in alt2_days)
        except Exception:
            alt2_flags = {}
        if dep_id:
            alt2_markeringar[dep_id] = alt2_flags

        # kosttyper: build rows based on diet defaults present in enrichment and marks
        # Collect diet types from marks and potential defaults index in payload enrichment
        diet_types: Dict[str, str] = {}
        # Try to infer readable names if present in payload; otherwise use diet_type id
        # Payload may include diet_defaults separately; fallback to ids from marks
        try:
            defaults = s.get("diet_defaults", {}) or {}
            for dt_id, cnt in defaults.items():
                diet_types[str(dt_id)] = str(dt_id)
        except Exception:
            pass
        try:
            for m in marks:
                dt = str(m.get("diet_type"))
                if dt:
                    diet_types.setdefault(dt, dt)
        except Exception:
            pass

        # Helper to decide if a special diet is marked for given day/meal/diet
        def _is_marked(day_idx: int, meal_key: str, diet_type: str) -> bool:
            try:
                for m in marks:
                    if bool(m.get("marked")) and int(m.get("day_of_week")) == day_idx and str(m.get("meal")) == meal_key and str(m.get("diet_type")) == diet_type:
                        return True
            except Exception:
                return False
            return False

        # Counts per diet type: use defaults if available; otherwise 0 (can be refined later)
        try:
            defaults = s.get("diet_defaults", {}) or {}
        except Exception:
            defaults = {}

        kosttyper = []
        for diet_id, diet_name in diet_types.items():
            # Build two cells per day (Lunch/Kväll)
            celler = []
            for d in range(1, 8):
                abbr = day_map_idx_to_abbr.get(d, str(d))
                # Lunch
                lunch_count = int(defaults.get(diet_id, 0))
                lunch_mark = _is_marked(d, "lunch", diet_id)
                lunch_alt2 = (d in alt2_days)
                celler.append(SimpleNamespace(dag=abbr, maltid="Lunch", antal=lunch_count, markerad=lunch_mark, alt2_gul=lunch_alt2))
                # Dinner
                dinner_count = int(defaults.get(diet_id, 0))
                dinner_mark = _is_marked(d, "dinner", diet_id)
                celler.append(SimpleNamespace(dag=abbr, maltid="Kväll", antal=dinner_count, markerad=dinner_mark, alt2_gul=False))
            kosttyper.append(SimpleNamespace(namn=diet_name, diet_id=diet_id, celler=celler))

        avdelningar.append(SimpleNamespace(id=dep_id, namn=dep_name, faktaruta=notes, kosttyper=kosttyper, antal_boende_per_dag=abd))

    context: Dict[str, Any] = {
        "vecka": week,
        "avdelningar": avdelningar,
        "alt2_markeringar": alt2_markeringar,
        "meny_data": meny_data,
        "etag": _etag,
    }
    return context
