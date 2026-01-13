from __future__ import annotations

import csv
import io
import json
from typing import Any

try:
    from openpyxl import Workbook
except Exception:  # pragma: no cover - tests run with openpyxl installed per requirements
    Workbook = None


def _specials_json(obj: dict[str, int]) -> str:
    return json.dumps({k: int(v) for k, v in sorted((obj or {}).items())}, separators=(",", ":"))


def build_csv(report_payload: dict[str, Any]) -> bytes:
    buf = io.StringIO(newline="")
    w = csv.writer(buf)
    # departments section
    w.writerow(["departments"])  # section marker
    w.writerow(["department_id", "department_name", "meal", "normal", "total", "specials_json"])
    for dep in report_payload.get("departments", []):
        dep_id = dep.get("department_id")
        dep_name = dep.get("department_name")
        for meal in ("lunch", "dinner"):
            m = dep.get(meal, {})
            w.writerow([
                dep_id,
                dep_name if dep_name is not None else "",
                meal,
                int(m.get("normal", 0)),
                int(m.get("total", 0)),
                _specials_json(m.get("specials", {})),
            ])
    # totals section
    w.writerow([])
    w.writerow(["totals"])  # section marker
    w.writerow(["meal", "normal", "total", "specials_json"])
    totals = report_payload.get("totals", {})
    for meal in ("lunch", "dinner"):
        m = totals.get(meal, {})
        w.writerow([
            meal,
            int(m.get("normal", 0)),
            int(m.get("total", 0)),
            _specials_json(m.get("specials", {})),
        ])
    return buf.getvalue().encode("utf-8")


def build_xlsx(report_payload: dict[str, Any]) -> bytes:
    if Workbook is None:  # pragma: no cover
        raise RuntimeError("openpyxl is required for XLSX export")
    wb = Workbook()
    # departments sheet
    ws1 = wb.active
    ws1.title = "departments"
    ws1.append(["department_id", "department_name", "meal", "normal", "total", "specials_json"])
    for dep in report_payload.get("departments", []):
        dep_id = dep.get("department_id")
        dep_name = dep.get("department_name")
        for meal in ("lunch", "dinner"):
            m = dep.get(meal, {})
            ws1.append([
                dep_id,
                dep_name if dep_name is not None else "",
                meal,
                int(m.get("normal", 0)),
                int(m.get("total", 0)),
                _specials_json(m.get("specials", {})),
            ])
    # totals sheet
    ws2 = wb.create_sheet("totals")
    ws2.append(["meal", "normal", "total", "specials_json"])
    totals = report_payload.get("totals", {})
    for meal in ("lunch", "dinner"):
        m = totals.get(meal, {})
        ws2.append([
            meal,
            int(m.get("normal", 0)),
            int(m.get("total", 0)),
            _specials_json(m.get("specials", {})),
        ])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
