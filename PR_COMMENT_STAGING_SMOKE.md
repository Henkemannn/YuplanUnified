# Staging smoke — Admin Phase B

Expected:
- Every write returns ETag.
- Alt2: second identical PUT returns 200 with the same collection ETag.
- Department with stale If-Match → 412 + ProblemDetails (type, title, status, detail, current_etag).
- HEAD on `/api/admin/departments/{id}` should return the same ETag as GET (when exposed).

Commands:

# 1) Create site
curl -i -X POST $HOST/api/admin/sites \
  -H 'Content-Type: application/json' \
  -d '{"name":"Varberg Midsommargården"}'

# 2) Create department
curl -i -X POST $HOST/api/admin/departments \
  -H 'Content-Type: application/json' \
  -d '{"site_id":"<site-id>","name":"Avd 1","resident_count_mode":"fixed","resident_count_fixed":24}'

# 3) GET department (capture ETag) – or read it from POST response headers
curl -i $HOST/api/admin/departments/<dep-id>

# 4) Update department with If-Match (expect 200 + new ETag)
curl -i -X PUT $HOST/api/admin/departments/<dep-id> \
  -H 'If-Match: W/"<ver>"' \
  -H 'Content-Type: application/json' \
  -d '{"name":"Avd 1 – Öst"}'

# 5) Alt2 bulk — first write (start at collection version v0)
curl -i -X PUT $HOST/api/admin/alt2 \
  -H 'If-Match: W/"admin:alt2:week:51:v0"' \
  -H 'Content-Type: application/json' \
  -d '{"week":51,"items":[{"department_id":"<dep-id>","weekday":1,"enabled":true},{"department_id":"<dep-id>","weekday":3,"enabled":true}]}'

# 6) Alt2 bulk — idempotent second write (expect same collection ETag)
curl -i -X PUT $HOST/api/admin/alt2 \
  -H 'If-Match: <ETag-from-step-5>' \
  -H 'Content-Type: application/json' \
  -d '{"week":51,"items":[{"department_id":"<dep-id>","weekday":1,"enabled":true},{"department_id":"<dep-id>","weekday":3,"enabled":true}]}'

# 7) Trigger 412 by using stale If-Match on department
curl -i -X PUT $HOST/api/admin/departments/<dep-id> \
  -H 'If-Match: W/"<stale-ver>"' \
  -H 'Content-Type: application/json' \
  -d '{"name":"Stale Write"}'
