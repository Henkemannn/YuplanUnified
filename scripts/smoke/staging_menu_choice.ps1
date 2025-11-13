param(
  [string]$BaseUrl = "https://yuplan-unified-staging.fly.dev",
  [string]$DeptId = "",  # provide a real department id if you want to scope; else it will create one
  [int]$Week = 47,
  [switch]$VerboseLog
)

# Minimal PowerShell smoke for /menu-choice API
# Steps:
# 1) Login as admin (simple auth assumed in staging)
# 2) Ensure a site+department exist (if $DeptId empty)
# 3) GET /menu-choice -> capture ETag
# 4) PUT idempotent (Alt1 -> Alt1) -> expect 204, same ETag
# 5) PUT mutation (Tue Alt1 -> Alt2) -> expect 204, different ETag; GET verifies days.tue == Alt2
# 6) Weekend PUT (Sat Alt2) -> expect 422
# 7) GET with If-None-Match -> expect 304

function Write-Log($msg){ if($VerboseLog){ Write-Host $msg } }

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

# 1) Login
Write-Log "Login as admin..."
$login = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/auth/login" -Method POST -Body (@{ role = 'admin' } | ConvertTo-Json) -ContentType 'application/json' -WebSession $session
if($login.StatusCode -ne 200){ throw "Login failed: $($login.StatusCode)" }

# Read CSRF token cookie for subsequent writes
function Get-CookieValue($name){
  $c = $session.Cookies.GetCookies($BaseUrl) | Where-Object { $_.Name -eq $name }
  if($c){ return [System.Web.HttpUtility]::UrlDecode($c.Value) }
  return ''
}
$csrf = Get-CookieValue 'csrf_token'
if(-not $csrf){ Write-Host "Warning: csrf_token missing; writes may fail" -ForegroundColor Yellow }

# 2) Ensure department
if([string]::IsNullOrWhiteSpace($DeptId)){
  Write-Log "Creating site+department for smoke..."
  $site = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/sites" -Method POST -Body (@{ name = 'SmokeSite' } | ConvertTo-Json) -Headers @{ 'Content-Type' = 'application/json'; 'X-CSRF-Token' = $csrf } -WebSession $session -SkipHttpErrorCheck
  if($site.StatusCode -ne 201){ throw "Create site failed: $($site.StatusCode)" }
  $siteJson = $site.Content | ConvertFrom-Json
  $dep = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/departments" -Method POST -Body (@{ site_id = $siteJson.id; name = 'SmokeDept'; resident_count_mode = 'fixed'; resident_count_fixed = 10 } | ConvertTo-Json) -Headers @{ 'Content-Type' = 'application/json'; 'X-CSRF-Token' = $csrf } -WebSession $session -SkipHttpErrorCheck
  if($dep.StatusCode -ne 201){ throw "Create department failed: $($dep.StatusCode)" }
  $DeptId = ($dep.Content | ConvertFrom-Json).id
}

# Helper: GET menu-choice
function Get-MenuChoice($week, $dept, $etag){
  $headers = @{}
  if($etag){ $headers['If-None-Match'] = $etag }
  return Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/menu-choice?week=$week&department=$dept" -Headers $headers -Method GET -WebSession $session
}
# Helper: PUT menu-choice
function Put-MenuChoice($week, $dept, $day, $choice, $etag){
  $headers = @{ 'If-Match' = $etag; 'Content-Type' = 'application/json'; 'X-CSRF-Token' = $csrf }
  return Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/menu-choice" -Method PUT -Body (@{ week = $week; department = $dept; day = $day; choice = $choice } | ConvertTo-Json) -Headers $headers -WebSession $session
}

# 3) GET -> ETag
$g1 = Get-MenuChoice -week $Week -dept $DeptId -etag $null
if($g1.StatusCode -ne 200){ throw "GET menu-choice failed: $($g1.StatusCode)" }
$etag1 = $g1.Headers['ETag']
if($etag1 -is [System.Array]){ $etag1 = $etag1[0] } else { $etag1 = [string]$etag1 }
if(-not $etag1){ throw "Missing ETag on initial GET" }
$body1 = $g1.Content | ConvertFrom-Json
if(-not $body1.days){ throw "Missing days in response" }

 # Use current Tue choice for idempotent check
$tueWas = [string]$body1.days.tue

# 4) PUT idempotent (Tue stays $tueWas)
$idem = Put-MenuChoice -week $Week -dept $DeptId -day 'tue' -choice $tueWas -etag $etag1
if($idem.StatusCode -ne 204){ throw "Idempotent PUT expected 204, got $($idem.StatusCode)" }
$etag2 = $idem.Headers['ETag']
if($etag2 -is [System.Array]){ $etag2 = $etag2[0] } else { $etag2 = [string]$etag2 }
if($etag2 -ne $etag1){ throw "Idempotent PUT changed ETag" }

# 5) PUT mutation Tue Alt1->Alt2
# Flip choice
$flip = if($tueWas -eq 'Alt2'){ 'Alt1' } else { 'Alt2' }
$mut = Put-MenuChoice -week $Week -dept $DeptId -day 'tue' -choice $flip -etag $etag1
if($mut.StatusCode -ne 204){ throw "Mutation PUT expected 204, got $($mut.StatusCode)" }
$etag3 = $mut.Headers['ETag']
if($etag3 -is [System.Array]){ $etag3 = $etag3[0] } else { $etag3 = [string]$etag3 }
if($etag3 -eq $etag1){ throw "Mutation PUT did not change ETag" }

# Verify via GET
$g2 = Get-MenuChoice -week $Week -dept $DeptId -etag $null
if($g2.StatusCode -ne 200){ throw "GET after mutation failed: $($g2.StatusCode)" }
$body2 = $g2.Content | ConvertFrom-Json
if($body2.days.tue -ne $flip){ throw "Expected Tue=$flip after mutation" }

# 6) Weekend rule
$wkend = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/menu-choice" -Method PUT -Body (@{ week = $Week; department = $DeptId; day = 'sat'; choice = 'Alt2' } | ConvertTo-Json) -Headers @{ 'If-Match' = $etag3; 'Content-Type'='application/json'; 'X-CSRF-Token' = $csrf } -WebSession $session -SkipHttpErrorCheck
if($wkend.StatusCode -ne 422){ throw "Weekend PUT expected 422, got $($wkend.StatusCode)" }

# 7) Conditional GET 304
$g3 = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/menu-choice?week=$Week&department=$DeptId" -Headers @{ 'If-None-Match' = $etag3 } -Method GET -WebSession $session -SkipHttpErrorCheck
if($g3.StatusCode -ne 304){ throw "GET with If-None-Match expected 304, got $($g3.StatusCode)" }

Write-Host "Smoke OK: /menu-choice idempotence, mutation, weekend rule, 304"
