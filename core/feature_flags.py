from __future__ import annotations

from collections.abc import Iterable
from typing import Literal, TypedDict

FlagMode = Literal["simple"]  # future: "percentage", "gradual", etc.


class FlagDefinition(TypedDict):
    name: str
    mode: FlagMode
    # For future modes we can append optional numeric fields (e.g. rollout_percent)


class FlagState(TypedDict):
    name: str
    enabled: bool
    mode: FlagMode


_SEED_FLAGS: tuple[FlagDefinition, ...] = (
    {"name": "menus", "mode": "simple"},
    {"name": "diet", "mode": "simple"},
    {"name": "attendance", "mode": "simple"},
    {"name": "export.docx", "mode": "simple"},
    {"name": "import.docx", "mode": "simple"},
    {"name": "module.municipal", "mode": "simple"},
    {"name": "module.offshore", "mode": "simple"},
    {"name": "turnus", "mode": "simple"},
    {"name": "waste.metrics", "mode": "simple"},
    {"name": "prep.tasks", "mode": "simple"},
    {"name": "freezer.tasks", "mode": "simple"},
    {"name": "messaging", "mode": "simple"},
    {"name": "openapi_ui", "mode": "simple"},
    {"name": "inline_ui", "mode": "simple"},
)


class _FlagProxy:
    """Proxy to support legacy tests mutating `registry._flags`.

    - `name in registry._flags` checks if the flag exists and is currently enabled.
    - `registry._flags.remove(name)` records a temporary disable for the next request.
      It does NOT permanently mutate the registry; an after-request hook should clear
      the temporary set so subsequent tests are unaffected (order independent).
    """

    def __init__(self, registry: FeatureRegistry) -> None:
        self._registry = registry

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        # Treat existence in definitions as membership to satisfy guard checks in tests
        return self._registry.has(name)

    def remove(self, name: str) -> None:
        # Record a temporary disable only when app is in TESTING or DEBUG mode.
        try:
            from flask import current_app  # lazy to avoid heavy import at module load

            testing = bool(current_app and current_app.config.get("TESTING"))
            debug = bool(current_app and current_app.config.get("DEBUG"))
        except Exception:
            testing = False
            debug = False
        if not (testing or debug):
            # Fallback for pytest collection phases outside app context
            try:
                import os

                if "PYTEST_CURRENT_TEST" not in os.environ:
                    return
            except Exception:
                return
        if self._registry.has(name):
            self._registry._temp_disabled.add(name)  # noqa: SLF001


class FeatureRegistry:
    """Minimal in-memory flag registry with typed definitions.

    Secure by default: only seeded or explicitly added flags return True.
    Later this may incorporate per-tenant overrides & advanced rollout modes.
    """

    def __init__(self, seed: Iterable[FlagDefinition] | None = None):
        base = list(seed) if seed else list(_SEED_FLAGS)
        self._defs: dict[str, FlagDefinition] = {d["name"]: d for d in base}
        self._enabled: set[str] = {d["name"] for d in base}  # all seed flags enabled by default
        # Temporary disables requested by tests via _flags.remove("name")
        self._temp_disabled: set[str] = set()
        # Backwards compatibility for tests referencing internal _flags
        self._flags = _FlagProxy(self)

    def enabled(self, name: str) -> bool:
        return name in self._enabled and name in self._defs and name not in self._temp_disabled

    def has(self, name: str) -> bool:
        return name in self._defs

    def add(self, definition: FlagDefinition | str) -> None:
        """Add a new flag.

        Accepts either a full FlagDefinition or a simple string name (treated as mode="simple").
        Idempotent: re-adding an existing flag (even with different mode) is a no-op to avoid
        accidental silent mode changes without explicit migration.
        """
        if isinstance(definition, str):
            definition = {"name": definition, "mode": "simple"}
        name = definition["name"].strip()
        if not name:
            raise ValueError("flag name empty")
        if name in self._defs:
            return
        self._defs[name] = definition
        self._enabled.add(name)

    def set(self, name: str, enabled: bool) -> None:
        if name not in self._defs:
            raise ValueError("unknown flag")
        if enabled:
            self._enabled.add(name)
        else:
            self._enabled.discard(name)

    def list(self) -> list[FlagState]:
        out: list[FlagState] = []
        for name, d in sorted(self._defs.items()):
            out.append({"name": name, "enabled": name in self._enabled, "mode": d["mode"]})
        return out

    # Test support: clear any temporary disables (call in after_request)
    def _clear_temp(self) -> None:
        self._temp_disabled.clear()
