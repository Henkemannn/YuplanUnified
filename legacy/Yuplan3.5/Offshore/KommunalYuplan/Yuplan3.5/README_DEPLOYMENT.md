# Yuplan – Deploy / IT Paket (Version 3.5)

Detta dokument beskriver hur IT kan köra och uppdatera Yuplan (Flask‑baserat kostregistreringssystem) i fryst (.exe) form.

Version: 3.5  
Build-datum: 2025-09-18  
Release-typ: Intern drift / serverinstallation

## Leveransinnehåll (one‑file build)
Minimal nödvändig leverans:
```
Yuplan_v3.5.exe          # Körbar fil (PyInstaller one-file)
LICENSE                  # Proprietär intern licens / användningsvillkor
README_DEPLOYMENT.md     # Detta dokument
```
Skapas automatiskt vid första körning om de saknas:
```
kost.db                  # SQLite databas (persistent, bredvid exe)
uploads/                 # Katalog för uppladdade filer
```
INBAKADE i exe (behöver INTE distribueras separat):
```
templates/               # Jinja2 templates
static/                  # CSS, JS, ikoner, manifest, service worker
```
OBS: Ändringar i externa templates/static mappar påverkar INTE körningen (override stöds ej i denna version).

## Systemkrav
- Windows 10/11 (64‑bit)
- Ingen separat Python-installation (runtime inbäddad)
- Port 5000 måste vara ledig (intern åtkomst). För klienter i nät: öppna brandvägg för inbound TCP 5000.

## Starta
1. Placera `Yuplan_v3.5.exe` i valfri skrivbar katalog (t.ex. `C:\Yuplan`).
2. Dubbelklicka exe.
3. Vid första körning:
  - Inbäddade resurser packas temporärt upp.
  - `kost.db` kopieras ut om den saknas annars ny tom databas skapas (auto‑init av tabeller).
  - `uploads/` skapas (eller kopieras från inbakad default om sådan fanns).
4. Surfa till: `http://127.0.0.1:5000` eller `http://<server-ip>:5000` inom nätverket.

Porten är statisk (5000) i denna version; port‑override stöds ej ännu.

## Loggar
Loggning sker för närvarande till konsolfönster. Ingen filrotation eller loggkatalog används i denna version. Om behov finns kan logg till fil läggas till i framtida build.

## Databas & Persistens
- Databasfil: `kost.db` (bredvid exe) – skapas automatiskt om saknas.
- Tabeller initieras via inbyggd auto‑init (CREATE TABLE IF NOT EXISTS).
- Backup: kopiera `kost.db` när programmet är stoppat (eller använd en kopia-säker shadow‑copy om live).
- Schemaändringar kräver ny version (ingen migrationsmotor).
- Uppladdade filer ligger i `uploads/` bredvid exe.

## Uppdateringar (ny version)
1. Stoppa körande instans (stäng konsolfönster / task manager).
2. Byt ut endast `Yuplan_v3.5.exe` (låter `kost.db` och `uploads/` ligga kvar).
3. Starta igen.
4. Gör en snabb funktionskontroll (rapport, personalvy, markeringar).
5. Om front‑end ändå verkar “cachead”: Ctrl+F5 i webbläsare.

NOTERA: Templates och static är inbakade → inga separata filer att ersätta.

## Säkerhet / Avgränsningar
- Ingen TLS/HTTPS – om extern åtkomst krävs: placera bakom reverse proxy (NGINX/IIS) med TLS‑terminering.
- Ingen autentisering på nätverksnivå – kör inom betrott internt nät.
- Filuppladdningar: inkludera `uploads/` i backup-rutin.

## Snabb funktionscheck efter installation
1. Starta exe → se “START AV APPEN” i konsolen.
2. Öppna personalvy → aktuell vecka visas (inte alltid vecka 1).
3. Markera några kosttyper → uppdateringar lagras.
4. Gå till rapport → samma vecka som senast vald bör vara förvald.
5. Lägg till (eller redigera) boendeantal i adminpanel.
6. Exportera rapport till Excel.
7. Ladda upp ett dokument → kontrollera att filen dyker upp i `uploads/`.

## Avinstallation
Stoppa programmet och radera katalogen. Inga registerposter eller globala komponenter installeras.

## Licens
Detta är ett proprietärt internt system. All kod och binaries är konfidentiella och får endast användas inom Yuplan / av behörig personal enligt villkor i `LICENSE`.

Otillåten kopiering, distribution, dekompilering eller vidareanvändning är förbjuden. Kontakta systemägare för frågor om utökad användning.

## Kontakt / Ändringsförslag
Henrik Jonsson, Yuplan.

---
Detta dokument uppdateras vid behov i framtida versioner.
