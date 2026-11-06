from __future__ import annotations

import datetime
import re

from docx import Document  # type: ignore
from docx.table import Table  # type: ignore
from docx.text.paragraph import Paragraph  # type: ignore
from docx.oxml.ns import qn  # type: ignore

from .base import ImportedMenuItem, MenuImporter, MenuImportResult, WeekImport, normalize_day

_WEEK_HEADING_RE = re.compile(
    r"^\s*(?:(?:vecka|week)\s*[:.]?\s*|v\.\s*)(\d{1,2})"
    r"(?:\s*(?:·|[-.])\s*(\d{4})|\s+(\d{4}))?"
    r"(?:\s*(?:\r?\n\s*)?"
    r"(?:måndag|tisdag|onsdag|torsdag|fredag|lördag|söndag|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s*:?)?\s*$",
    re.IGNORECASE,
)
_TABLE_HEADERS = {
    "dag": "day",
    "lunch alt 1": "alt1",
    "lunch alt 2": "alt2",
    "dessert": "dessert",
    "kvallsmat": "evening",
}
_NON_DISH_PHRASES = [
    "med reservation för ändringar",
    "ni når oss på telefon",
    "allt med röd text",
]
_PHONE_RE = re.compile(r"\b07\d{1,2}[-\s]?\d{2,3}[-\s]?\d{2,3}\b")


class DocxMenuImporter(MenuImporter):
    """Adapts legacy kommun Word parser to unified model.
    Focus: Alt1/Alt2/Dessert/Kväll mapping.
    """

    def can_handle(self, filename: str, mimetype: str | None, first_bytes: bytes) -> bool:
        return filename.lower().endswith(".docx")

    def parse(self, file_bytes: bytes, filename: str) -> MenuImportResult:
        from io import BytesIO

        doc = Document(BytesIO(file_bytes))
        sections = self._collect_ordered_sections(doc)
        if not sections:
            return MenuImportResult(
                weeks=[],
                errors=["Could not detect any week number; supply week manually."],
                warnings=[],
            )

        results: list[WeekImport] = []
        warnings: list[str] = []
        errors: list[str] = []
        for section in sections:
            items = list(section["table_items"])
            items.extend(self._extract_items(section["lines"], section["year"], section["week"]))
            if items:
                results.append(WeekImport(year=section["year"], week=section["week"], items=items))
            else:
                warnings.append(
                    f"No menu items recognized for week {section['week']}/{section['year']}."
                )

        if not results:
            errors.append("No menu items recognized; no menus were created.")
        return MenuImportResult(weeks=results, warnings=warnings, errors=errors)

    def _collect_ordered_sections(self, document: Document) -> list[dict[str, object]]:
        sections: list[dict[str, object]] = []
        current: dict[str, object] | None = None
        current_year = datetime.date.today().year

        for child in document.element.body.iterchildren():
            if child.tag == qn("w:p"):
                block = Paragraph(child, document).text.strip()
                if not block:
                    continue
                heading = _WEEK_HEADING_RE.fullmatch(block)
                if heading:
                    current = self._start_section(
                        sections,
                        week=int(heading.group(1)),
                        year=int(heading.group(2) or heading.group(3) or current_year),
                    )
                elif current is not None:
                    current["lines"].extend(
                        line.strip() for line in block.splitlines() if line.strip()
                    )
            elif child.tag == qn("w:tbl") and current is not None:
                table = Table(child, document)
                table_items = self._parse_menu_table(table)
                if table_items is None:
                    for row in table.rows:
                        for cell in row.cells:
                            current["lines"].extend(
                                line.strip()
                                for line in cell.text.splitlines()
                                if line.strip()
                            )
                else:
                    current["table_items"].extend(table_items)

        return sections

    def _start_section(
        self,
        sections: list[dict[str, object]],
        *,
        week: int,
        year: int,
    ) -> dict[str, object]:
        if not 1 <= week <= 53:
            raise ValueError(f"invalid ISO week {week}/{year}")
        try:
            datetime.date.fromisocalendar(year, week, 1)
        except ValueError as exc:
            raise ValueError(f"invalid ISO week {week}/{year}") from exc
        section: dict[str, object] = {
            "week": week,
            "year": year,
            "lines": [],
            "table_items": [],
        }
        sections.append(section)
        return section

    def _parse_menu_table(self, table: Table) -> list[ImportedMenuItem] | None:
        if not table.rows:
            return None

        def normalize_header(value: str) -> str:
            value = re.sub(r"\s+", " ", value.strip().casefold())
            return value.replace("å", "a").replace("ä", "a").replace("ö", "o")

        headers = [normalize_header(cell.text) for cell in table.rows[0].cells]
        if len(headers) != 5 or any(header not in _TABLE_HEADERS for header in headers):
            return None
        if headers[0] != "dag" or len(set(headers)) != len(headers):
            return None

        items: list[ImportedMenuItem] = []
        for row in table.rows[1:]:
            cells = [re.sub(r"\s+", " ", cell.text.replace("\u00a0", " ").strip()) for cell in row.cells]
            if len(cells) < len(headers):
                cells.extend([""] * (len(headers) - len(cells)))
            day_text = row.cells[0].text.replace("\u00a0", " ").strip()
            day = normalize_day(re.split(r"[\r\n]", day_text, maxsplit=1)[0].strip())
            if day is None:
                continue
            for index, value in enumerate(cells[: len(headers)]):
                variant = _TABLE_HEADERS[headers[index]]
                if variant == "day" or value.strip().casefold() in {"", "-", "–", "—"}:
                    continue
                if variant == "evening":
                    meal, variant_type, category = "dinner", "main", "evening"
                elif variant == "dessert":
                    meal, variant_type, category = "lunch", "dessert", "dessert"
                else:
                    meal, variant_type, category = "lunch", variant, "main"
                items.append(
                    ImportedMenuItem(
                        day=day,
                        meal=meal,
                        variant_type=variant_type,
                        dish_name=value,
                        category=category,
                        source_labels=[variant],
                    )
                )
        return items

    def _extract_items(self, lines: list[str], year: int, week: int) -> list[ImportedMenuItem]:
        items: list[ImportedMenuItem] = []
        current_day = None
        current_ctx: dict[str, str] | None = None
        # Patterns for variants
        alt_patterns = [
            ("alt1", re.compile(r"^(Alt\s*1:|Alternativ\s*1:|Lunch:)", re.IGNORECASE)),
            ("alt2", re.compile(r"^(Alt\s*2:|Alternativ\s*2:)", re.IGNORECASE)),
            ("dessert", re.compile(r"^(Dessert:)", re.IGNORECASE)),
            ("evening", re.compile(r"^(Kväll:)", re.IGNORECASE)),
        ]

        def norm_line(s: str) -> str:
            s = s.replace("\u00a0", " ").strip()
            return re.sub(r"\s+", " ", s)

        def is_non_dish_line(s: str) -> bool:
            low = s.lower().strip()
            if not low:
                return True
            for phrase in _NON_DISH_PHRASES:
                if phrase in low:
                    return True
            if _PHONE_RE.search(low):
                return True
            return False

        for raw in lines:
            for sub in raw.split("\n"):
                line = norm_line(sub)
                if not line:
                    continue
                if is_non_dish_line(line):
                    continue
                # Day detection: direct localized token detection via normalize_day map below
                # Try localized day tokens
                lower = line.lower()
                day_token = None
                for token, eng in list(
                    {k: v for k, v in normalize_day.__globals__["_day_map"].items()}.items()
                ):
                    if re.match(rf"^\b{re.escape(token)}\b", lower):
                        day_token = eng
                        break
                if day_token:
                    current_day = day_token
                    current_ctx = None
                    # Remove only the matched localized day token plus optional colon/punctuation and whitespace
                    # Strip first word and following punctuation
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        line_after = parts[1].strip()
                    else:
                        # fallback: remove first word
                        line_after = " ".join(line.split(" ")[1:]).strip()
                    if line_after:
                        current_ctx = self._handle_variant_line(items, current_day, line_after, alt_patterns, current_ctx)
                    continue
                if current_day:
                    current_ctx = self._handle_variant_line(items, current_day, line, alt_patterns, current_ctx)
        return items

    def _handle_variant_line(
        self,
        items: list[ImportedMenuItem],
        day: str,
        text: str,
        alt_patterns,
        current_ctx: dict[str, str] | None,
    ):
        matched = False
        for vtype, rgx in alt_patterns:
            m = rgx.match(text)
            if m:
                dish = text[m.end() :].strip()
                if not dish:
                    return current_ctx
                meal = "dinner" if vtype == "evening" else "lunch"
                canonical_variant = "main" if vtype == "evening" else vtype
                # Category inference: dessert -> dessert, evening -> evening, alts -> main
                if canonical_variant == "dessert":
                    category = "dessert"
                elif vtype == "evening":
                    category = "evening"
                else:
                    category = "main"
                current_ctx = {
                    "meal": meal,
                    "variant_type": canonical_variant,
                    "category": category,
                }
                items.append(
                    ImportedMenuItem(
                        day=day,
                        meal=meal,
                        variant_type=canonical_variant,
                        dish_name=dish,
                        category=category,
                        source_labels=[vtype],
                    )
                )
                matched = True
                break
        if not matched:
            if current_ctx is None:
                return current_ctx
            items.append(
                ImportedMenuItem(
                    day=day,
                    meal=current_ctx["meal"],
                    variant_type=current_ctx["variant_type"],
                    dish_name=text,
                    category=current_ctx["category"],
                    source_labels=["unlabeled"],
                )
            )
        return current_ctx
