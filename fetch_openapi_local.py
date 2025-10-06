#!/usr/bin/env python3
"""Minimal CLI to fetch local OpenAPI spec without external deps.

Usage:
  python fetch_openapi_local.py --base-url http://localhost:5000 --output openapi.json

Tries /openapi.json then /docs/openapi.json.
Exit code 0 on success, 1 on failure.
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.request
import urllib.error
from typing import Tuple

FALLBACK_PATHS = ["/openapi.json", "/docs/openapi.json"]

def fetch_spec(base_url: str, timeout: float) -> Tuple[str, dict]:
    errors = []
    for path in FALLBACK_PATHS:
        url = base_url.rstrip("/") + path
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:  # nosec B310 (stdlib usage)
                data = resp.read()
            try:
                obj = json.loads(data)
            except json.JSONDecodeError as e:
                errors.append(f"{url} -> invalid JSON: {e}")
                continue
            if "openapi" not in obj:
                errors.append(f"{url} -> JSON missing 'openapi' key")
                continue
            return url, obj
        except (urllib.error.URLError, urllib.error.HTTPError) as e:  # pragma: no cover - network
            errors.append(f"{url} -> {e}")
    raise RuntimeError("All endpoints failed:\n" + "\n".join(errors))

def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch OpenAPI JSON (local CLI)")
    parser.add_argument("--base-url", dest="base_url", default="http://localhost:8000", help="Base URL (default: http://localhost:8000)")
    parser.add_argument("--output", dest="output", default="openapi.json", help="Output file path (default: openapi.json)")
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout seconds (default: 10)")
    args = parser.parse_args()

    try:
        used_url, spec = fetch_spec(args.base_url, args.timeout)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"Fetched from {used_url} -> {args.output}")
    return 0

if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
