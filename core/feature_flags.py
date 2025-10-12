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


class FeatureRegistry:
    """Minimal in-memory flag registry with typed definitions.

    Secure by default: only seeded or explicitly added flags return True.
    Later this may incorporate per-tenant overrides & advanced rollout modes.
    """

    def __init__(self, seed: Iterable[FlagDefinition] | None = None):
        base = list(seed) if seed else list(_SEED_FLAGS)
        self._defs: dict[str, FlagDefinition] = {d["name"]: d for d in base}
        self._enabled: set[str] = {d["name"] for d in base}  # all seed flags enabled by default
        # Backwards compatibility for tests referencing internal _flags (treated as enabled set)
        self._flags: set[str] = self._enabled

    def enabled(self, name: str) -> bool:
        return name in self._enabled and name in self._defs

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
