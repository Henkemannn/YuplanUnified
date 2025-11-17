Root cause:
- Raw db.execute("SELECT ...") without sqlalchemy.text under SQLAlchemy 2.x led to 500 on PUT /menu-choice.

Fix:
- Import: from sqlalchemy import text
- Change: db.execute(text("SELECT site_id FROM departments WHERE id=:id"), {"id": department_id})

Verification:
- pytest -q tests/api/test_menu_choice.py -vv → 7 passed.
- Full test suite → 353 passed, 7 skipped.

ADR-lint:
- Removed placeholder adr/ADR-00X-global-429-standardization.md to satisfy ADR filename/sequence checks.

Release relevance:
- Critical for 0.3.0: removes an actual 500 in menu-choice PUT and unblocks ADR lint.