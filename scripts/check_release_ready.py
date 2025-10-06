#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "specs" / "openapi.baseline.json"
SPEC = ROOT / "openapi.json"
CHECKLIST = ROOT / "docs" / "v1.0-beta-checklist.md"


def run(cmd: list[str]) -> int:
    print(f"$ {' '.join(cmd)}")
    return subprocess.call(cmd)


def ensure_file(p: Path, msg: str):
    if not p.exists() or p.stat().st_size == 0:
        print(f"[FAIL] {msg}: {p} saknas eller är tomt.")
        sys.exit(1)


def semantic_diff_ok() -> bool:
    tmp = ROOT / "openapi-extras" / "tmp-openapi-diff.json"
    tmp.parent.mkdir(exist_ok=True, parents=True)
    code = run([
        sys.executable,
        str(ROOT / "scripts" / "openapi_diff.py"),
        str(BASELINE),
        str(SPEC),
        "--json-report",
        str(tmp),
    ])
    try:
        data = json.loads(tmp.read_text(encoding="utf-8"))
    except Exception:
        print("[FAIL] Kunde inte läsa JSON diff artifact.")
        return False
    print(
        f"[DIFF] status={data.get('status')} breaking={len(data.get('breaking', []))} additions={len(data.get('additions', []))}"
    )
    return code == 0


def checklist_clear() -> bool:
    if not CHECKLIST.exists():
        print("[WARN] Ingen v1.0-beta-checklist.md hittad – hoppar denna kontroll.")
        return True
    txt = CHECKLIST.read_text(encoding="utf-8")
    open_boxes = re.findall(r"^\s*-\s*\[\s\]\s", txt, re.M)
    if open_boxes:
        print(f"[FAIL] Checklist har {len(open_boxes)} öppna punkter.")
        return False
    print("[OK] Checklistan är ifylld.")
    return True


def main():
    # 1) Filer finns
    ensure_file(BASELINE, "Baseline krävs (hård policy)")
    if not SPEC.exists():
        print("[INFO] openapi.json saknas – kör 'make openapi' först.")
        sys.exit(1)
    ensure_file(SPEC, "OpenAPI-spec")

    # 2) Lint & tester (om make finns)
    if shutil.which("make"):
        if run(["make", "format"]) != 0:
            sys.exit(1)
        if run(["make", "lint"]) != 0:
            sys.exit(1)
        if run(["make", "test"]) != 0:
            sys.exit(1)

    # 3) Spectral (valfri lokal)
    if shutil.which("spectral"):
        if run(["spectral", "lint", str(SPEC)]) != 0:
            sys.exit(1)
    else:
        print("[WARN] spectral ej installerad – skippar stilkontroll.")

    # 4) Semantisk diff
    if not semantic_diff_ok():
        print(
            "[FAIL] Semantisk OpenAPI-diff rapporterar BREAKING – åtgärda eller uppdatera baseline/MAJOR."
        )
        sys.exit(1)

    # 5) Checklista klar
    if not checklist_clear():
        sys.exit(1)

    print("\n✅ Release readiness OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
