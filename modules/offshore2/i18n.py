from __future__ import annotations

from typing import Final

SUPPORTED_LOCALES: Final[tuple[str, ...]] = ("sv", "no", "en")

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "sv": {
        "offshore.brand": "Offshore",
        "offshore.nav.overview": "Översikt",
        "offshore.nav.settings": "Inställningar",
        "offshore.topbar.organization": "Organisation",
        "offshore.topbar.installation": "Installation",
        "offshore.topbar.support": "Support",
        "offshore.topbar.logout": "Logga ut",
        "offshore.topbar.profile": "Profil",
        "offshore.dashboard.title": "Offshore",
        "offshore.dashboard.subtitle": "Ny separat Offshore-startsida i Yuplan-familjen.",
        "offshore.dashboard.no_active_period": "Ingen aktiv arbetsperiod",
        "offshore.dashboard.no_active_period_body": "Arbetsperioder kommer senare samla meny, prep, frysplock och handover.",
        "offshore.dashboard.open_settings": "Öppna inställningar",
        "offshore.dashboard.today_placeholder": "Dagens meny, prep och frysplock kommer visas här.",
        "offshore.dashboard.roadmap": "Kommande steg",
        "offshore.dashboard.roadmap.installation": "Installation",
        "offshore.dashboard.roadmap.menu_cycle": "Menycykel",
        "offshore.dashboard.roadmap.work_period": "Arbetsperiod",
        "offshore.dashboard.roadmap.period_plan": "Periodplan",
        "offshore.settings.title": "Inställningar",
        "offshore.settings.subtitle": "Konfigurationsskelett för Offshore.",
        "offshore.settings.installation": "Installation",
        "offshore.settings.period_templates": "Periodmallar",
        "offshore.settings.work_positions": "Virtuella arbetspositioner",
        "offshore.settings.work_positions_body": "Kokk 1, Kokk 2, Dagkock A och Nattkock B är planerade domänkoncept.",
        "offshore.settings.menu_cycle": "Menycykel",
        "offshore.settings.default_portions": "Standardportioner",
        "offshore.settings.permissions": "Behörigheter",
        "offshore.settings.placeholder": "Den här sektionen är ännu inte aktiv.",
        "offshore.settings.coming_later": "Kommer i senare ticket",
    },
    "no": {
        "offshore.brand": "Offshore",
        "offshore.nav.overview": "Oversikt",
        "offshore.nav.settings": "Innstillinger",
        "offshore.topbar.organization": "Organisasjon",
        "offshore.topbar.installation": "Installasjon",
        "offshore.topbar.support": "Support",
        "offshore.topbar.logout": "Logg ut",
        "offshore.topbar.profile": "Profil",
        "offshore.dashboard.title": "Offshore",
        "offshore.dashboard.subtitle": "Ny separat Offshore-startside i Yuplan-familien.",
        "offshore.dashboard.no_active_period": "Ingen aktiv arbeidsperiode",
        "offshore.dashboard.no_active_period_body": "Arbeidsperioder vil senere samle meny, prep, fryselager og handover.",
        "offshore.dashboard.open_settings": "Åpne innstillinger",
        "offshore.dashboard.today_placeholder": "Dagens meny, prep og fryseplukk vises her senere.",
        "offshore.dashboard.roadmap": "Neste steg",
        "offshore.dashboard.roadmap.installation": "Installasjon",
        "offshore.dashboard.roadmap.menu_cycle": "Menycyklus",
        "offshore.dashboard.roadmap.work_period": "Arbeidsperiode",
        "offshore.dashboard.roadmap.period_plan": "Periodeplan",
        "offshore.settings.title": "Innstillinger",
        "offshore.settings.subtitle": "Konfigurasjonsskall for Offshore.",
        "offshore.settings.installation": "Installasjon",
        "offshore.settings.period_templates": "Periodemaler",
        "offshore.settings.work_positions": "Virtuelle arbeidsposisjoner",
        "offshore.settings.work_positions_body": "Kokk 1, Kokk 2, Dagkokk A og Nattkokk B er planlagte domeneidéer.",
        "offshore.settings.menu_cycle": "Menycyklus",
        "offshore.settings.default_portions": "Standard porsjoner",
        "offshore.settings.permissions": "Tilganger",
        "offshore.settings.placeholder": "Denne seksjonen er ikke aktiv ennå.",
        "offshore.settings.coming_later": "Kommer i en senere ticket",
    },
    "en": {
        "offshore.brand": "Offshore",
        "offshore.nav.overview": "Overview",
        "offshore.nav.settings": "Settings",
        "offshore.topbar.organization": "Organization",
        "offshore.topbar.installation": "Installation",
        "offshore.topbar.support": "Support",
        "offshore.topbar.logout": "Log out",
        "offshore.topbar.profile": "Profile",
        "offshore.dashboard.title": "Offshore",
        "offshore.dashboard.subtitle": "New standalone Offshore start page in the Yuplan family.",
        "offshore.dashboard.no_active_period": "No active work period",
        "offshore.dashboard.no_active_period_body": "Work periods will later collect menu, prep, freezer picking, and handover.",
        "offshore.dashboard.open_settings": "Open settings",
        "offshore.dashboard.today_placeholder": "Today\'s menu, prep, and freezer picks will appear here later.",
        "offshore.dashboard.roadmap": "Next steps",
        "offshore.dashboard.roadmap.installation": "Installation",
        "offshore.dashboard.roadmap.menu_cycle": "Menu cycle",
        "offshore.dashboard.roadmap.work_period": "Work period",
        "offshore.dashboard.roadmap.period_plan": "Period plan",
        "offshore.settings.title": "Settings",
        "offshore.settings.subtitle": "Configuration shell for Offshore.",
        "offshore.settings.installation": "Installation",
        "offshore.settings.period_templates": "Period templates",
        "offshore.settings.work_positions": "Virtual work positions",
        "offshore.settings.work_positions_body": "Cook 1, Cook 2, Day cook A, and Night cook B are planned domain concepts.",
        "offshore.settings.menu_cycle": "Menu cycle",
        "offshore.settings.default_portions": "Default portions",
        "offshore.settings.permissions": "Permissions",
        "offshore.settings.placeholder": "This section is not active yet.",
        "offshore.settings.coming_later": "Coming in a later ticket",
    },
}


def normalize_locale(value: str | None) -> str:
    candidate = (value or "").strip().lower()
    if candidate in SUPPORTED_LOCALES:
        return candidate
    return "sv"


def t(locale: str | None, key: str) -> str:
    lang = normalize_locale(locale)
    return _TRANSLATIONS.get(lang, {}).get(key) or _TRANSLATIONS["sv"].get(key, key)


def copy_for(locale: str | None) -> dict[str, str]:
    lang = normalize_locale(locale)
    out = dict(_TRANSLATIONS["sv"])
    out.update(_TRANSLATIONS.get(lang, {}))
    return out
