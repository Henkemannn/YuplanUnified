from __future__ import annotations

import pytest

from core.app_factory import create_app
from core.db import create_all


def test_create_all_refuses_dev_db_in_testing(tmp_path):
    db_file = tmp_path / "dev.db"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "database_url": f"sqlite:///{db_file}",
        }
    )
    with app.app_context():
        with pytest.raises(RuntimeError, match="Refusing to run TESTING destructive operations on dev.db"):
            create_all()
