# Staging: 403 origin_mismatch – uppdatera CORS_ALLOW_ORIGINS

Problem:

- `core/security._csrf_check` blockar GET/POST med `detail="origin_mismatch"` när Origin/Host inte tillåts.
- Fly-staging för `yuplan-unified-staging` saknade korrekt `CORS_ALLOW_ORIGINS`.

Lösning/Åtgärd:

1) Sätt secret på Fly (staging):

```
flyctl secrets set CORS_ALLOW_ORIGINS="https://yuplan-unified-staging.fly.dev" -a yuplan-unified-staging
```

Fly rullar en ny release automatiskt när secret ändras.

2) Verifiera att secret finns:

```
flyctl secrets list -a yuplan-unified-staging
```

Du ska se `CORS_ALLOW_ORIGINS` med en färsk timestamp.

3) Snabb manuell kontroll i browsern (i samma tabb efter att session satts via test-login):

- `https://yuplan-unified-staging.fly.dev/test-login`
- `https://yuplan-unified-staging.fly.dev/ui/weekview?site_id=5f8e2aea-9060-4981-9686-c70dbc723a11&department_id=cb763847-e326-42cb-8bb4-35a2cb823f52&year=2025&week=47`
- `https://yuplan-unified-staging.fly.dev/portal/week?site_id=5f8e2aea-9060-4981-9686-c70dbc723a11&department_id=cb763847-e326-42cb-8bb4-35a2cb823f52&year=2025&week=47`
- `https://yuplan-unified-staging.fly.dev/ui/admin`
- `https://yuplan-unified-staging.fly.dev/ui/reports/weekview?site_id=5f8e2aea-9060-4981-9686-c70dbc723a11&year=2025&week=47`

Förväntat: alla GET svarar 200 och renderar UI (ingen `origin_mismatch`).

4) Valfritt POST-sanitetstest:

- Öppna DevTools → Network, trigga en enkel POST i Portal/Weekview/Admin.
- Kontrollera Request Headers:
  - Origin: `https://yuplan-unified-staging.fly.dev`
  - Host: `yuplan-unified-staging.fly.dev`
- Om POST ger 403 `origin_mismatch`, notera värdena för Origin/Host för vidare felsökning.

Status:

- Secret är nu satt i staging. Vi parkerar vidare felsökning tills vi har mer ork/tid.
