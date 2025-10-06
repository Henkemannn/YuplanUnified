## Ändringar
Kort sammanfattning av vad PR:en gör. Lista gärna moduler / filer med större påverkan.

## Strict Typing / Pocket
- [ ] Berör strikt ficka (lista):
- [ ] Nya moduler under `strict = True`
- [ ] Inga nya mypy-fel / `Any`-läckor

## Kvalitetsportar
- [ ] `ruff check .` grön (inga nya varningar)
- [ ] `mypy` grön för berörda paths
- [ ] Tester körda lokalt (`pytest -q`)
- [ ] Uppdaterad README vid ändrad ficklista / arkitektur
- [ ] Uppdaterad CHANGELOG (Unreleased) vid interna förbättringar
- [ ] `DECISIONS.md` uppdaterad (vid nya mönster / policybeslut)

## Säkerhet / Risk
- Påverkar auth / tokens? Beskriv risk & mitigering.
- Nya externa beroenden? Motivera.
- Datamodell migration? Länka Alembic-revision.

## Test
Beskriv nya testfall och varför de räcker. Edge cases täckta? Negativa scenarier?

## Manuell Verifiering (om relevant)
Lista korta manuella steg du kört (curl, UI, etc.).

## Riskbedömning
| Aspekt | Bedömning | Kommentar |
|--------|-----------|-----------|
| Auth / Security | låg / medel / hög | |
| Databas Migration | låg / medel / hög | |
| Prestanda | låg / medel / hög | |
| Underhåll / Komplext | låg / medel / hög | |

## Övrigt
Övriga noter eller uppföljningspunkter.
