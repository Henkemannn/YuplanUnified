# Kommun 1.1 – aktuell lägesbild och MVP-TODO

Status: **WORKING STATUS / review pending** (inte en ändring av låsta arkitekturbeslut)  
Datum: **2026-10-30**  
Källa: verifierade GitHub-commits på `feat/planera-app-shell-2026-03-03`, tidigare manuella acceptansrapporter samt `docs/ground_truth/*`.  
Referens-HEAD: `6233b11cd4530ed0261992dc6be18af0357955c7`  
Arbetssätt: **1 order → 1 Copilot-rapport → review → nästa order**.

> **Viktigt:** "klar för pilot" för en enskild vy betyder inte att hela Kommun 1.1 är pilotgodkänd. En tidigare genomförd manuell kontroll eller fokuserad pytest-svit är inte bevis för ett grönt komplett kundflöde vid denna HEAD. Dokumentation/acceptans får inte markeras grönt enbart genom att en teknisk route finns.

## 1. Produkt- och releasegränser

- **Kommun 1.0:** befintlig legacy-/pilotbas för jämförelse.
- **Kommun 1.1:** aktuell Product2 + Planera 2.0-väg till en ny kommunpilot.
- **Yuplan 1.0:** större MVP med Kommun och det låsta Offshore 1.0-omfånget.
- **Builder/Menu:** kanonisk källa, gemensamma Dish/Component-editorer accepterade för 1.0 och frysta mot mikroputs.
- **Planera 2.0 Core:** generisk produktionsmotor; inga Kommun-specifika antaganden eller parallella beräkningsmotorer.
- **Future Lab:** Home, Hotel/Bankett, avancerad recept-/ingrediensutveckling, bred offshoreexpansion m.m. är inte blockerande för den aktuella Kommun-stängningen.

## 2. Verifierat genomfört (avgränsad acceptans)

| Leverans | Status | Evidens / begränsning |
| --- | --- | --- |
| Gemensamma Builder-editorer, kanonisk publicering och kärnarkitektur | Accepterad tidigare | Tidigare överlämning `docs/handoffs/KOMMUN_1_1_HANDOFF_2026-10-02.md` på separat dokumentationsbranch, samt Ground Truth. Inte omgranskad i detta docs-pass. |
| Planera 2.0 Page1/Page2, option-review/staleness, cohort/primary/modifier, adapter och meal orchestration | Etablerad grund | Ground Truth och accepterade tidigare checkpoints. |
| Page3: Översikt, Normalkost, Specialkost, produktion/packlista och utskrifter | Accepterad för nuvarande pilot-UI | `236ff859`, `0988ee1a`, `07376af5` och efterföljande manuell UI-acceptans. |
| Page3 → Kitchen Weekview: färdigmarkering med API och behörighet/ETag-regler | Implementerad/testad; äldre E2E-underlag finns | Ground Truth + fokustester; full **ny kunds** E2E till rapport är inte godkänd. |
| Produktionslistor 2.0: ISO-vecka/år, sju dagar, full lunch → Page3, bevarade historiska sparade listor | Accepterad för pilotens lunchflöde | `b23f22f4`, `9399350d`; 39 fokustester och manuell webbläsaracceptans. **Endast lunch** visas som sammanhängande måltidsunderlag här. |
| App Shell: stabilt dark/light-tema utan ljusa sidbytesblinkningar | Accepterad i webbläsare | `6233b11c`; 77 fokustester i sista kontrollen, ingen full suite-redovisning. |
| Gate 01: ny kund + site + separat adminsession + tenant-site-scope | Tidigare GO | `docs/KOMMUN_1_1_LIVE_ACCEPTANCE.md`; ska fortfarande ingå i sista fulla smoke. |

### Avgränsning för Produktionslistor

Produktionslistor är en **lätt navigeringsvy**, inte en andra källa till produktionsdata eller ett nytt spar-/arkivsystem. En dag kan i framtiden presentera flera serveringar, men nuvarande samlade Page3-route utan `option_id` gäller lunch. Kvällsmat, dessert, bankett eller flera separata lunchserveringar ska inte markeras färdiga i denna vy innan de har riktig identifiering, data och verifierade underlag.

## 3. Vad som fortfarande är öppet – prioriterad MVP-TODO

### P0 — live-acceptans / produktfakta, gör först

1. **Återuppta Gate 02: Avdelningar + registrerade behov, på en ren kund**. Kontrollera nuvarande Department Edit, antal, cohorts, varierat antal och Serveringstillägg. Tidigare UX-13–18 (hierarki, sparomfång, begrepp, serveringstillägg) är fortfarande öppna i live-ledgern tills nya bevis finns. Ändra inte sidan i stor skala utan konkret reproduktion och avgränsat beslut.
2. **Teknisk kontroll av Admin → Menyval / override-semantik**. Nuvarande portal- och adminflöden använder kanoniska `department_menu_choices`; ingen bevisad separat lagring för ursprungligt portalval, adminöverskrivning och effektivt val. Besluta minsta korrekta regel innan nya adminval byggs.
3. **Full clean-customer kedja**: onboarding → avdelning/behov → Builder-import/publicering → Department Portal val och explicit spara → Kitchen Weekview → Planera Page1/Page2 → Page3 → färdigmarkering → reload/login → Admin Weekview → rapport. Dokumentera skärmbild, tenant/site, status och faktisk data; ingen demo-förkonfigurerad E2E får räknas som ett nytt kundscenario.
4. **Måltidsvägar**: kontrollera lunch och pröva kvällsmat/dessert separat; rapportera stöd, saknad länk, blockerare eller uttryckligt scope-beslut. Utgå inte från att full-lunch-Page3 automatiskt betyder full måltidsparitet.

### P1 — måste bedömas före pilot GO; implementation efter uppmätt gap

5. **Reporting/statistik-brygga**: verifiera om aktuell rapport verkligen konsumerar Product2 cohort-quantities och completion (inte enbart legacy-registrering). Nuvarande `docs/report_current_behaviour.md` beskriver äldre rapportkällor. Klassificera som bekräftad funktion, blockerare eller kontrollerat avgränsat pilotkrav.
6. **Separat Servering / Packning**: håll Specialkost skild från avdelningsvisa serveringsanpassningar. Bevara befintliga `service_addons` och `department_service_addons`. Kontrollera behovet av daglig destinationsorienterad packvy; Page3:s specialkost-packlista är **inte i sig bevis för full sammanlagd packningsparitet**.
7. **Planera 1 vs 2.0 parity/cutover**: prov med realistisk vecka och samma menykälla/antal/avvikelser/val/destinationer; klassificera skillnad som regression, legacy-begränsning eller avsiktligt nytt beteende. Ingen okontrollerad cutover.
8. **iPad + polish endast där det blockerar uppgift**: 1024×768 och 768×1024, tom-/felstatus, rättigheter, popup/overlay, färger, menyval och tillagningsflöde. Återöppna inte färdiga Page3-/Produktionslistor-/Builder-ytor för smakändringar.
9. **Release-gate**: full regression, säkerhet/tenant-scope, migration, staging/deploy, ny kundsmoke och fryst/taggad pilotkandidat. Senaste **77 passed** är en *fokuserad* testslice, inte en fullständig releaseverifiering.

### P2 — efter Kommun 1.1 pilot GO

10. Återgå till **Offshore 1.0** med ny read-only census mot `OFFSHORE_1_0_MVP_LOCK.md`; därefter Yuplan 1.0-samlingsgate.
11. Framtida flera serveringar per dag, avancerad serveringsregel-editor, receptkonvertering/ingredienser, Home och Bankett hör utanför denna Kommun-gate om inget verkligt pilotblockerande krav uppkommer.
12. Noterad separat UI-/datafråga: text som återges `Centralk?ket` i visst sammanhang; diagnos av lagrat värde kontra rendering/encoding, inte automatiskt ett skäl till bred refaktor.

## 4. Beslutsunderlag / rekommenderad nästa gate

**Rekommendation: READ-ONLY acceptanscensus av Gate 02 – Avdelningar + behov, med därefter en livekontroll på ren kund.**

Varför: Här möts uppgifter som matar hela Planera 2.0-kedjan. Om kundadmin inte kan registrera och spara korrekt behov/antal eller förstå omfattningen av sina val, spelar en färdig Page3 mindre roll. Det är också den första uttryckligen öppna gaten i den senare live-acceptansledgern.

Föreslagen minsta arbetsorder till Copilot (först efter gemensamt beslut):
- verifiera nuvarande route och dataflöde för avdelningslistan, Department Edit och Registered Needs,
- mappa sparknappar mot persistence och tenant/site-scope,
- jämför UX-13–18 mot vad som *faktiskt* är implementerat på aktuell HEAD,
- bedöm blocker/HIGH och lämna en liten acceptanslista,
- **ingen implementation, migration, reset, commit eller push** i första census-gaten.

Beslutspunkten efter census: **A)** Gate 02 redan bra → liveacceptans och gå vidare till Menyval; **B)** konkret blocker → en avgränsad Copilot-order; **C)** produktbeslut krävs om antal/sparomfång → ta det innan kod.

## 5. Datakällor, skydd och dokumentationsdisciplin

Primära låsta beslut:
- `docs/ground_truth/YUPLAN_1_0_FINISHLINE.md`
- `docs/ground_truth/KOMMUN_1_0_MVP_LOCK.md`
- `docs/ground_truth/PLANERA_2_0_ARCHITECTURE_LOCK.md`
- `docs/ground_truth/PORTALS_ARCHITECTURE_LOCK.md`
- `docs/ground_truth/OFFSHORE_1_0_MVP_LOCK.md`

Operativ live-ledger: `docs/KOMMUN_1_1_LIVE_ACCEPTANCE.md`.  
Genomförande: `docs/roadmap.md`.

Lokalt på utvecklingsbranchen vid senaste checkpointen har följande **skyddade, ocommittade** förändringar rapporterats: `core/admin_repo.py`, `scripts/seed_ostergarden_from_json.py`, `scripts/seed_product2_e2e.py`, `artifacts/`. Dessa är inte en del av den nya lägesbilden, får inte skrivas över, och deras innehåll har inte granskats i denna dokumentationsuppdatering.

Detta dokument skiljer mellan **verifierat i git / tester**, **tidigare live-acceptans**, **kvarvarande öppet** och **framtida scope**. Ett nytt acceptance-GO måste grundas på bevis vid aktuell kod och miljö.
