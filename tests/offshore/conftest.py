from __future__ import annotations

from contextlib import suppress
import logging

import pytest

from core import db as db_mod


def _snapshot_logger(name: str) -> dict[str, object]:
    logger = logging.getLogger(name)
    return {
        "handlers": list(logger.handlers),
        "filters": list(logger.filters),
        "level": logger.level,
        "propagate": logger.propagate,
        "disabled": logger.disabled,
    }


def _restore_logger(name: str, snapshot: dict[str, object]) -> None:
    logger = logging.getLogger(name)
    logger.handlers = list(snapshot["handlers"])
    logger.filters = list(snapshot["filters"])
    logger.setLevel(int(snapshot["level"]))
    logger.propagate = bool(snapshot["propagate"])
    logger.disabled = bool(snapshot["disabled"])


@pytest.fixture(autouse=True)
def _restore_core_db_singletons() -> None:
    """Keep Offshore tests from leaking the process-global SQLAlchemy singleton."""
    previous_engine = db_mod._engine
    previous_session_factory = db_mod._SessionFactory
    previous_root_logger = _snapshot_logger("root")
    previous_app_factory_logger = _snapshot_logger("core.app_factory")
    previous_unified_logger = _snapshot_logger("unified")
    previous_metrics_logger = _snapshot_logger("metrics")
    try:
        yield
    finally:
        current_session_factory = db_mod._SessionFactory
        if current_session_factory is not None:
            with suppress(Exception):
                current_session_factory.remove()
        current_engine = db_mod._engine
        if current_engine is not None and current_engine is not previous_engine:
            with suppress(Exception):
                current_engine.dispose()
        db_mod._engine = previous_engine
        db_mod._SessionFactory = previous_session_factory
        _restore_logger("metrics", previous_metrics_logger)
        _restore_logger("unified", previous_unified_logger)
        _restore_logger("core.app_factory", previous_app_factory_logger)
        _restore_logger("root", previous_root_logger)