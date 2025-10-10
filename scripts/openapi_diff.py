#!/usr/bin/env python3
"""
Semantic OpenAPI diff (baseline vs new).

Exit codes:
    0 = OK (no breaking changes; additions allowed)
    1 = Breaking changes detected
    2 = Usage or IO error
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def load_spec(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # pragma: no cover - defensive
        print(f"[ERROR] Failed to read {path}: {e}", file=sys.stderr)
        sys.exit(2)


def as_set(obj) -> set[Any]:
    if obj is None:
        return set()
    if isinstance(obj, list):
        return set(obj)
    if isinstance(obj, set):  # pragma: no cover - not expected but safe
        return obj
    return {obj}


def iter_paths(spec: dict[str, Any]) -> set[str]:
    return set((spec.get("paths") or {}).keys())


def iter_methods(path_item: dict[str, Any]) -> set[str]:
    return {m for m in path_item if m.lower() in {"get", "put", "post", "delete", "options", "head", "patch", "trace"}}


def responses_of(op: dict[str, Any]) -> set[str]:
    return set((op.get("responses") or {}).keys())


def content_types_of(op_or_resp: dict[str, Any]) -> set[str]:
    content = (op_or_resp or {}).get("content") or {}
    return set(content.keys())


def request_body(op: dict[str, Any]) -> dict[str, Any] | None:
    return op.get("requestBody")


def schema_of(content: dict[str, Any]) -> dict[str, Any] | None:
    for mt in (content or {}).values():
        sch = mt.get("schema")
        if sch:
            return sch
    return None


def diff_enums(old_enum: list[Any] | None, new_enum: list[Any] | None) -> tuple[set[Any], set[Any]]:
    old = set(old_enum or [])
    new = set(new_enum or [])
    removed = old - new
    added = new - old
    return removed, added


def diff_schemas(ctx: str, base_schema: dict, new_schema: dict) -> list[str]:
    brk: list[str] = []

    base_ref = base_schema.get("$ref")
    new_ref = new_schema.get("$ref")
    if base_ref or new_ref:
        if base_ref != new_ref:
            brk.append(f"{ctx}: $ref changed ({base_ref!r} -> {new_ref!r})")
        return brk  # don't descend on $ref

    bt = base_schema.get("type")
    nt = new_schema.get("type")
    if bt and nt and bt != nt:
        brk.append(f"{ctx}: type changed ({bt} -> {nt})")

    # NEW: format changes (narrowing or any change treated as breaking)
    bf = base_schema.get("format")
    nf = new_schema.get("format")
    if (bf or nf) and (bf != nf):
        brk.append(f"{ctx}: format changed ({bf!r} -> {nf!r})")

    # Enum narrowing (removals)
    b_enum = base_schema.get("enum")
    n_enum = new_schema.get("enum")
    rem, _add = diff_enums(b_enum, n_enum)
    for v in sorted(rem):
        brk.append(f"{ctx}: enum value removed: {v!r}")

    # Objects
    if (bt or nt) == "object" or ("properties" in base_schema or "properties" in new_schema):
        b_props_map = base_schema.get("properties") or {}
        n_props_map = new_schema.get("properties") or {}

        removed_props = set(b_props_map) - set(n_props_map)
        for prop in sorted(removed_props):
            brk.append(f"{ctx}: property removed: {prop}")

        b_req = set(base_schema.get("required") or [])
        n_req = set(new_schema.get("required") or [])
        new_required = n_req - b_req
        for prop in sorted(new_required):
            brk.append(f"{ctx}: new required property: {prop}")

        # Recurse on intersecting props
        for prop in sorted(set(b_props_map) & set(n_props_map)):
            brk.extend(
                diff_schemas(f"{ctx} property '{prop}'", b_props_map[prop] or {}, n_props_map[prop] or {})
            )
        return brk  # object handled

    # Strings: detect tighter constraints
    if (bt or nt) == "string" or any(k in base_schema or k in new_schema for k in ("minLength", "maxLength", "pattern")):
        b_min_len = base_schema.get("minLength")
        n_min_len = new_schema.get("minLength")
        if isinstance(b_min_len, int) and isinstance(n_min_len, int) and n_min_len > b_min_len:
            brk.append(f"{ctx}: minLength increased ({b_min_len} -> {n_min_len})")
        # Adding a new minLength where none existed is also a restriction
        if b_min_len is None and isinstance(n_min_len, int) and n_min_len > 0:
            brk.append(f"{ctx}: new restrictive minLength {n_min_len}")

        b_max_len = base_schema.get("maxLength")
        n_max_len = new_schema.get("maxLength")
        if isinstance(b_max_len, int) and isinstance(n_max_len, int) and n_max_len < b_max_len:
            brk.append(f"{ctx}: maxLength decreased ({b_max_len} -> {n_max_len})")
        # Introducing a maxLength where none existed is a restriction
        if b_max_len is None and isinstance(n_max_len, int):
            brk.append(f"{ctx}: new restrictive maxLength {n_max_len}")

        b_pat = base_schema.get("pattern")
        n_pat = new_schema.get("pattern")
        if b_pat != n_pat:
            # Adding or changing pattern narrows / changes accepted values (treat as breaking)
            if n_pat and not b_pat:
                brk.append(f"{ctx}: new restrictive pattern added ({n_pat})")
            elif b_pat and n_pat and b_pat != n_pat:
                brk.append(f"{ctx}: pattern changed ({b_pat} -> {n_pat})")
        # Removal of pattern (n_pat is None while b_pat existed) is a widening; not breaking.
        # Continue; strings have no deeper schema to recurse into.
        return brk

    # Arrays: check items + NEW: minItems/maxItems constraints
    if (bt or nt) == "array" or ("items" in base_schema or "items" in new_schema):
        b_min = base_schema.get("minItems")
        n_min = new_schema.get("minItems")
        if isinstance(b_min, int) and isinstance(n_min, int) and n_min > b_min:
            brk.append(f"{ctx}: minItems increased ({b_min} -> {n_min})")

        b_max = base_schema.get("maxItems")
        n_max = new_schema.get("maxItems")
        if isinstance(b_max, int) and isinstance(n_max, int) and n_max < b_max:
            brk.append(f"{ctx}: maxItems decreased ({b_max} -> {n_max})")

        b_items = base_schema.get("items") or {}
        n_items = new_schema.get("items") or {}
        brk.extend(diff_schemas(f"{ctx} items", b_items, n_items))
        return brk

    return brk


def collect_breaking_changes(baseline: dict[str, Any], new: dict[str, Any]) -> list[str]:
    brk: list[str] = []
    base_paths = iter_paths(baseline)
    new_paths = iter_paths(new)
    removed_paths = base_paths - new_paths
    for p in sorted(removed_paths):
        brk.append(f"Removed path: {p}")
    for p in sorted(base_paths & new_paths):
        base_item = baseline["paths"].get(p) or {}
        new_item = new["paths"].get(p) or {}
        base_methods = iter_methods(base_item)
        new_methods = iter_methods(new_item)
        removed_methods = base_methods - new_methods
        for m in sorted(removed_methods):
            brk.append(f"Removed operation: {m.upper()} {p}")
        for m in sorted(base_methods & new_methods):
            base_op = base_item.get(m, {}) or {}
            new_op = new_item.get(m, {}) or {}
            base_resps = responses_of(base_op)
            new_resps = responses_of(new_op)
            for code in sorted(base_resps - new_resps):
                brk.append(f"Removed response {code}: {m.upper()} {p}")
            base_rb = request_body(base_op)
            new_rb = request_body(new_op)
            if base_rb and not new_rb:
                brk.append(f"Removed requestBody: {m.upper()} {p}")
            elif base_rb and new_rb:
                base_ct = content_types_of(base_rb)
                new_ct = content_types_of(new_rb)
                for ct in sorted(base_ct - new_ct):
                    brk.append(f"Removed requestBody content-type '{ct}': {m.upper()} {p}")
                base_schema = schema_of(base_rb.get("content", {}))
                new_schema = schema_of(new_rb.get("content", {}))
                if isinstance(base_schema, dict) and isinstance(new_schema, dict):
                    brk.extend(diff_schemas(f"{m.upper()} {p} request", base_schema, new_schema))
            base_resp_map = base_op.get("responses") or {}
            new_resp_map = new_op.get("responses") or {}
            for code in (base_resps & new_resps):
                base_resp = base_resp_map.get(code, {}) or {}
                new_resp = new_resp_map.get(code, {}) or {}
                base_ct = content_types_of(base_resp)
                new_ct = content_types_of(new_resp)
                for ct in sorted(base_ct - new_ct):
                    brk.append(f"Removed response {code} content-type '{ct}': {m.upper()} {p}")
    return brk


def collect_additions(baseline: dict[str, Any], new: dict[str, Any]) -> list[str]:
    adds: list[str] = []
    base_paths = iter_paths(baseline)
    new_paths = iter_paths(new)
    for p in sorted(new_paths - base_paths):
        adds.append(f"Added path: {p}")
    for p in sorted(base_paths & new_paths):
        base_item = baseline["paths"].get(p) or {}
        new_item = new["paths"].get(p) or {}
        base_methods = iter_methods(base_item)
        new_methods = iter_methods(new_item)
        for m in sorted(new_methods - base_methods):
            adds.append(f"Added operation: {m.upper()} {p}")
        for m in sorted(base_methods & new_methods):
            base_op = base_item.get(m, {}) or {}
            new_op = new_item.get(m, {}) or {}
            for code in sorted(responses_of(new_op) - responses_of(base_op)):
                adds.append(f"Added response {code}: {m.upper()} {p}")
            base_rb = request_body(base_op)
            new_rb = request_body(new_op)
            if (not base_rb) and new_rb:
                adds.append(f"Added requestBody: {m.upper()} {p}")
    return adds


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(
            "Usage: openapi_diff.py <baseline.json> <new.json> [--report <txt-file>] [--json-report <json-file>]",
            file=sys.stderr,
        )
        return 2
    baseline_path = Path(argv[1])
    new_path = Path(argv[2])
    report_path: Path | None = None
    json_report_path: Path | None = None
    if "--report" in argv:
        idx = argv.index("--report")
        try:
            report_path = Path(argv[idx + 1])
        except Exception:
            print("Missing path after --report", file=sys.stderr)
            return 2
    if "--json-report" in argv:
        idx = argv.index("--json-report")
        try:
            json_report_path = Path(argv[idx + 1])
        except Exception:
            print("Missing path after --json-report", file=sys.stderr)
            return 2
    baseline = load_spec(baseline_path)
    new = load_spec(new_path)
    breaking = collect_breaking_changes(baseline, new)
    additions = collect_additions(baseline, new)

    payload = {
        "breaking": breaking,
        "additions": additions,
        "baseline_path": str(baseline_path),
        "new_path": str(new_path),
        "status": "breaking" if breaking else "ok",
    }

    lines: list[str] = []
    lines.append("== OpenAPI Semantic Diff ==")
    lines.append(f"Baseline: {baseline_path}")
    lines.append(f"New:      {new_path}")
    lines.append("")
    if breaking:
        lines.append("Breaking changes:")
        lines += [f"  - {b}" for b in breaking]
    else:
        lines.append("Breaking changes: none ✅")
    lines.append("")
    if additions:
        lines.append("Additions (non-breaking):")
        lines += [f"  + {a}" for a in additions]
    else:
        lines.append("Additions: none")
    out = "\n".join(lines)
    print(out)
    if report_path:
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(out, encoding="utf-8")
        except Exception as e:  # pragma: no cover - best effort
            print(f"[WARN] Could not write report {report_path}: {e}", file=sys.stderr)
    if json_report_path:
        try:
            json_report_path.parent.mkdir(parents=True, exist_ok=True)
            json_report_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:  # pragma: no cover - best effort
            print(f"[WARN] Could not write JSON report {json_report_path}: {e}", file=sys.stderr)
    return 1 if breaking else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv))
