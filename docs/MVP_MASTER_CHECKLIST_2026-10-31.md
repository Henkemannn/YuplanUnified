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
| K26 | CLOSED / LOCAL COMMIT | Produktionslistor: separat sida med familjegrupper, numeriska avdelningsantal för vald dag, beskrivning/kommentar, utskrift av alla eller vald familj. 16 fokustester godkända; skärm och utskrift accepterade 2026-10-31. Lokal commit `b09c3d7a719e304666c5900a0c6a0587b7496e83` (6 filer), ännu inte pushad. |
| K27 | CLOSED / LOCAL COMMIT | Page3 Specialkost → Packlista: tydliga avdelningskort med specialkost och serveringstillägg, inklusive addon-only-avdelningar, numeriska antal/kommentarer samt A4-utskrift. 79 tester och verklig skärm/print-preview godkända 2026-10-31. Lokal commit `0d8032620cd5943439d7a9eda29c267a27b3f189` (exakt 5 filer), ännu ej pushad. |
| K28 | LOCKED | Specialkost och Serveringsanpassning är separata domäner |
| K29 | OPEN | Planera 1 vs 2.0 parity och kontrollerad cutover |
| K30 | IN PROGRESS – K30-01 CLOSED / K30-02 NEXT | Full clean-customer Kommun E2E återstår. K30-01 HTTP 500 vid ny avdelning fixad och lokalt committad `14ab0825f56d17500eb516f09a226bfdf5341bc6` (2 tilläggsrader, 1 template); 40 tester passed (13+27). Full K30, 20+ avdelningar/print, kväll/dessert och rapport→completion ej slutbevisade. Ingen push. |
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

## K26 – Utskrift och familjegrupperad vy visuellt accepterade (2026-10-31)

**Visuell och funktionell acceptans:** Produktägaren har granskat `/ui/production-lists/addons` med familjer MOS, PASTA och SALLAD, numeriska antal, kommentarer samt skrivarikoner och bekräftat att funktionerna fungerar. K26 är **CLOSED / LOCAL COMMIT**. Terminalverifierat: `tests/ui/test_production_lists_snapshot.py -q` = **16 passed**, `git diff --check` OK och selektiv commit `b09c3d7a719e304666c5900a0c6a0587b7496e83` med exakt sex K26-filer. Den samlade diffen granskades före checkpoint. Ingen push eller merge utförd.

**Implementerat enligt Copilotrapport:** Page3-lik skrivarikon i sidhuvudet för alla familjer och diskret ikon för varje familj. Familjeprint filtreras endast under print via stabilt `data-family-key`; `afterprint` och Escape återställer skärmstatus. Ljus A4-layout används. Ingen backendändring för utskriftsfunktionen.

**Återstående release-verifiering:** lokal K26-checkpoint är färdig. Fortsatt skyddade dirty-filer: `core/admin_repo.py`, `scripts/seed_ostergarden_from_json.py`, `scripts/seed_product2_e2e.py` samt `artifacts/`. Full iPad-/storskalig 20+-regression och CI kvarstår inför pilot. Nästa avgränsade gate: återanvändbara serveringstillägg i Admin, därefter K27 packlistor. Ingen övergripande pilot-GO utfärdad.

## Admin – Återanvänd serveringsanpassningar, implementation review (2026-10-31)

**Status: CLOSED / LOCAL COMMIT.** Produktägaren har efter manuell kontroll uttryckligen godkänt Add-flödet: "funkar perfekt" (2026-10-31). Lokal commit `ad96abd4f0c5b26640bd0557b745544685d64d6e` innehåller exakt tre Admin-filer, ännu inte pushad. Efter K26-checkpoint `b09c3d7a719e304666c5900a0c6a0587b7496e83` har Copilot enligt rapport ändrat exakt tre filer: `templates/ui/unified_admin_departments_form.html`, `static/js/admin_service_addons.js`, `tests/ui/test_admin_department_service_addons.py`. Admins Lägg till-knapp går nu till befintligt Add-läge, familj väljs före beskrivning, sökning filtrerar återanvändbara addon-ID inom vald familj/site, byte av familj rensar sökning och valt ID utan automatiskt ersättningsval. Skapa ny finns kvar med varning och välj-befintlig för lika namn; mängd/scope/notering, edit/remove avses oförändrade. Inga backend-, repository- eller migrationsändringar.

**Testbevis:** `pytest tests/ui/test_admin_department_service_addons.py tests/ui/test_production_lists_snapshot.py -q` = **24 passed** (8 Admin + 16 K26); `git diff --check` OK. **Manuell browseracceptans och selektiv lokal commit verifierade.** Terminalresultat: `24 passed` (8 Admin, 16 K26), `git diff --check` samt staged diff check OK; exakt tre filer i commit med 115 tillägg och 13 borttagningar. Efter commit återstår endast skyddade dirty `core/admin_repo.py`, båda seed-scripten och `artifacts/`. Nästa gate K27 packlistor; utvecklingsbranchen på GitHub kan fortfarande ligga efter lokal HEAD. Ingen push eller pilot-GO.

## Beslut: Familjegrupperad kökslista och återanvändbara registreringar (2026-10-31; förtydligat)

**Produktbeslut – K26 presentation nu accepterad:** Kökslistan ska **grupperas direkt per kategori/familj som rubrik**, t.ex. `Sallad`, `Mos`, `Pasta`, `Övrigt`. Direkt under rubriken visas **avdelning | numeriskt antal för vald dag/måltid | avdelningsspecifik kommentar**. Exempel under `Sallad`: `Avdelning A | 5 | Utan rå tomat`, `Avdelning B | 8 | —`. Visa inte `Aldrig rå tomat` som egen huvudrubrik eller extra kategorinivå. Gruppstruktur ska fungera för 20+ avdelningar och utskrift.

**Dataintegritet:** Befintlig `service_addons.addon_family` är familjen, `service_addons.name` är registreringens beskrivning/identitet, och `department_service_addons.note` är avdelningens kommentar. Gruppning på familj är **endast en visningsprojektion**; bibehåll registreringens unika addon-ID. Om flera olika tillägg i samma familj finns på samma avdelning måste de hållas särskiljbara (t.ex. liten beskrivningsrad) i stället för att dölja, slå ihop eller summera dem automatiskt. En text som för närvarande är sparad som tilläggsnamn får **inte** automatiskt flyttas till kommentarsfältet. Inga migrationer eller ändringar av pilotdata.

**Separat framtida Admin-UX-gate:** Vid tilldelning av serveringsanpassning bör administratören först välja familj och sedan söka/välja en befintlig återanvändbar beskrivning inom aktiv site eller skapa en ny endast vid behov. Återanvänd befintligt `service_addons`-ID, minska dubbletter utan automatisk sammanslagning, behåll antal/scope/notering per avdelning. Befintlig kod innehåller `addon_family`, `ServiceAddonsRepo.list_active(site_id)`, `create_if_missing` och `department_service_addons`; verifiera lokal kod före separat order.

**Sekvens:** säkra först K26:s selektiva lokala checkpoint. Därefter separat avgränsad Admin-UX-gate för återanvändning av beskrivningar före K27. Ingen parallell implementation. K25 förblir CLOSED.

## K27 – Packlista per avdelning: serving addons (2026-10-31)

**Status: OPEN – nästa implementation, ej accepterad.** Page3 har redan `Specialkost → Packlista` med avdelningskort från `Product2Page3VM.special_destination_groups`. Detta är rätt yta; ingen ny Page3-flik/route, ingen motor och ingen separat PDF-funktion. Under varje relevant avdelning ska en tydligt avskild `Serveringstillägg`-sektion visa familj, registrerad beskrivning, numeriskt antal för valt datum/måltid och avdelningsspecifik notering. Samma innehåll måste ingå vid befintlig Page3-utskrift av Packlistan.

**Kritisk kant:** även avdelningar som bara har serveringstillägg (ingen specialkost) måste komma med på avdelningspacklistan, men helt tomma avdelningar får inte tillkomma. Datumstyrda `whole_department`-antal via befintlig `resolve_service_addon_quantity`; `custom` från rätt måltid; lunch/dinner/all_services filtreras korrekt; dessert ska aldrig få lunchens serveringstillägg; inaktiva poster och andra sites/tenants bort. Bevara unika addon-ID/kommentarer utan sammanslagning eller dubbelräkning. Page3:s completion/ready/blocked, normalkost, specialkost och print-state får inte ändras i övrigt.

**Ordning:** en avgränsad K27-order → Copilotrapport med fokustester → browser+printacceptans → selektiv checkpoint. Admin-gate är CLOSED på `ad96abd4f0c5b26640bd0557b745544685d64d6e`; K26 `b09c3d7a719e304666c5900a0c6a0587b7496e83`; båda endast lokalt, ej pushade.

## K27 – Copilotrapport efter första implementation (2026-10-31)

**IN PROGRESS / EJ ACCEPTED:** Copilot har lokalt implementerat K27 i fem filer (`core/planera_product2_page3_vm.py`, `templates/ui/kitchen_product_planera_page3.html`, `static/css/planera_product2_page3.css`, två tillhörande Page3-testfiler). Rapport: `pytest tests/core/test_planera_product2_page3_vm.py tests/ui/test_kitchen_product_planera_page3.py tests/ui/test_production_lists_snapshot.py tests/ui/test_admin_department_service_addons.py -q` = **79 passed**, `git diff --check` OK; lokal HEAD är fortfarande `ad96abd4f0c5b26640bd0557b745544685d64d6e`, inga commits/pushes, skyddade dirty-filer kvar.

Uppgivet beteende: läser aktiva site-scopade addons, löser `whole_department` och `custom` per datum/måltid, visar familj/antal/beskrivning/notering under respektive avdelnings specialkost i befintlig Packlista, skapar addon-only-grupper men inga helt tomma grupper, bevarar addon-ID och print-CSS. Ingen särskild route eller motor. **Måste fortfarande visuellt testas i riktig Page3 inklusive avdelning med specialkost + tillägg, enbart tillägg samt utskriftsförhandsgranskning, och att andra Page3-lägen är oförändrade.** Före commit: lokal K27-diff/allowlist- och regressionskontroll. Inte hävda full clean-customer/pilot-GO.

## K27 – UI-läsbarhet efter användarfeedback (2026-10-31)

**Visuell acceptans fortsatt OPEN.** Produktägaren visade en faktisk Page3 Packlista där specialkost och serveringstillägg såg ut att flyta ihop utan tydliga avdelningsgränser; önskemålet var att omedelbart se vilken avdelning, vilken kategori och vilket numeriskt antal varje rad hör till. Efter avgränsad UI-order rapporterar Copilot ändringar endast i `templates/ui/kitchen_product_planera_page3.html`, `static/css/planera_product2_page3.css`, `tests/ui/test_kitchen_product_planera_page3.py` (den första implementationens VM/test-diff ligger kvar). Nya avdelningsblock med distinkta rubriker; separat Specialkost endast där sådan finns, tydlig Serveringstillägg-tabell med `Familj | Beskrivning / kommentar | Antal`, kapitaliserade familjer och högerjusterade antal, A4-/responsiva regler. **79 passed** samma fyra Page3/K26/Admin-testfiler; `git diff --check` godkänd. Ingen commit/push.

**Nästa acceptansgate:** skärmbild av uppdaterad faktisk Packlista med både Specialkost+Serveringstillägg samt addon-only-avdelning; därefter faktisk A4-print-preview. Kontrollera övriga Page3-vyer oförändrade. Gör först efter godkännande slutlig samlad diff-/staginggranskning av exakt fem K27-filer och lokal checkpoint; skydda `core/admin_repo.py`, båda seed-filerna och `artifacts/`. Inga ytterligare Copilot-order parallellt.

## K27 – Visuell och printacceptans (2026-10-31)

**CLOSED / LOCAL COMMIT.** Produktägaren granskade riktig Page3 Packlista med Avdelning 2 (specialkost och tillägg) och Avdelning A (endast tillägg) efter UI-förfining. Avdelningsgränser, separata sektioner, familj/beskrivning/antal, läsbara högerställda antal och addon-only-fall visuellt godkända. Verklig ljus A4-print-preview för 12 oktober 2026 granskad och godkänd; på testbladet ryms båda avdelningarna på 1 sida. Fortsatt **79 passed** i Page3 VM/UI, K26 och Admin verifierade i terminalen (3.77 s), `git diff --check` OK; selektiv lokal commit `0d8032620cd5943439d7a9eda29c267a27b3f189` med exakt fem K27-filer (435 additions, 10 deletions). Ingen push/merge. Skyddade ocommittade filer kvar: `core/admin_repo.py`, båda seed-scripten och `artifacts/`.

**Valfri senare UI-förfining, INTE blockerande K27:** möjlig skärmbaserad fäll ihop/expandera för Serveringstillägg per avdelning vid 20+ avdelningar; öppet som standard och alltid fullt synligt på utskrift. Ingen sådan funktion ska läggas till i pågående K27-gate. Storskalig print med 20 avdelningar och full pilot-E2E kvarstår som separat release-verifiering. K27:s lokala checkpoint är klar; nästa gate är Kommun release-/E2E-verifiering, utan att återöppna godkända produktfunktioner. Skydda `core/admin_repo.py`, båda seed-scripten och `artifacts/`. Ingen push förrän uttryckligt beslut.

## K30 – Read-only E2E-census och K30-01 blocker (2026-10-31)

**Ingen kodändring.** Lokal branch `feat/planera-app-shell-2026-03-03`, HEAD `0d8032620cd5943439d7a9eda29c267a27b3f189`, `git diff --check` godkänd; tidigare skyddade dirty `core/admin_repo.py`, båda seed-scripten och `artifacts/` kvar. Pilotdatabasen användes inte som testmål; hash kunde inte tas på låst `instance/yuplan_mvp.db`, vilket inte i sig bevisar databasändring.

**Grönt verifierat i särskilda testskivor:** 67 Admin/menyimport/publicering/portal; 44 completion service/API. **Inte full grön regression:** Planera option-review två fixtur-/invariantfel före avsedda assertions; rapporttest om duplicerat `Glutenfri` samt äldre testsetups med saknade legacytabeller; Weekview äldre shared-DB/`create_all`-problem. Klassificera dessa separat, påstå inte att hela Planera/rapport/Weekview är testgrönt.

**Blocker K30-01:** GET `/ui/admin/departments/new` och redirects dit kan ge HTTP 500 eftersom `templates/ui/unified_admin_departments_form.html` renderar `vm.resident_variation_forever_table | tojson` i ett edit-only variationsmodal medan new-VM i `core/ui_blueprint.py` saknar denna nyckel. Exempeltestfall från `tests/ui/test_admin_departments_residences.py`: `test_new_department_form_shows_residence_controls`, `test_create_residence_from_new_form_redirects_with_selection`, `test_create_department_requires_residence_selection`. Rotorsak måste reproduceras och avgränsas lokalt. Företrädesvis säkra villkorad rendering av edit-only modaler utan att dölja delad `residence-create-modal` eller injicera fejkdata i VM. Korrigera endast nödvändiga template/controller-/testfiler; ingen K25–K27-/Admin-addon-/DB-motorändring, commit/push eller pilotdataåtkomst. Efter fix: separat clean-customer E2E, rapportcompletion-truth, kväll/dessert och 20-avdelnings A4.

## K30-01 – Department form HTTP 500: fix implemented (2026-11-01)

**Status: CLOSED / LOCAL COMMIT `14ab0825f56d17500eb516f09a226bfdf5341bc6`.** Copilot verifierade på befintlig local HEAD `0d8032620cd5943439d7a9eda29c267a27b3f189` att `tests/ui/test_admin_departments_residences.py` före fix gav **7 failed, 6 passed**, med `TypeError: Object of type Undefined is not JSON serializable` när new-mode renderade edit-only `residents-variation-modal` efter den edit-specifika Jinja-grenen. Lösningen villkorar endast den specifika modalen med `vm.mode == 'edit' and vm.department`; gemensamma `residence-create-modal` lämnas för new/edit. Endast `templates/ui/unified_admin_departments_form.html` ändrad, enligt Copilot två template-rader; ingen Python/DB/migration/seed eller K25–K27-kod ändrad.

**Testbevis efter fix:** fokustest **13 passed**; närliggande Admin-svit **27 passed**, `git diff --check` OK. Separat äldre `tests/admin/test_admin_ui_departments_phase5.py` har text-/kapitaliseringsassertion och `tests/ui/test_admin_department_settings_phase1.py` en settings-POST-värdeassertion; ej klassade som orsakade av denna fix, ej påstå full grön regression. Protected dirty kvar: `core/admin_repo.py`, två seed-scripts, `artifacts/`. Selektiv lokal commit genomförd och verifierad: exakt en template, 2 tillagda rader; 40 tester passed i samma terminalkörning; skyddade dirty-filer kvar. Nästa gate K30-02: isolerad clean-customer Kommun E2E, ingen pilot-GO.

## Kommun pilot – språk/skal, rapport och Planera-cutover review (2026-11-01)

**Status: REVIEW / beslut, inga produktändringar.** Produktägaren visade aktuell lokal Admin `Veckorapport` och Kitchen `Menyöversikt` i v42/2026 och lyfte kvarstående fel i ÅÄÖ, äldre utskriftsikoner, statistikens nytta, olika UI-generationer och att sidomenyns Planera fortfarande öppnar v1. Körning av hela `pytest` pågår hos produktägaren; resultat ej inläst, ingen ny implementation ska startas parallellt.

- **Språkdata:** GitHub-koden i `templates/ui/_layout/app_shell_base.html` innehåller faktiskt bokstavligt `Anv?ndare` i adminnavigation; ingen charsetgissning behövs för just den etiketten. `Centralk?ket` kommer däremot via dynamiskt `current_site_name`/site-display och måste diagnostiseras i DB-värde vs response/HTML vs utskrift; `<meta charset="utf-8">` finns redan i shellet. Ingen blind replacement eller massuppdatering av pilotdata.
- **UI-shell:** Både `templates/ui/kitchen_menu_overview.html` och `templates/ui/unified_report_weekly.html` ärver `ui/_layout/app_shell_base.html`. Shell-integration finns, men de gamla sidmallarna använder emoji `🖨️` i stället för Page3:s etablerade SVG-skrivare, samt äldre cards/sidkomposition. Gör en separat liten gemensam UI-gate efter funktionella blockerare, inte total shell-rewrite.
- **Rapportsemantik:** Nuvarande `Veckorapport` kan visa normal/special per avdelning och vecka/dag, men det är inte bevisad, entydigt märkt `registrerat/planned` kontra `producerat/completed`. I `unified_report_weekly.html` finns dessutom en `coverage_data`-gren där `special = 0` och dagrader `Normal 0 · Special 0` är hårdkodade; måste klassificeras och korrigeras innan rapportens värden får säljas som verklig produktionsstatistik. Lägg hellre till semantiskt korrekta KPI för planerat/registrerat, faktiskt färdigmarkerat, återstår och datatäckning än kosmetiska diagram. K21/K22/K23 kvarstår.
- **Planera:** `_layout/app_shell_base.html` pekar i både kitchen-varianter på `url_for('ui.kitchen_planering_v1')`. Den befintliga routen `/ui/kitchen/planering` stödjer redan `ui=product2`, men det är inte en godkänd cutover. K29 är fortsatt OPEN; efter K30 clean-customer E2E, rapportcompletion-truth, meal-/site-/security-verifiering och klassificerad Planera1-vs-2-parity kan kontrollerad site-/testmiljöspecifik navigeringsswitch till v2 med lätt rollback accepteras. Håll v1 tillgänglig som fallback tills v2 godkänd.

**Föreslagen arbetsordning efter fulla pytest-resultatet:** 1) triagera nya failure-/error-typer utan massfix, 2) genomför isolerad K30-02A från ny kund till rapport och identifiera fakta, 3) minimal språk/source-vs-DB-fix; 4) rapportcompletion-truth och cutovergate; 5) små shell/printikon-parityfixar samt 20-avdelnings/iPad/A4; 6) staging/pilotfreeze. Prioritering kan ändras om full pytest visar en omedelbar blocker.

## Full pytest 2026-11-01 – 138 failures triage

**Source:** user-provided complete pytest summary, local `feat/planera-app-shell-2026-03-03` at recent checkpoint `14ab0825f56d17500eb516f09a226bfdf5341bc6` (the pasted log does not itself independently print HEAD). Run total **2426 passed, 138 failed, 16 skipped, 3 warnings**, **667.33 s**. This is not a clean release gate; broad test pass rate 94.6% of executed tests but no basis to call all 138 product defects.

**Distinct recurring patterns, counts from 138 FAILED lines:** 57 include HTTP 401/authentication-required; 17 `tests/core/test_planera_product2_menu_vm.py` failures share `CommunMenuProjectionRow.__init__` required argument mismatch; 8 legacy dietary migration failures `NoSuchTableError: users`; 9 `ValueError: duplicate_name`; 3 `RequirementCountExceededError`; 7 tasks tests have `KeyError: task_id` often downstream of failed auth. UI label/snapshot mismatches include deprecated emojis, renamed buttons and week headings. No causality established beyond output text.

**Must independently triage before v2 cutover or pilot:** 4 tests in `tests/admin/test_admin_ui_departments_delete_canonical_cleanup.py` including orphaned canonical rows, FK-off case and service overrides; 1 Builder publication rollback test where `published` remains instead of `draft`; 3 announcement UI tests and 2 week-grid cohort tests giving HTTP 500; sample authenticated-site/menu-choice API tests giving HTTP 401. These may be fixture/auth/setup mismatches or genuine behavioral bugs; do not silently relabel. Protect locally dirty `core/admin_repo.py` and both seeds. Existing K25-K27/K30-01 focused tests remain accepted, but whole regression NOT GREEN.

**Priority next diagnostic gate:** READ ONLY, one representative isolated testcase per failure family with traceback, captured effective auth claims/tenant/site/DB config and code-path, then classify each as product regression / test fixture drift / deprecated contract / unresolved. No blanket authentication weakening, renaming product UI to satisfy old snapshots, resetting DB, committing or changing production code. Since K30-02A clean-customer E2E is pending, its execution should be sequenced after this priority triage unless diagnostic proof shows the environment safe. Planera v2 default switch K29 remains OPEN.

**Product-owner decision:** No expansion of report/statistics dashboard proposed on 2026-11-01; preserve current report scope and fix only validated data-semantic/reporting defects (K21-K23) before pilot.

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
