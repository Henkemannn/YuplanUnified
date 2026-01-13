from __future__ import annotations

from core.limit_registry import get_limit, refresh


def test_tenant_override_beats_default():
    refresh(
        {"tenant:1:export_csv": {"quota": 2, "per": 60}, "export_csv": {"quota": 9, "per": 60}}, {}
    )
    ld, src = get_limit(1, "export_csv")
    assert src == "tenant" and ld["quota"] == 2


def test_default_fallback_when_no_tenant_entry():
    refresh({}, {"export_csv": {"quota": 5, "per": 60}})
    ld, src = get_limit(2, "export_csv")
    assert src == "default" and ld["quota"] == 5


def test_invalid_json_yields_safe_default():
    refresh("not-json", "also-bad")
    ld, src = get_limit(5, "unknown_limit")
    assert src == "fallback" and ld["quota"] == 5 and ld["per_seconds"] == 60


def test_clamp_and_caps():
    refresh({"export_big": {"quota": 0, "per": 9999999}}, {})
    ld, src = get_limit(1, "export_big")
    assert ld["quota"] == 1 and ld["per_seconds"] <= 86400
