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
| K30 | IN PROGRESS – K30-02B SERVICE/API E2E PASSED | K30-01, K30-P0 and K30-DELETE-VERIFY local checkpoints closed (`14ab0825`, `205f294a`, `1995b09e`). K30-02B new temp-isolated same-customer integration test: **1 passed, exit 0**, A→E creation/menu/review/completion and report API site response; **committed locally** `tests/integration/test_k30_kommun_new_customer_e2e.py` at `249a904f`, 1 test passed again in 1.69s; no push. Not browser UX or full report-number parity; pilot GO remains OPEN. Protected dirty repo/seeds retained. Primary immediate goal: reduce 138 full-suite pytest failures systematically. |
| K31 | VERIFY | iPad full acceptans samt empty/error-states |
| K32 | DEFERRED | Extern debitering och Mathilda-/ekonomiintegrationer |
| K33 | OPEN – PILOT SECURITY | Inloggning och lösenordsåterställning: riktiga felmeddelanden i HTML, uthålligt throttling/lockout över flera workers, fungerande email-tokenreset med single-use/expiry, konto-/tenantisolering, revokering av sessions/tokens, auditering; säker full regression. Nuvarande `/auth/forgot` är placeholder. |
| K34 | OPEN – LOGIN UX | Bevara uttryckligen den befintliga snurrande Yuplan-globen, som produktägaren vill behålla. Ta fram separata diskreta form-/bakgrundsförslag runt samma animation; rätt logga/brandfärger, dark/light, iPad, visa/dölj lösenord, tangentbord/tillgänglighet, reduced-motion; ändra inte authlogik under UI-passet. |

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

## Login / återställning – kodinventering och prioritering (2026-11-01)

**Produktbeslut:** prioritera fungerande självbetjäning för glömt lösenord och säker felhantering före bred login-designpolish; designen ska vara Yuplan-clean med officiell logga, inte ny loginmotor eller publikt användarregistreringsflöde. För närvarande pågår Copilot K30-testtriage och ingen parallell order ska ges.

**Kodinventering (GitHub remote `feat/planera-app-shell-2026-03-03`, som kan ligga efter lokal kod):** `templates/login.html` ärver `ui/_layout/auth_base.html`, har e-post, password, csrf, felruta, glömt-länk och roterande `logo-proposal-globe-exp-v3.svg`. `templates/auth_forgot.html` är bara texten `Återställ lösenord kommer snart`. `core/auth.py`: POST `/auth/login` använder check_password_hash och in-memory `_RATE_LIMIT_STORE` per epost:IP med default 5 fel/300 s och lock 600 s (401/429 JSON även för webform); GET `/auth/forgot` renderar bara placeholder. `tests/test_auth_rate_limit.py` testar enkel spärr. Admin kan skapa tillfälligt lösenord och tvinga lösenordsbyte; `tests/ui/test_auth_version_revocation.py` visar befintlig `auth_version` / refresh revocation vid admin-reset och eget password change. Serverregeln i `core/ui_blueprint.py::account_change_password` accepterar min 6 tecken; behöver policyreview (NIST SP 800-63B-4 rekommenderar/kräver min 15 vid single factor, minst 8 vid MFA) och avgränsad migration för nya/bytta lösenord, utan att omedelbart låsa ute existerande användare.

**Acceptanskriterier auth:** HTML-fel för fel uppgifter utan account enumeration; 429 vänlig retry; beständiga/spårbara och rimliga rate limits (separat epost, IP, ändamål), ingen permanent lockout som möjliggör DoS. Forgot POST alltid neutralt svar; på riktig adress levereras resetmail med slumpmässig kryptostark engångstoken, kort expiry, hashad token i storage, single-use/atomic compare-and-consume, rate-limit och ingen token i URL-loggar/analytics; verifierad password policy, sessions/JWT- och refresh-invalidering via befintlig auth_version mekanism, mailnotis efter lyckad reset, CSRF, tenant/site guards, funktionella isolerade tester inkl. token reuse/expiry/concurrency. Verifiera mailleverans/infrastruktur före implementation; inget gissande om redan befintlig mailprovider. Admins befintliga säkra resetflöde ska behållas som fallback.

**Login-design:** använd officiell Yuplan SVG/brandfärger, lugn ljus/mörk inloggning med diskret optional rörelse (reduced-motion), bra kontrast, visa/dölj lösenord, tydliga felfält, mobil/iPad-touch, autofill/password manager och korrekt ÅÄÖ; ingen ny registrera-dig-knapp eller rollväljare. Begränsa till login/auth CSS/templates som en separat UI-gate efter authkontraktet. **Inga kodändringar beställda i detta beslut.**

## K30-TEST-TRIAGE – verifierade P0-resultat (2026-11-01)

**READ ONLY, ingen commit/produktändring.** Branch `feat/planera-app-shell-2026-03-03`, lokal HEAD `14ab0825f56d17500eb516f09a226bfdf5341bc6`. Isolerade pytest-fixtures under systemets tempkatalog; rapporterade skyddade dirty-filer oförändrade; `git diff --check` grönt.

- **P0 verklig regression: Meddelanden/Påminnelser** `tests/ui/test_announcements_mvp.py` → **3 failed, 1 passed**; återkommande `NameError: _format_announcement_display is not defined` i `core/ui_blueprint.py::_build_dashboard_announcements` (~rad 340), anropas för Admin announcements/dashboard och Kitchen dashboard efter att relevant meddelande lagts till. Saknad definition/import verifierad vid separat GitHub-kodläsning; nästa ENDA Copilot-order bör kirurgiskt återställa formatteringen med test av datum/tid och site-/kitchen-only-filtrering. Före fix är detta pilotblockerare när meddelanden används.
- **Avdelningsradering – ännu ej fullständigt cleanup-verifierad:** `tests/admin/test_admin_ui_departments_delete_canonical_cleanup.py` → **3 failed, 1 passed**. Test-POST saknar ny obligatorisk `confirmation`, varvid route stoppar före repo. Ett separat happy-path `tests/ui/test_unified_admin_departments_phase2.py::test_departments_delete_happy_path` → **1 passed** med korrekt bekräftelse, men detta bevisar inte alla kanoniska/override-cleanup fall. Anpassa senare testfixtures och verifiera FK-on/off, scope och relaterade rader i isolerad DB, utan att skriva över dirty `core/admin_repo.py`.
- **Publikationsrollback:** tidigare full-suite-fail kan inte isolerat reproduceras, `test_publish_projection_failure_keeps_legacy_draft_and_no_pin` → **1 passed**; observera suite-interaktion som möjlig förklaring, ännu inte generell full-suite-friskförklaring.
- **Cohort/Weekgrid:** `tests/ui/test_week_grid_cohort_shared_render.py` → **3 passed** isolerat; tidigare 500 ej reproducerad.
- **Menu-choice API 401:** ett isolerat test **1 failed** p.g.a. testets manipulerade session/otillräcklig autentisering gentemot nuvarande fail-closed-kontroll. Misstänkt inaktuellt testkontrakt; säkerheten får inte släppas. Detta ensamma test bevisar inte att samtliga 57 401-fel har samma orsak.
- **Planera2 menu VM:** ett isolerat test **1 failed** p.g.a. att testfixture inte anger nya obligatoriska `CommunMenuProjectionRow.selection_group_id`. Produktionsanrop har fältet. Endast fixture ska uppdateras efter avgränsad review, inte dataklassens kontrakt; full testfil fortfarande 17 reds.

**Nästa ordning:** P0 saknad announcement formatter → fokustest + närliggande regressionsgranskning → selektiv lokal checkpoint → tester som verifierar verklig canonical cleanup → K30-02A clean-customer E2E → återstående testdrift och release-frysning. K33/K34 login backlog, ingen parallell order. Full pytest fortfarande **2426 passed, 138 failed, 16 skipped**, ej pilotklart.

## K30-P0 – Announcements formatter restored locally (2026-11-01)

**Status: CLOSED / LOCAL COMMIT `205f294aad596cf5036bbc0a7db62ac8a752d4ec`.** Copilot på lokal `feat/planera-app-shell-2026-03-03`, HEAD `14ab0825f56d17500eb516f09a226bfdf5341bc6`, reproducerade `tests/ui/test_announcements_mvp.py` **3 failed, 1 passed** p.g.a. saknad `_format_announcement_display` vid Admin-/Kitchen-dashboardrendering. Återställde befintligt historiskt formatteringskontrakt i `core/ui_blueprint.py` med svenska veckodagsförkortningar, dag/månad och valfri `kl HH:MM`; lade till fokuserade tester i `tests/ui/test_announcements_mvp.py` för ÅÄÖ, datum/tid, site-isolering och HTML-escaping. Inga schema-, repo- eller behörighetsändringar.

**Rapporterat testbevis:** announcements **6 passed**; Admin/Kitchen dashboards (`tests/ui/test_admin_dashboard_today_menu.py`, `tests/ui/test_unified_cook_dashboard_phase4.py`) **31 passed**; `git diff --check` OK. Endast två produkt-/testfiler ändrade; skyddade dirty `core/admin_repo.py`, `scripts/seed_ostergarden_from_json.py`, `scripts/seed_product2_e2e.py`, `artifacts/` kvar. Lokal selektiv commit verifierad i användarens terminal: `205f294aad596cf5036bbc0a7db62ac8a752d4ec`, två filer, 56 tillagda och 1 borttagen rad; samma 37 tester passerade i ny körning (1,97 s). Ingen push. Nästa gate: bevisa canonical department-delete cleanup med korrekt bekräftelse och isolerad DB; därefter K30-02A. Full regressionssvit alltjämt ej grön och ingen pilot-GO.

## K30-DELETE-VERIFY – canonical department delete cleanup (2026-11-01)

**Status: CLOSED / LOCAL TEST COMMIT `1995b09e18fc70aefa8f02d5663d01ee0e66c08b`.** På `feat/planera-app-shell-2026-03-03`, HEAD `205f294aad596cf5036bbc0a7db62ac8a752d4ec`, har Copilot enbart ändrat `tests/admin/test_admin_ui_departments_delete_canonical_cleanup.py`. Före ändring: **4 failed** (alla delete POST saknade `confirmation` eller förväntade äldre flashtext). Test-helper returnerar nu riktigt avdelningsnamn, POST använder `confirmation`, wrong-site gör detsamma men förhindras, och extra test för fel namn har tillkommit. **Kombinerad svit:** `tests/admin/test_admin_ui_departments_delete_canonical_cleanup.py` + `tests/ui/test_unified_admin_departments_phase2.py` → **33 passed in 11.38 s**; `git diff --check` OK; isolerad pytest-temp-SQLite. Bekräftad cleanup av department, group, joins och service overrides, delad dietary type bevaras, FK OFF fungerar, fel site och fel bekräftelse tar inte bort data. **Viktigt:** verifierat mot lokalt modifierad, fortfarande ocommittad `core/admin_repo.py`; release-reproducerbarhet i ren checkout är ännu inte godkänd. Skydda denna fil och båda seed-script samt `artifacts/`; selektiv lokal commit verifierad av användaren: 33 passed in 13.62 s, 1 testfil med 52 tillägg och 8 borttagna rader. Ingen push. K30-02A isolerad clean-customer E2E återstår. För pilotfrysning krävs separat inspektion av ocommittad skyddad `core/admin_repo.py` så att lokalt godkänd datastädning är reproducerbar från Git-checkpoint.

## K30-02A – E2E census execution and unresolved smoke exit (2026-11-01)

**Status: PARTIAL ACCEPTANCE / COMPLETE LINKED E2E NOT PROVEN.** Copilot på lokal `feat/planera-app-shell-2026-03-03`, HEAD `1995b09e18fc70aefa8f02d5663d01ee0e66c08b`, körde isolerade kontraktstester i temp-SQLite: canonical preparation **1 passed**; portal **9 passed**; Page2/Page3 **51 passed**; completion API **21 passed**; kommun/Weekview/cohort-report **2 passed**. Dessa är separata data- och fixturescenarier och **bevisar inte** att ny kund→publicerad meny→menyval→review→packlista→completion→rapport fungerar på **samma tenant/site/vecka/dataset**. Full report UI-svit `test_unified_report_weekly_phase1.py` + `test_weekview_report_ui_phase1.py` → **14 passed, 1 failed, 3 errors** (legacy `weekview_items` table absent, textförväntan på `Normal`). Klassificering är ännu inte fullständigt verifierad.

**Viktig inkonsekvens:** Tre skriptbaserade, avsiktligt temp-isolerade smoke-försök att skapa ny tenant/site/tre avdelningar/grupper/addon visar alla `Tool execution failed with exit code 1` i rå rapport; Copilot sammanfattar trots detta en `COUNTS={tenant:1,site:1,departments:3,variable_departments:1,groups:2,group_memberships:3,addons:1}` och markerar A/B som PASS. Den bifogade loggen innehåller inte skriptens slutliga traceback/framgångsstatus; siffrorna ensamma uppfyller inte PASS. Skapande av boende-/residentpersoner, varierande dag-/måltidsantal och personbaserad deduplicering inte verifierat. Måste diagnostisera det faktiska exit 1 och därefter köra ett sparat, reproducerbart isolerat integrationstest med exit 0; rapportera A/B som VERIFY tills dess. Ingen användardata berörd enligt Copilot; staging/pilot/instance-DB ej nyttjade, manuella temporära kataloger rensade. Skyddad dirty `core/admin_repo.py` inspekterad; Copilot rapporterar endast tolerans för `site_id=None` i `DietTypesRepo.create()`, men release-säkring kräver separat kodreview innan pilot.

**Nästa gate K30-02B:** riktad sanningsenlig körning med en **enda** tenant/site/vecka/datum som flyttas fram sekventiellt; fånga fullständigt fel från smoke exit 1, verifiera faktisk temporär huvud-/Builder-databas, skapa persistent testfil bara under `tests/`, inga produktändringar, start med A/B och fortsätt till C/D/E enbart när samma dataset stödjer det. Gränsen för full K30 förblir OPEN. K29 Planera2 global cutover fortsatt OPEN; inga nya statistikfunktioner beställda.

## K30-02B – reproducible customer E2E (2026-11-01)

**Service/API integration CLOSED / LOCAL COMMIT `249a904f6b8b10a7c076676d671c796effcd4313`.** On `feat/planera-app-shell-2026-03-03`, HEAD `1995b09e18fc70aefa8f02d5663d01ee0e66c08b`, Copilot created only `tests/integration/test_k30_kommun_new_customer_e2e.py`. Reported verified temp main + Builder SQLite, same tenant/site/date/meal across: new customer and three departments (fixed and variable counts); atomic Timbal/Glutenfri with combination and explicit correct total; serveringstillägg quantity 3 and note; canonical Builder menu linking/publication; alt1 department choices; Page2 review; Page3 special and packlist; completion targets marked and persisted; weekly report API HTTP 200 correct site. `pytest tests/integration/test_k30_kommun_new_customer_e2e.py -vv --tb=short` **1 passed in 1.75 s, process exit 0**; user reran the test and confirmed **1 passed in 1.69 s**, then selectively committed only the 346-line new integration test file as `249a904f6b8b10a7c076676d671c796effcd4313`. No push. This is **not** Playwright browser acceptance or exhaustive review of weekreport quantitative data; entire K30 release gate stays OPEN. User's stated immediate priority: return to baseline **138 failed, 2426 passed, 16 skipped** full pytest; no further E2E development until fixing regression clusters. Scope-lock/protected dirty `core/admin_repo.py`, both seed files, `artifacts/` untouched; no push. Previous K30-02A exit-1 causes categorized: invalid requirement semantics `composite`, variable department effective resident count missing (invariant), and Windows SQLite file lock during TemporaryDirectory cleanup. Next: target 17 stale Planera menu VM fixture tests with `selection_group_id`; do not weaken auth to satisfy other 401 tests.

## PYTEST RECOVERY 01 – Planera menu VM fixture (2026-11-01)

**CLOSED / LOCAL COMMIT `0505fcf40cf6e89e942939a500ffd6438706bec2`.** At local development HEAD `249a904f6b8b10a7c076676d671c796effcd4313`, `tests/core/test_planera_product2_menu_vm.py` reproduced **17 failed, 1 passed**; all 17 shared obsolete test-helper construction lacking mandatory nullable `CommunMenuProjectionRow.selection_group_id`. Copilot modified only this test fixture, adding optional `selection_group_id: str | None = None` and forwarding it to constructor. After change **18 passed in 0.81 s**; neighboring `test_commun_builder_projection.py`, `test_planera_v2_kommun_projection_contract.py`, `test_planera_v2_kommun_day_projection.py`: **79 passed in 1.98 s**; `git diff --check` green. No product-code changes, no commit/push yet. Tool report's git status is internally inconsistent (lists `scripts/seed_product2_menu_vm.py` rather than protected `scripts/seed_product2_e2e.py` and only later cites changed test file). Require direct `git status --short` and verify staged path exactly before selective commit. Protect dirty `core/admin_repo.py`, the two established seed scripts, and `artifacts/`; do not alter unknown files. On original full-suite baseline 138 failures, **24 individual failures were corrected in focused runs**: 3 announcements, 4 canonical delete tests and 17 Planera; remaining **114 provisional**, not a new full-suite result. 3 older failures passed in isolation without code fixes, not proved resolved under full suite. User's terminal verified **97 passed in 1.95s** across this and neighboring projection tests, staged only `tests/core/test_planera_product2_menu_vm.py`, exactly 2 lines added, and committed locally as `0505fcf40cf6e89e942939a500ffd6438706bec2`; final dirty worktree includes only protected `core/admin_repo.py`, two seed scripts and `artifacts/`, with no push. Next workflow: **PYTEST RECOVERY 02 READ ONLY**—inventory and cluster the up-to-57 original 401 failures using source suite evidence and a handful of isolated representative tests; distinguish stale fixture from actual auth regression; do not change production authorization, weaken fail-closed paths or use any permanent database. Fix cohorts in subsequent separate orders after review. Retest entire suite when cluster reduction is established. K30 E2E and K33/K34 login polish deferred while pytest recovery is the user-directed priority.

## PYTEST RECOVERY 02 – auth cohort verified against original summary (2026-11-01)

**READ-ONLY Copilot diagnosis, no local code changes.** Preflight local `feat/planera-app-shell-2026-03-03`, HEAD `0505fcf40cf6e89e942939a500ffd6438706bec2`, protected dirty unchanged, `git diff --check` passed. Reproduced `tests/api/test_menu_choice.py::TestMenuChoiceAPI::test_get_without_tenant_header_uses_authenticated_session` **expected 200, actual 401**, because manually inserted Flask session lacks validated user/auth_version under current fail-closed `core/app_authz.py`. **Preserve this test's no-tenant-header intent**; adding header `X-Tenant-Id` would defeat its purpose. Correct with genuine seeded active user + valid `auth_version` or a real login fixture, not product auth relaxation. 6 representative portal/kitchen/admin/login/RFC7807 tests passed. `tests/test_admin_limits_api.py::test_admin_limits_unauthorized` instead fails **before request**: its direct `create_app(TESTING=True)` inherited a protected pilot DATABASE_URL, and correctly tripped guard; fix test DB isolation separately. Never run these standalone app tests against inherited pilot URLs.

**Original full pytest short summary recovered from user-supplied file** `Inklistrad text(20261101-074116).txt`: **138 individual FAILED lines**, of which **55 actual HTTP 401** (explicit actual status), not 57 as previously approximate; **17** Planera selection-group fixture; **9** duplicate_name; **8** NoSuchTableError users; **7** KeyError task_id; **5** actual HTTP 500 (3 announcements resolved, 2 cohort green isolated); **3** RequirementCountExceeded; **34** other. Original 401 cluster by code areas: `tests/test_import_api.py` 7, `tests/test_import_api_strict.py` 5, `tests/test_import_menu_api.py` 4, `tests/test_tasks_api.py` 6, menu_choice 3, pagination 3, rate-limit registry 3, plus smaller groups. Counts are original-run facts, **not current failures**. 24 previous original failures locally patched & focused-verified (3 announcements + 4 delete + 17 Planera), so 114 provisionally open pending full-suite rerun. One standalone successful security test doesn't establish broad 401 health.

**Next user-prioritized gate:** PYTEST RECOVERY 03 – target **16 original import API HTTP 401 failures** across three files; first verify safe temporary database before any test command (these files include standalone `create_app(TESTING=True)` which may inherit env DATABASE_URL), then reproduce, minimally update only test-owned login/setup to a real current auth fixture or safe TESTING headers without defeating intentionally negative auth cases. No production auth changes, no blanket weakening, preserve import validation assertions and menu rollback/500 test intent, STOP on genuine product failure. One order → report → review. Full suite rerun after several large clusters.

## PYTEST RECOVERY 03 – Import API test-auth and temporary DB isolation (2026-11-01)

**CLOSED / LOCAL COMMIT `cee1c3856bfebbd1370738d39f046bb3ffb51412`.** Branch `feat/planera-app-shell-2026-03-03`, local HEAD `0505fcf40cf6e89e942939a500ffd6438706bec2`. Copilot reported original 16 HTTP 401 failures across `tests/test_import_api.py` (7), `tests/test_import_api_strict.py` (5), `tests/test_import_menu_api.py` (4). On a safely process-overridden temp DB before modifying tests, these 3 files produced **17 failed, 3 passed**, with mixed 401 and schema/500 issues (therefore not exactly the original 16 failures). Actual .env DATABASE_URL points to protected `sqlite:///instance/yuplan_mvp.db`, which was not used. Copilot changed **only three test files**, making direct app helpers take pytest `tmp_path`, explicit temp main and Builder DB, `FORCE_DB_REINIT=True`, and `create_all()`; test login helpers set TESTING identity headers rather than relying only on legacy Flask-session fields. Test assertions unchanged, including negative import/MIME/rate-limit/rollback cases. After changes **20 passed in 7.97 s, exit 0**; user then reran with explicit temp DB override: **20 passed in 7.39s**, `git diff --check` passed, and selectively committed only three tests: **70 additions, 43 deletions, commit `cee1c3856bfebbd1370738d39f046bb3ffb51412`**. Protected dirty `core/admin_repo.py`, both seed scripts and `artifacts/` unchanged; **no push**. Baseline 138 original failures: **40 locally corrected/focused-verified** (3 announcements, 4 delete, 17 Planera VM, 16 import) → **98 provisional remaining**; whole-suite regression still unrun and could reveal interactions. Next: PYTEST RECOVERY 04, 13 original Tasks API failures in `tests/test_tasks_api.py` (six explicit HTTP 401 and seven follow-on `KeyError: task_id`); safely isolate module-scoped app and DB first, then fix test-only authentication while preserving negative RBAC and tenant-isolation behavior; no further K30-E2E until full recovery. No auth product changes permitted.

## PYTEST RECOVERY 04 – Tasks API fixtures (2026-11-01)

**CLOSED / LOCAL COMMIT `613c3b3c675bd7ea101d75dc10606f328afe0013`.** Local branch `feat/planera-app-shell-2026-03-03`, HEAD `cee1c3856bfebbd1370738d39f046bb3ffb51412`. Copilot verified `tests/test_tasks_api.py`: original baseline **13 failures** (6 direct 401, 7 downstream `KeyError: task_id` when task creation fails); isolated before-fix reproduction **13 failed**, mainly schema/HTTP500 due to missing `create_all()`. Only `tests/test_tasks_api.py` changed: module-scoped fixture uses `tmp_path_factory.mktemp("tasks-api")`, explicit temp SQLite main/Builder paths, `FORCE_DB_REINIT=True`, `create_all()`; auth fixture keeps session fields and sets TESTING headers for role, tenant, user to preserve role- and tenant-switching. **After-fix 13 passed in 1.31s**, also verified with `-s` and printed temp paths. User reran under a process-local temporary DB **13 passed in 1.14s**, selectively staged only `tests/test_tasks_api.py` (22 insertions, 2 deletions) and committed `613c3b3c675bd7ea101d75dc10606f328afe0013`. No push. Real behavior coverage: create/list, validation errors, unknown task, viewer denied on create/update, wrong tenant denied update, tenant B cannot see tenant A's task. No production-code changes; protected dirty `core/admin_repo.py`, two seed scripts, `artifacts/` unchanged; `git diff --check` passed, test-only commit confirmed, no push. Baseline 138 original failed test cases now **53 focused-verified corrections** (3 announcements + 4 deletion + 17 Planera VM + 16 import + 13 tasks), with **85 provisional remaining** pending full pytest rerun. Next step is selective one-file commit and then a new targeted cluster, avoiding unnecessary full-suite reruns until grouped repairs. User requested regression cleanup priority over new product development.

## PYTEST RECOVERY 05 – legacy dietary migration fixtures (2026-11-01)

**CLOSED / LOCAL COMMIT `54fe07fe37e0ec7d5c0ac11c4db1739afe268a2f`.** Branch `feat/planera-app-shell-2026-03-03`, local HEAD `613c3b3c675bd7ea101d75dc10606f328afe0013`, protected dirty `core/admin_repo.py`, `scripts/seed_ostergarden_from_json.py`, `scripts/seed_product2_e2e.py`, and `artifacts/` unchanged. Eight baseline `NoSuchTableError: users` failures reproduced from two legacy migrations test files. They stamped Alembic revision 0034 with only `dietary_types` populated, incorrectly omitting historically required `users` and `departments`. A temp SQLite database upgraded to actual 0034 confirms old users schema includes department_id but not yet auth_version (added 0045). Copilot modified **only** `tests/core/test_dietary_types_requirement_identity.py` and `tests/core/test_dietary_types_site_id_migration.py`: added a private `_seed_historical_0034_support(conn)` to each (users, departments, expected FK and users username unique index), used for older stamped schemas; **49 added lines per file, 98 insertions total, 0 deletions**. Actual Alembic upgrade from 0034 to head still exercised, with legacy row/identity, index, invalid semantics, duplicate and non-destructive downgrade assertions preserved. Focused rerun **22 passed in 7.39s**; adjoining `tests/core/test_user_auth_version_migration.py` **1 passed in 1.97s**; user then reran all three files together **23 passed in 5.63s**, selectively committed only two migration test files (**98 insertions, no deletions**) to local HEAD `54fe07fe37e0ec7d5c0ac11c4db1739afe268a2f`; git diff check passed. No migrations or production code modified; **selective test-only commit completed, no push**. Baseline **61/138** repaired and focus-verified, **77 provisional** pending full-suite run. Next: **PYTEST RECOVERY 06 READ-ONLY**: triage nine original `ValueError: duplicate_name` failures across core, planera, reporting, UI; inspect current dirty `core/admin_repo.py` modifications *without* changing/resetting them, compare working tree to HEAD for source of failures, confirm temporary DB before representative tests and group confirmed root causes. No code changes until review. Local navigation performance to Weekview user-observed as ~1s, defer PERF-01 diagnostics/optimization until regression recovery complete; do not touch functionality or assumptions before measuring local first.

## PYTEST RECOVERY 06 – duplicate_name nine-failure diagnosis (2026-11-01)

**READ-ONLY DIAGNOSIS VERIFIED; NINE TESTS STILL FAILING.** Preflight local `feat/planera-app-shell-2026-03-03`, HEAD `54fe07fe37e0ec7d5c0ac11c4db1739afe268a2f`, protected dirty unchanged; `git diff --check` PASS. Isolated run with `app_session` / `client_admin` SQLite at pytest temp path reproduced **9 failed, 0 passed** with `ValueError: duplicate_name`. Shared source: `SitesRepo.create_site()` automatically provisions canonical atomic dietary types for the new site via `DietTypesRepo.provision_canonical_atomic_catalog()` (including `Glutenfri`, `Laktosfri`, `Timbal`). Nine older tests across six files immediately call `DietTypesRepo.create(site_id=...,name=canonical)`, so the correct same-site duplicate guard rejects them. Runtime scope probe: same name allowed on distinct sites; same site denied. Dirty `core/admin_repo.py` diff affects only null site_id in the relevant check and all nine test sites are explicit; no demonstrated production regression. **No code changes** made in Recovery 06.

**Next gate PYTEST RECOVERY 07: test-only targeted correction.** In the six affected test files, obtain pre-provisioned canonical type IDs by site-scoped lookup (`DietTypesRepo.list_all(site_id=...)` / appropriate getter) rather than recreating them; when tests require `default_select=True`, explicitly use `DietTypesRepo.update(id, default_select=True)` and assert state before behavioral assertions, keeping canonical atomic semantics and requirement_key intact. A genuinely custom diet may use a uniquely named type if the test is not explicitly testing canonical nomenclature. Never delete canonical types, monkeypatch `_name_exists`, remove the site-provisioning behavior, or rewrite outcome assertions to hide new failures. Verify exactly the original nine tests and full six file slices with temporary DB; ensure negative same-site and positive cross-site duplicate policy remains tested; note any new functional/report failures separately. Protected `core/admin_repo.py`, seed scripts, `artifacts/` unchanged; no commit/push before review. Full suite still not rerun; 61 focused-verified of baseline 138, 77 provisional. PERF-01 local Weekview latency deferred.

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
