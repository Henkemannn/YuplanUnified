"""Helper launcher for local development.

Usage (PowerShell):
  $Env:PORT=5050
  $Env:DEMO_MODE=1
  python run_local.py

Features:
 - Honors PORT / YUPLAN_PORT (falls back to 5000)
 - Prints a compact route list (key public endpoints)
 - Shows whether DEMO_MODE is active
"""
from __future__ import annotations

import os

from app import app

PORT = int(os.environ.get("PORT") or os.environ.get("YUPLAN_PORT") or 5000)

def _print_routes():
    interesting = {"/","/landing","/coming-soon","/ping","/dashboard","/login"}
    print("\n[yuplan] Selected port:", PORT)
    print("[yuplan] DEMO_MODE:", os.environ.get("DEMO_MODE") == "1")
    print("[yuplan] Key routes:")
    for r in sorted(app.url_map.iter_rules(), key=lambda x: str(x)):
        rule_str = str(r)
        if rule_str in interesting:
            print("  ", f"{rule_str.ljust(15)} -> {r.endpoint}")
    print()

if __name__ == "__main__":
    _print_routes()
    app.run(host="127.0.0.1", port=PORT, debug=False)
