from __future__ import annotations

from .base import MenuImporter, MenuImportResult


class CompositeMenuImporter:
    def __init__(self, importers: list[MenuImporter]):
        self.importers = importers

    def parse(self, file_bytes: bytes, filename: str, mimetype: str | None) -> MenuImportResult:
        first_bytes = file_bytes[:256]
        for imp in self.importers:
            try:
                if imp.can_handle(filename, mimetype, first_bytes):
                    return imp.parse(file_bytes, filename)
            except Exception as e:
                return MenuImportResult(
                    weeks=[], errors=[f"Importer {imp.__class__.__name__} failed: {e}"], warnings=[]
                )
        return MenuImportResult(weeks=[], errors=["No importer accepted file"], warnings=[])
