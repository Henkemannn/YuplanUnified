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

**A–Ö-status uppdaterad 2026-10-31:** Användaren bekräftar att den löpande A–Ö-genomgången redan nått **Rapport**. Äldre "Gate 02 – OPEN" i historisk live-ledger är administrativ dokumentationsskuld, inte bevis för att Avdelningar behöver byggas eller testas om från början. Tidigare acceptans ska dock inte likställas med ett nytt komplett clean-customer release-GO.


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

1. **A–Ö-genomgången är redan framme vid Rapport – fortsätt där.** Enligt senare livearbete i oktober har kund/site, avdelningar, boendeantal/variationer, registrerade behov, Serveringstillägg, Builder/import/publicering och portalflöde redan granskats. Den äldre Gate 02-ledgern saknar sammanställd slutlig status, men detta är **inte** skäl att återstarta Avdelningar. Återöppna en tidigare yta endast vid konkret reproducerad blockerare.
2. **Teknisk kontroll av Admin → Menyval / override-semantik**. Nuvarande portal- och adminflöden använder kanoniska `department_menu_choices`; ingen bevisad separat lagring för ursprungligt portalval, adminöverskrivning och effektivt val. Besluta minsta korrekta regel innan nya adminval byggs.
3. **Full clean-customer kedja**: onboarding → avdelning/behov → Builder-import/publicering → Department Portal val och explicit spara → Kitchen Weekview → Planera Page1/Page2 → Page3 → färdigmarkering → reload/login → Admin Weekview → rapport. Dokumentera skärmbild, tenant/site, status och faktisk data; ingen demo-förkonfigurerad E2E får räknas som ett nytt kundscenario.
4. **Måltidsvägar**: kontrollera lunch och pröva kvällsmat/dessert separat; rapportera stöd, saknad länk, blockerare eller uttryckligt scope-beslut. Utgå inte från att full-lunch-Page3 automatiskt betyder full måltidsparitet.

### P1 — måste bedömas före pilot GO; implementation efter uppmätt gap

5. **Rapport – nästa aktiva A–Ö-gate**: verifiera vad dagens rapport faktiskt visar (avdelningsval, antal, specialkost, produktion, completion), vilka datakällor den läser och om den konsumerar Product2 cohort-quantities/completion eller bara legacy-registrering. `docs/report_current_behaviour.md` beskriver de äldre rapportkällorna. Börja med read-only census och live-screenshot, klassificera sedan konkreta luckor.
6. **Serveringstillägg – enkel köksvisning saknas**: visa befintliga registreringar/antal/anteckningar direkt under avdelningsnamn i Kitchen Weekview och via Tillägg-ikon bredvid Lunch i Produktionslistor. Listan grupperas per tillägg med en avdelningsrad och dess anmärkning. Visa även informationen avdelningsvis vid packning, men ingen menylogik/ny beräkningsmotor/ny Page3-flik; se §4b.
7. **Planera 1 vs 2.0 parity/cutover**: prov med realistisk vecka och samma menykälla/antal/avvikelser/val/destinationer; klassificera skillnad som regression, legacy-begränsning eller avsiktligt nytt beteende. Ingen okontrollerad cutover.
8. **iPad + polish endast där det blockerar uppgift**: 1024×768 och 768×1024, tom-/felstatus, rättigheter, popup/overlay, färger, menyval och tillagningsflöde. Återöppna inte färdiga Page3-/Produktionslistor-/Builder-ytor för smakändringar.
9. **Release-gate**: full regression, säkerhet/tenant-scope, migration, staging/deploy, ny kundsmoke och fryst/taggad pilotkandidat. Senaste **77 passed** är en *fokuserad* testslice, inte en fullständig releaseverifiering.

### P2 — efter Kommun 1.1 pilot GO

10. Återgå till **Offshore 1.0** med ny read-only census mot `OFFSHORE_1_0_MVP_LOCK.md`; därefter Yuplan 1.0-samlingsgate.
11. Framtida flera serveringar per dag, avancerad serveringsregel-editor, receptkonvertering/ingredienser, Home och Bankett hör utanför denna Kommun-gate om inget verkligt pilotblockerande krav uppkommer.
12. Noterad separat UI-/datafråga: text som återges `Centralk?ket` i visst sammanhang; diagnos av lagrat värde kontra rendering/encoding, inte automatiskt ett skäl till bred refaktor.

## 4. Beslutsunderlag / rekommenderad nästa gate

**Rekommendation: fortsätt A–Ö på Rapport, inte en omstart på Avdelningar.**

Varför: A–Ö-arbetet har redan nått Rapport. Rapporteringens koppling till Planera 2.0- och färdigmarkeringsdata är ännu inte bevisad. Den identifierade luckan i hur köket ser Serveringstillägg bör få en egen separat Servering/Packning-gate efter rapportcensus (eller tidigare endast om dagens verkliga arbetsflöde blockeras).

Föreslagen minsta arbetsorder till Copilot (först efter gemensamt beslut):
- kartlägg befintliga Rapport-routes/UI/services och om de läser Product2 quantity/completion eller legacy-registrering,
- verifiera aktuell rapportupplevelse med verkliga data och en skärmbild,
- mappa dagens Serveringstillägg från Admin/Portal/legacy mot saknad köksvy (read-only; inget skrivande),
- dokumentera vilka skillnader som blockerar pilot respektive kan vänta,
- **ingen implementation, migration, reset, commit eller push** i första census-gaten.

Beslutspunkt efter rapportcensus: **A)** rapporten korrekt → gå vidare i A–Ö; **B)** rapporten saknar Product2-truth → en avgränsad brygga; **C)** servering/packning hindrar arbetet → prioritera separat köksvy. Tidigare godkända A–Ö-delar förblir stängda utan ny buggevidens.

## 4b. Serveringstillägg i köksvyer — beslutad MVP-avgränsning 2026-10-31

**Produktbeslut:** Yuplan 1.0 ska **endast visa den information som faktiskt är registrerad på avdelningen**: tillägg/preferens, sparat antal där det finns samt anteckning/instruktion. Personalen avgör själv när maten ska tillverkas och vilka tillägg som är aktuella mot dagens meny. **Ingen automatisk menyanalys, tolkning av fritext, substitutionsmotor, ny produktionskalkyl, variantgenerering eller beslut om mos/sallad ska göras i denna MVP-gate.**

### Placering

1. **Kitchen Weekview**: Under avdelningens namn visas en kort, diskret rad med stående registrerade serveringsönskemål/anteckningar, t.ex. `Aldrig potatis – mos istället`. Återge användarens faktiska text; hitta inte på en regel från dagens publicerade meny. Håll skillnad mot personbaserad Specialkost.
2. **Produktionslistor / veckolistan**: Behåll befintlig Lunch-knapp till Page3 oförändrad. Placera en tydlig men lågmäld **Tillägg-ikon** bredvid Lunch för relevant dag/måltid. Klick öppnar registrerade serveringstillägg i samma kökskontext, utan att navigera in i avdelningsadministrationen.
3. **Tilläggslistan – grupperat per registrerat tillägg**: `Mos → Avd 11: 4; Avd 12: 5` och `Sallad → Avd 11: 6; Avd 12: 8 (Aldrig tomat)`. Kommentar står direkt vid **rätt avdelningsrad**. Visa inte automatisk "sallad utan tomat"-produktvariant; det är en instruktion till personalen.
4. **Packlistor – per avdelning (MVP-KRAV)**: Där köket packar till Avdelning 11 ska **Avdelning 11:s registrerade Serveringstillägg, antal och kommentarer** stå direkt under den avdelningen i packlistan, tillsammans med övrig packinformation. Ingen separat administrationsvy behöver öppnas. Samma sak för varje annan avdelning. Kontrollera befintliga packlistor/routemallar innan beslut om exakt UI-placering. **Skapa inte ny packmotor och skriv inte till nya tabeller.**
5. **Page3**: Lägg **inte** till en ny flik i nuvarande gate. Page3:s låsta Översikt/Normalkost/Specialkost och färdigmarkering lämnas oförändrade. Framtida ingång kan övervägas först efter faktisk nytta.

### Datakontrakt / icke-mål

- Läs befintliga site-/department-scopade `service_addons` och `department_service_addons` samt gällande registreringsfält (`service_scope`, `quantity_mode`, lunch-/dinner-antal, anteckning) enligt det befintliga kontraktet.
- **Enbart läsprojektion.** Visa redan registrerade antal utan ny produktionskalkyl eller ny totalsummering. Om ett val avser `whole_department` och inga fasta antal finns, återge det begripligt som `Hela avdelningen` i första versionen i stället för att hitta på en siffra. Håll tidigare verifierad semantik oförändrad.
- Måltidskontext får filtrera det **redan registrerade** scope:t (lunch/kväll/alla serveringar); den får inte tolka maträtt eller avgöra om tillägget "behövs" idag.
- Skilj serveringstillägg/avdelningsönskemål från Specialkost/individkrav. Återge inte interna privata fält på avdelningsportaler; köksvyn ska använda avsedda serveringsfält.
- Existerande legacylistor och tidigare addonregistreringar får inte brytas.
- Tidigare långsiktiga idéer om menyberoende substitutionsregler/resolver finns i Ground Truth för framtiden, men **är uttryckligen utanför denna 1.0-implementation**. Ingen migration, schemaändring eller ny generell specialkostmotor behövs.

**Genomförandeordning:** Fortsätt A–Ö-gaten Rapport som planerat. Därefter en smal read-only Copilot-census av befintlig service-addon visning, scope och registrering; därefter en enda liten UI-order för Weekview-text och Produktionslistor-ikonen/listan, följd av iPad/liveacceptans. Ingen ombyggnad av Page3.

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
