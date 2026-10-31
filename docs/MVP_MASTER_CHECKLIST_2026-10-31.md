# Yuplan 1.0 – styrande MVP-masterchecklista

**Granskad:** 2026-10-31  
**Utvecklingsbas:** `feat/planera-app-shell-2026-03-03` @ `6233b11cd4530ed0261992dc6be18af0357955c7`  
**Status:** Programinventering / dokumentationsutkast. Inte full regression och inte pilot-GO.

## Två skilda mållinjer

1. **Kommun 1.1 Ready for Pilot** – första aktuella leveransen.
2. **Yuplan 1.0** – plattforms-MVP med både Kommun 1.1 och Offshore 1.0.

**CLOSED** = tidigare funktionell acceptans (inte en full ny-kund-releasesmoke).  
**FOUNDATION** = grund finns men slutlig operational acceptance saknas.  
**OPEN** = saknad implementation eller nödvändigt beslut.  
**VERIFY** = slutbevis/test återstår.  
**DEFERRED** = ingår inte som blockerare före första pilot.

**Senaste A–Ö:** Rapport. Återöppna inte avdelningar, Builder, portal, Page3 eller Produktionslistor utan reproducerad regression. Den äldre `KOMMUN_1_1_LIVE_ACCEPTANCE.md` har en föråldrad Gate 02-status jämfört med den senare A–Ö-överlämningen 2026-10-11.

## Gemensam plattform och Builder

| ID | Status | Avtalad funktion / slutgate |
| --- | --- | --- |
| P01 | VERIFY | Tenant/site/RBAC- och datascoping, negativ slutverifiering |
| P02 | CLOSED | Skapa kund/site och separat kundadmin |
| P03 | CLOSED | Användare och roller Admin/Kök/Avdelning |
| P04 | CLOSED | Canonical Components -> Dishes -> Menus |
| P05 | CLOSED foundation | Komponentrecept/metod/kalkyl/allergener; Dish aggregerar |
| P06 | CLOSED | Delade Dish-/Component-editorer, ingen kopia per modul |
| P07 | CLOSED | Menyimport DOCX/CSV, unresolved/matchning/alias |
| P08 | CLOSED | Kanonisk menypublikation och edit, immutable baseline |
| P09 | CLOSED | Dynamiska slots, W42-söndag utan påhittad Alt2 |
| P10 | CLOSED seam | Privat Offshore Work Menu/COW skilt från publicerad meny |
| P11 | VERIFY | CSP, migration, tenant-scope och full regressionssäkerhet |
| P12 | CLOSED partial | App Shell dark/light-fix klar; full iPad-smoke återstår |

## Kommun 1.1 – A–Ö och produktion

| ID | Status | Avtalad funktion / slutgate |
| --- | --- | --- |
| K01 | CLOSED | Avdelningar, Boende/enhet, ändra/sortera/radera |
| K02 | CLOSED | Fast antal och Varierar per dag/måltid |
| K03 | CLOSED | Registrerade Kostbehov, primär/modifier, undvik dubbelräkning |
| K04 | CLOSED | Behovsantal och aktuella overrides |
| K05 | CLOSED admin | Registrera Serveringstillägg, antal och anteckning |
| K06 | CLOSED | Avdelningsportal ser kanoniskt publicerad meny |
| K07 | CLOSED | Avdelningsportal väljer och skickar menyval |
| K08 | CLOSED | Kökets Veckovy/Menyöversikt ser samma meny och val |
| K09 | CLOSED seam | Admin Weekview read-only completion-projektion |
| K10 | CLOSED | Alt2 gul menyvalstatus separat från grön färdigmarkering |
| K11 | CLOSED partial | Kök dashboard, menyöversikt och beställningspåminnelse |
| K12 | CLOSED foundation | Planera Page1 vecka/dag/måltid |
| K13 | CLOSED foundation | Page2 mänsklig review med staleness |
| K14 | CLOSED foundation | Planera 2.0 generisk motor + Kommun-adapter |
| K15 | CLOSED partial | Page3 Översikt/Normalkost/Specialkost |
| K16 | CLOSED partial | Page3 specialkost produktions-/packlista och print |
| K17 | CLOSED seam | Page3 marking -> cohort completion -> Weekview persistence |
| K18 | CLOSED partial | Produktionslistor ISO vecka/år och lunchlänk till Page3 |
| K19 | VERIFY | Kvällsmat/dessert fulla måltidsvägar |
| K20 | CLOSED partial | Rapport: normal + producerad/markerad specialkost per avdelning |
| K21 | OPEN | Skilj gammal registreringstäckning från produktionsrapport |
| K22 | OPEN | Rapportexport: HTML/CSV/XLSX/PDF-konsistens; PDF placeholder |
| K23 | VERIFY security | Rapportens tenant/site/department-behörighet |
| K24 | VERIFY/OPEN | Admin Menyval-översikt och admin-overrideregel enligt realt behov |
| K25 | CLOSED / LOCAL COMMIT | Under avdelningsnamn: sparad serveringspreferens, kompakt horisontellt informationsfält med befintlig allmän information; 7 fokustester godkända och visuell acceptans på verklig Kitchen Weekview 2026-10-31. Lokal commit `bbea233b0ac8268d3b58a055a5318652612be688` bekräftad, ännu inte pushad. |
| K26 | OPEN | Produktionslistor: Tillägg-ikon vid Lunch, sparade poster per tillägg |
| K27 | OPEN | Packlistor: sparat tillägg/antal/kommentar per avdelning |
| K28 | LOCKED | Specialkost och Serveringsanpassning är separata domäner |
| K29 | OPEN | Planera 1 vs 2.0 parity och kontrollerad cutover |
| K30 | OPEN | Färsk full clean-customer E2E till rapport/packning |
| K31 | VERIFY | iPad full acceptans samt empty/error-states |
| K32 | DEFERRED | Extern debitering och Mathilda-/ekonomiintegrationer |

## Offshore 1.0 – separat låst mål efter Kommun

| ID | Status | Avtalad funktion / slutgate |
| --- | --- | --- |
| O01 | FOUNDATION | Installation/site och onboarding från central admin |
| O02 | OPEN | Provisioning: installation -> cykel -> rotation -> virtuella platser -> bemanning -> aktivera |
| O03 | FOUNDATION | Fyra veckors menycykel och rätt period/2-4 rotation |
| O04 | CLOSED seam | Privat Work Menu, Dish Picker, kanonisk Builder och reload/reset |
| O05 | FOUNDATION | Kocken ser rätt arbetsperiod och meny |
| O06 | FOUNDATION/VERIFY | Prep-uppgifter/listor |
| O07 | OPEN/VERIFY | Frysplock |
| O08 | OPEN/VERIFY | Husk att bestill |
| O09 | VERIFY | Rollisolering och ersättarkock |
| O10 | OPEN | Minimal Mässportal: meny, allergener, tider, praktisk info, iPad |
| O11 | OPEN | Riggpilot: RBAC, migration, iPad och ny installation |
| O12 | VERIFY scope | Handover/anteckningar, print och historik från äldre blueprint |

## Release och CI – gemensamma gates

| ID | Status | Avtalad funktion / slutgate |
| --- | --- | --- |
| R01 | CLOSED ongoing | Utvecklingsbranch/checkpoints och skyddad lokal arbetsyta |
| R02 | OPEN | Full pytest och frontend-CI-grön |
| R03 | OPEN | Ruff: 7 fel på utvecklings-HEAD |
| R04 | OPEN | Vitest: 15 fel på utvecklings-HEAD |
| R05 | CLOSED docs only | Markdownlint MD028 åtgärdad på dokumentationsbranch |
| R06 | OPEN | pip-audit 6 sårbarhetsposter på gammal master; CodeQL grön |
| R07 | OPEN | Negativa 2-tenant/site tester och rollgränser |
| R08 | OPEN/VERIFY | Alembic, isolerad testdata, staging och smoke |
| R09 | OPEN | Hela Kommun E2E med login/reload/lunch/kväll/dessert/pack/rapport |
| R10 | OPEN | Kommun pilotacceptans och taggad releasekandidat |
| R11 | OPEN | Offshore frisk census och full pilotacceptans |
| R12 | OPEN | Samlad Yuplan 1.0 release (Kommun + Offshore) |

## Serveringstillägg – explicit beslut 2026-10-31

MVP:n visar **endast registrerad information**. Veckovy visar sparad preferenstext under avdelningen. Produktionslistor har en Tillägg-ikon bredvid Lunch och en lista per tillägg med avdelning, antal och anteckning. Packlistorna visar samma information direkt under respektive avdelning. Kökspersonalen avgör vad som ska lagas. **Ingen menyaware mos-/salladsautomatik, ingen extra beräkning och ingen ny Page3-flik.** Långsiktig regelmotor i Ground Truth är en framtida möjlighet, inte aktuell MVP-order.

## K25 – acceptansnotering 2026-10-31

**Beslut:** K25 funktion/UI är CLOSED efter Copilotrapport och manuell screenshot av Kökets Veckovy vecka 44, 2026. Registrerade serveringstillägg ligger horisontellt med diskreta avgränsare och naturlig radbrytning i samma kompakta informationsfält som befintlig allmän avdelningsinformation. Tidigare dubblerat avdelningsprefix har rättats. Ingen ny beräknings- eller skrivlogik, ingen K26/K27-implementation.

**Evidens:** Copilot rapporterade `tests/ui/test_kitchen_week_v3.py -q` = **7 passed**, `git diff --check` godkänd och bevarade dirty-filer. Manuell screenshot accepterades av produktägaren 2026-10-31. Relaterad äldre Weekview-slice rapporterades som **28 passed, 2 failed** (veckoetikett-förväntningar); detta är fortsatt regressionsskuld och inte bevis för full suite.

**Checkpoint-gate:** K25-filerna `core/ui_blueprint.py`, `templates/ui/kitchen_week_v3.html`, `static/css/kitchen_week_v3.css`, `tests/ui/test_kitchen_week_v3.py` är lokalt committade som `bbea233b0ac8268d3b58a055a5318652612be688` (`feat(kommun): show serving addons in kitchen weekview`), bekräftat med användarens terminalrapport. **Ingen push**; GitHub remote development-branch har därför inte bekräftats innehålla committen. Kvarvarande dirty-filer: `core/admin_repo.py`, `scripts/seed_ostergarden_from_json.py`, `scripts/seed_product2_e2e.py`, `artifacts/`. Dokumentationsbranch/PR #130 är separat från utvecklingsbranchen. Full tenant-/site-regression, iPad, CI och staging tillhör kvarvarande release-gates; inget övergripande pilot-GO utfärdat.

## Beslut: Familj och återanvändbara serveringsbeskrivningar (2026-10-31)

**Produktbeslut – ännu inte implementerat eller accepterat:** Presentation av Serveringstillägg ska följa hierarkin **kategori/familj → återanvändbar beskrivning/tillägg → avdelning med serveringsscope, antal och eventuell avdelningsspecifik notering**. Exempel: familjen `Sallad` med en återanvändbar beskrivning `Aldrig rå tomat i sallad`; beskrivningen är inte en ny toppnivåkategori. Om flera avdelningar behöver `Mos istället för kokt potatis` ska de välja samma befintliga beskrivning, inte skapa stavningsvarianter.

I Admins skapa-/lägg-till-flöde bör vald familj styra en sökbar lista med befintliga beskrivningar inom aktiv site; återanvänd befintligt `service_addons`-ID när en beskrivning väljs. Skapa ny beskrivning endast när den verkligen saknas, med kontroll av dubbletter. Individuella antal, serveringsscope och noteringar ligger fortsatt i avdelningens tilldelning. Befintlig kod har redan `addon_family`, `ServiceAddonsRepo.list_active(site_id)`, `create_if_missing` och `department_service_addons`; verifiera aktuell lokal kod före UI-order, ingen ny datamodell som standard.

Viktigt: vissa nuvarande registreringar kan ha `Sallad` som tillägg och `Aldrig rå tomat` som avdelningsnotering; andra kan ha längre beskrivning som själva tillägget. Tolka inte eller migrera dessa automatiskt och skriv inte om pilotdata. Visning ska skilja familj, beskrivning och notering utifrån faktiskt lagrade fält.

**Sekvens:** först slutför och granska pågående K26 antal/print-gate; därefter en separat avgränsad Admin/återanvändningsgate före K27/vid relevant pilottestbeslut. Ingen parallell implementation och ingen omöppning av K25.

## Rekommenderad återstående ordning

1. Avsluta den nuvarande CI-censusen: välj små, testade Ruff- och därefter Vitest-fixar, utan att skriva om fungerande produktbeteende.
2. Verifiera rapportens tenant/site/department-behörighet med negativa två-tenant-tester; rätta enbart bevisad svaghet. Bevara korrekt rapport över producerad/markerad specialkost.
3. Genomför liten Serveringstillägg-UI-gate enligt låsta beslut ovan.
4. Verifiera kvällsmat/dessert; Admin Menyval endast vid påvisat gap; jämför Planera 1/2 med verklig vecka.
5. Komplett clean-customer Kommun-kedja, iPad, full regression, staging, pilotfrysning/tagg.
6. Färsk read-only Offshore-census mot låst MVP; stäng dess provisioning/kock/prep/frys/beställ/Mässportal innan samlad Yuplan 1.0-release.

## Utanför denna MVP

Yuplan Home; Hotel/Bankett/Event; full inköps- och lagerplattform; grossistkoppling; AI/prognoser/avancerat matsvinn; avancerade ingredienskonverteringar och stor receptimport; villkorad menyaware substitutionsmotor; stor chefs-/beställningskalender och mobil managerapp; Offshore asset-ID-felanmälan och resursbokning; full offline; externa debiteringssystem.

## Källprioritet och reservationer

1. `docs/ground_truth/README.md`, `YUPLAN_1_0_FINISHLINE.md`, `KOMMUN_1_0_MVP_LOCK.md`, `OFFSHORE_1_0_MVP_LOCK.md`, `BUILDER_MENU_LOCK.md`, `PLANERA_2_0_ARCHITECTURE_LOCK.md`, `PORTALS_ARCHITECTURE_LOCK.md`, `DECISION_LOG.md`.
2. Oktober-handoffs på separata dokumentationsbrancher – främst `KOMMUN_1_1_HANDOFF_2026-10-11.md` på `handoff/kommun-1-1-2026-10-07`.
3. Senare accepterade checkpoint- och browserresultat samt användarens uttryckliga beslut 2026-10-31.
4. GitHub CI-loggar på development-HEAD och `master`; jämställ inte gröna fokustester med full grön release.
5. `docs/offshore2/product_blueprint.md` är äldre vision/underlag; senare `OFFSHORE_1_0_MVP_LOCK.md` har företräde vid konflikt.

En full manuell rekonstruktion av varje tidigare chatt eller varje kodrad är inte möjlig i denna inventering. Klassificeringar som VERIFY/FOUNDATION är medvetet försiktiga. Inga produktfunktioner har implementerats genom detta dokument.

**Arbetsdisciplin:** en Copilot-order -> en rapport -> granskning -> nästa. Skydda lokala dirty-filer och pilotdata; inga ospecificerade sidorefaktorer, inga migrations- eller arkitekturändringar utan godkännande.
