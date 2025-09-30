from __future__ import annotations

from dataclasses import dataclass
from typing import Set


@dataclass
class FeatureRegistry:
    """In-memory feature flag registry.

    Later this will query database (tenant_feature_flags table) but for now
    it's a simple allow-all for core + module-implied features.
    """
    _flags: Set[str] = None  # type: ignore

    def __post_init__(self):
        if self._flags is None:
            # seed with known features (namespaced proposals)
            self._flags = {
                # Core capabilities
                "menus", "diet", "attendance", 
                # Export / import
                "export.docx", "import.docx",
                # Modules
                "module.municipal", "module.offshore",
                # Domain feature areas
                "turnus", "waste.metrics", "prep.tasks", "freezer.tasks", "messaging",
                # Documentation UI
                "openapi_ui",
                # Inline experimental UI
                "inline_ui",
            }

    def enabled(self, name: str) -> bool:
        # Secure-by-default: only True if explicitly registered
        return name in self._flags

    def add(self, name: str):  # dynamic enabling
        self._flags.add(name)

    def list(self):
        return sorted(self._flags)
