from __future__ import annotations

DIET_FAMILY_TEXTUR = "Textur"
DIET_FAMILY_ALLERGY = "Allergi / Exkludering"
DIET_FAMILY_CHOICE = "Kostval"
DIET_FAMILY_ADAPTATION = "Anpassning"
DIET_FAMILY_OTHER = "Övrigt"

DIET_FAMILY_OPTIONS = [
    DIET_FAMILY_TEXTUR,
    DIET_FAMILY_ALLERGY,
    DIET_FAMILY_CHOICE,
    DIET_FAMILY_ADAPTATION,
    DIET_FAMILY_OTHER,
]


def normalize_diet_family(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in ("textur",):
        return DIET_FAMILY_TEXTUR
    if raw in ("allergi / exkludering", "allergi/exkludering", "allergi", "exkludering"):
        return DIET_FAMILY_ALLERGY
    if raw in ("kostval",):
        return DIET_FAMILY_CHOICE
    if raw in ("anpassning",):
        return DIET_FAMILY_ADAPTATION
    if raw in ("ovrigt", "övrigt"):
        return DIET_FAMILY_OTHER
    return DIET_FAMILY_OTHER


def infer_diet_family(name: str | None) -> str:
    txt = str(name or "").strip().lower()
    if not txt:
        return DIET_FAMILY_OTHER

    textur_keywords = (
        "timbal",
        "pat",
        "flyt",
        "pure",
        "pate",
        "konsistens",
        "lattugg",
        "passerad",
    )
    if any(k in txt for k in textur_keywords):
        return DIET_FAMILY_TEXTUR

    kostval_keywords = (
        "vegetar",
        "vegan",
        "pesc",
        "halal",
        "kosher",
    )
    if any(k in txt for k in kostval_keywords):
        return DIET_FAMILY_CHOICE

    allergy_keywords = (
        "gluten",
        "laktos",
        "mjolk",
        "fiskfri",
        "not",
        "nott",
        "agg",
        "soja",
        "utan ",
        "ej ",
        "allerg",
    )
    if any(k in txt for k in allergy_keywords):
        return DIET_FAMILY_ALLERGY

    adaptation_keywords = (
        "energi",
        "protein",
        "berik",
        "diabet",
        "anpass",
    )
    if any(k in txt for k in adaptation_keywords):
        return DIET_FAMILY_ADAPTATION

    return DIET_FAMILY_OTHER
