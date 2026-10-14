from __future__ import annotations

from pathlib import Path

import pytest

from core.app_factory import create_app
from core.db import create_all


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path}"


def test_create_app_refuses_testing_against_protected_pilot_db(tmp_path, monkeypatch):
    protected_db = tmp_path / "instance" / "yuplan_mvp.db"
    monkeypatch.setenv("DATABASE_URL", _sqlite_url(protected_db))

    with pytest.raises(RuntimeError, match="Refusing to start TESTING app against protected pilot database"):
        create_app({"TESTING": True, "SECRET_KEY": "test"})


def test_create_all_refuses_testing_against_protected_pilot_db(tmp_path, monkeypatch):
    protected_db = tmp_path / "instance" / "yuplan_mvp.db"
    monkeypatch.setenv("DATABASE_URL", _sqlite_url(protected_db))

    app = create_app({"TESTING": False, "SECRET_KEY": "test"})
    assert protected_db.exists()
    before_size = protected_db.stat().st_size

    app.config["TESTING"] = True
    with app.app_context():
        with pytest.raises(RuntimeError, match="Refusing to run TESTING destructive operations on protected pilot database"):
            create_all()

    assert protected_db.exists()
    assert protected_db.stat().st_size == before_size


def test_testing_allows_in_memory_sqlite(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")

    app = create_app({"TESTING": True, "SECRET_KEY": "test"})
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"

    with app.app_context():
        create_all()


def test_testing_allows_isolated_temporary_sqlite_db(tmp_path, monkeypatch):
    temp_db = tmp_path / "isolated" / "test_app.db"
    monkeypatch.setenv("DATABASE_URL", _sqlite_url(temp_db))

    app = create_app({"TESTING": True, "SECRET_KEY": "test"})
    assert app.config["SQLALCHEMY_DATABASE_URI"].endswith("test_app.db")

    with app.app_context():
        create_all()

    assert temp_db.exists()


def test_non_testing_allows_protected_pilot_db(tmp_path, monkeypatch):
    protected_db = tmp_path / "instance" / "yuplan_mvp.db"
    monkeypatch.setenv("DATABASE_URL", _sqlite_url(protected_db))

    app = create_app({"TESTING": False, "SECRET_KEY": "test"})
    assert app.config["SQLALCHEMY_DATABASE_URI"].endswith("yuplan_mvp.db")
    assert protected_db.exists()
