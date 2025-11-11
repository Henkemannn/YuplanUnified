param(
  [string]$BaseUrl = $env:BASE_URL,
  [string]$SiteId = $env:SITE_ID,
  [int]$Week = 51
)

if (-not $BaseUrl) { $BaseUrl = "https://yuplan-unified-staging.fly.dev" }

Write-Host "Smoke start => $BaseUrl (site=$SiteId, week=$Week)" -ForegroundColor Cyan

# Create a WebSession to persist cookies
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

# 1) Login as admin (staging simple auth)
try {
  $body = '{"role":"admin"}'
  $res = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/auth/login" -Method Post -ContentType 'application/json' -Body $body -WebSession $session
  if ($res.StatusCode -lt 200 -or $res.StatusCode -ge 300) { throw "login_failed: $($res.StatusCode)" }
  Write-Host "Login OK" -ForegroundColor Green
} catch {
  Write-Error $_
  exit 1
}

# Helper: read cookie value
function Get-CookieValue($name) {
  $c = $session.Cookies.GetCookies($BaseUrl) | Where-Object { $_.Name -eq $name }
  if ($c) { return [System.Web.HttpUtility]::UrlDecode($c.Value) }
  return ''
}
$csrf = Get-CookieValue 'csrf_token'
if (-not $csrf) { Write-Host "Warning: csrf_token cookie missing; writes may fail" -ForegroundColor Yellow }

# Require SiteId for departments tests
if (-not $SiteId) {
  Write-Host "SITE_ID not provided; set -SiteId or $env:SITE_ID for full smoke. Skipping dept checks." -ForegroundColor Yellow
} else {
  # 2) Departments list
  try {
    $res = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/departments?site_id=$SiteId" -WebSession $session -Method Get
    $deptsEtag = $res.Headers['ETag']
    if ($deptsEtag -is [System.Array]) { $deptsEtag = $deptsEtag[0] } else { $deptsEtag = [string]$deptsEtag }
    if (-not $deptsEtag) { throw 'no_depts_etag' }
    $data = $res.Content | ConvertFrom-Json
    $first = $data.items[0]
    Write-Host "Departments ETag: $deptsEtag" -ForegroundColor Gray
    # 2a) Conditional GET -> 304
    $headers = @{ 'If-None-Match' = $deptsEtag }
  $res304 = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/departments?site_id=$SiteId" -WebSession $session -Method Get -Headers $headers -SkipHttpErrorCheck
    if ($res304.StatusCode -ne 304) { throw "expected_304_got_$($res304.StatusCode)" }
    Write-Host "Departments 304 OK" -ForegroundColor Green
    # 2b) PUT rename first with If-Match
  # PowerShell-safe ETag construction (avoid escape pitfalls with -f)
  $ifMatch = ('W/"admin:dept:{0}:v{1}"' -f $first.id, $first.version)
    $headers2 = @{ 'If-Match'=$ifMatch; 'X-CSRF-Token'=$csrf; 'Content-Type'='application/json' }
  # Use a unique name per run to avoid potential unique constraints in staging
  $suffix = (Get-Date).ToUniversalTime().ToString('HHmmss') + '-' + (Get-Random -Minimum 10 -Maximum 99)
  $newName = "Dept (smoke) $suffix"
    $body2 = (@{ name=$newName } | ConvertTo-Json -Compress)
  $resPut = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/departments/$($first.id)" -WebSession $session -Method Put -Headers $headers2 -Body $body2 -SkipHttpErrorCheck
    if ($resPut.StatusCode -lt 200 -or $resPut.StatusCode -ge 300) {
      Write-Host "Rename response body:" -ForegroundColor Yellow
      Write-Host $resPut.Content
      throw "rename_failed_$($resPut.StatusCode)"
    }
    Write-Host "Department PUT OK (If-Match)" -ForegroundColor Green
    # 2c) GET again -> collection ETag must bump
    $res2 = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/departments?site_id=$SiteId" -WebSession $session -Method Get
    $newEtag = $res2.Headers['ETag']
    if (-not $newEtag) { throw 'no_new_depts_etag' }
    if ($newEtag -eq $deptsEtag) { throw "collection_etag_not_bumped" }
    Write-Host "Departments ETag bumped: $newEtag" -ForegroundColor Green
    # 2d) Conditional GET with stale ETag -> 200
    $res200 = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/departments?site_id=$SiteId" -WebSession $session -Method Get -Headers @{ 'If-None-Match'=$deptsEtag } -ErrorAction SilentlyContinue
    if ($res200.StatusCode -ne 200) { throw "expected_200_with_stale_got_$($res200.StatusCode)" }
    Write-Host "Departments stale ETag => 200 OK" -ForegroundColor Green
  } catch {
    Write-Error $_
    exit 1
  }
}

# 3) Alt2 flow for week
try {
  $res = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/alt2?week=$Week" -WebSession $session -Method Get
  $alt2Etag = $res.Headers['ETag']
  if ($alt2Etag -is [System.Array]) { $alt2Etag = $alt2Etag[0] } else { $alt2Etag = [string]$alt2Etag }
  if (-not $alt2Etag) { throw 'no_alt2_etag' }
  $alt2 = $res.Content | ConvertFrom-Json
  Write-Host "Alt2 ETag: $alt2Etag" -ForegroundColor Gray
  # 3a) Conditional GET 304
  $res2 = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/alt2?week=$Week" -WebSession $session -Method Get -Headers @{ 'If-None-Match'=$alt2Etag } -SkipHttpErrorCheck
  if ($res2.StatusCode -ne 304) { throw "alt2_expected_304_got_$($res2.StatusCode)" }
  Write-Host "Alt2 304 OK" -ForegroundColor Green
  # 3b) Idempotent PUT
  $headers3 = @{ 'If-Match'=$alt2Etag; 'X-CSRF-Token'=$csrf; 'Content-Type'='application/json' }
  $body3 = (@{ week=$Week; items=$alt2.items } | ConvertTo-Json -Compress)
  $res3 = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/alt2" -WebSession $session -Method Put -Headers $headers3 -Body $body3 -SkipHttpErrorCheck
  if ($res3.StatusCode -lt 200 -or $res3.StatusCode -ge 300) { throw "alt2_idem_failed_$($res3.StatusCode)" }
  Write-Host "Alt2 PUT idempotent OK" -ForegroundColor Green
  # ETag should remain the same after idempotent update
  $res3b = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/alt2?week=$Week" -WebSession $session -Method Get -SkipHttpErrorCheck
  $etagAfterIdem = $res3b.Headers['ETag']
  if ($etagAfterIdem -is [System.Array]) { $etagAfterIdem = $etagAfterIdem[0] } else { $etagAfterIdem = [string]$etagAfterIdem }
  if ($etagAfterIdem -ne $alt2Etag) { throw 'alt2_etag_changed_after_idempotent' }
  Write-Host "Alt2 ETag stable after idempotent: $etagAfterIdem" -ForegroundColor Green
  # 3c) Toggle first item and PUT
  if ($alt2.items.Count -gt 0) {
    $first = $alt2.items[0]
    $first.enabled = -not [bool]$first.enabled
  $body4 = (@{ week=$Week; items=@($first) } | ConvertTo-Json -Compress)
  $res4 = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/alt2" -WebSession $session -Method Put -Headers $headers3 -Body $body4 -SkipHttpErrorCheck
    if ($res4.StatusCode -lt 200 -or $res4.StatusCode -ge 300) { throw "alt2_toggle_failed_$($res4.StatusCode)" }
    Write-Host "Alt2 PUT toggle OK" -ForegroundColor Green
    # ETag should change after toggle
  $res4b = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/alt2?week=$Week" -WebSession $session -Method Get -SkipHttpErrorCheck
  $etagAfterToggle = $res4b.Headers['ETag']
  if ($etagAfterToggle -is [System.Array]) { $etagAfterToggle = $etagAfterToggle[0] } else { $etagAfterToggle = [string]$etagAfterToggle }
    if ($etagAfterToggle -eq $alt2Etag) { throw 'alt2_etag_not_bumped_after_toggle' }
    # 304 with new ETag
  $res4c = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/alt2?week=$Week" -WebSession $session -Method Get -Headers @{ 'If-None-Match'=$etagAfterToggle } -SkipHttpErrorCheck
    if ($res4c.StatusCode -ne 304) { throw "alt2_expected_304_after_toggle_got_$($res4c.StatusCode)" }
    # 200 with stale
  $res4d = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/alt2?week=$Week" -WebSession $session -Method Get -Headers @{ 'If-None-Match'=$alt2Etag } -SkipHttpErrorCheck
    if ($res4d.StatusCode -ne 200) { throw "alt2_expected_200_with_stale_got_$($res4d.StatusCode)" }
    Write-Host "Alt2 ETag bumped and conditional GET behavior OK" -ForegroundColor Green
  } else {
    Write-Host "Alt2 has no items; skipping toggle" -ForegroundColor Yellow
  }
} catch {
  Write-Error $_
  exit 1
}

Write-Host "Smoke PASSED" -ForegroundColor Green
exit 0
