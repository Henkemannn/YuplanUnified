from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOCS = [
    (ROOT / "docs" / "legacy_routes_weekview.md", "Legacy routes — Weekview"),
    (ROOT / "docs" / "legacy_routes_report.md", "Legacy routes — Report"),
    (ROOT / "docs" / "legacy_routes_admin.md", "Legacy routes — Admin"),
    (ROOT / "docs" / "legacy_rbac_ff.md", "Legacy RBAC & Feature Flags"),
    (ROOT / "docs" / "unified_mapping.md", "Unified mapping"),
]


def test_docs_exist_and_have_headings():
    for path, heading in DOCS:
        assert path.exists(), f"Missing doc: {path}"
        text = path.read_text(encoding="utf-8")
        assert heading in text, f"Heading '{heading}' not found in {path.name}"
    # Check specific section anchors are present
    um = (ROOT / "docs" / "unified_mapping.md").read_text(encoding="utf-8")
    for section in ("## Weekview", "## Report", "## Admin"):
        assert section in um, f"Missing section {section} in unified_mapping.md"
