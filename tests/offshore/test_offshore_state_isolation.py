from __future__ import annotations

from core import db as db_mod
from tests.offshore.test_offshore_ticket2 import _mk_app


def test_offshore_ticket2_creates_an_isolated_app() -> None:
    app = _mk_app()
    assert app.testing is True


def test_shared_db_singleton_is_restored_after_offshore() -> None:
    engine = db_mod._engine
    assert engine is None or not (
        engine.dialect.name == "sqlite" and engine.url.database == ":memory:"
    )