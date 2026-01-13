# Unified Meal Details – /ui/planera/day (ui=unified)

Detta är den enhetliga (unified) vy för måltid/dag på toppen av den befintliga routen `/ui/planera/day`. Vyn introduceras stegvis och renderas när query-parametern `ui=unified` används.

## Innehåll
- Header: datum, veckodag, måltid (Lunch/Kvällsmat), avdelning, enhet.
- Kort: Meny, Specialkost & antal, Registreringar, Alt 2.
- Framtida sektioner: Prepp, Inköp, Frys, Recept (read-only placeholders med "Kommer senare…").

## Fas 1–2
Vyn är read-only i Phase 1–2 och fungerar som en framtida nav‑punkt för:
- Prepp (förberett enligt recept och meny)
- Inköp (inköpsunderlag per menydetalj)
- Frys (frysuttag och saldo)
- Recept (kopplade recept)

Syftet är att förbereda struktur och hooks för kommande moduler utan backend‑ändringar i detta skede.

## Referens
Se även `docs/portal_department_week.md` för den enhetliga veckovyn.
