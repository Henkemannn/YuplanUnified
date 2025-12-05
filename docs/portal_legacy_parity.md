Detta dokument sammanfattar hur Avdelningsportalen (department week) fungerar i legacy Kommun, och vilka constraints Unified måste följa.

- Roll & scope: Avdelningsportal för en specifik avdelning och vecka. Läs- och visningsroller enligt SAFE_UI_ROLES (enhetschef, kock, admin, superuser). Statistik (boende och specialkostsummeringar) är read-only.
- Vad vyn visar: Read-only statistik från Weekview/Planera-domäner (boendeantal, diets_summary) med Alt2-kontext. Menyval (Alt1/Alt2) visualiseras.
- Vilka actions användaren kan göra: Endast menyval (menu choice) får mutera portalens eget tillstånd. Inga ändringar av boende eller specialkost.
- Vilka data/beräkningar ligger bakom: Data komponerad via komposit-GET (se `docs/adr/ADR_department_portal_composite_and_etags.md`). ETag-baserad cache; residents och diets hämtas från Weekview/Planera, inte skrivs från portalen.

Constraints
- Portalen får aldrig skriva boende eller specialkost. Endast menu-choice endpoint är tillåten för mutation (ETag-säkrad).
- UI ska inte exponera formulär för residents/diets. Menyval länk/knapp är okej.
