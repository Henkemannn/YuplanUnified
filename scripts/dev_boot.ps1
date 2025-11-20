Param(
  [int]$Year = (Get-Date).Year,
  [int]$Week = 47,
  [string]$SiteId,
  [string]$DepartmentId,
  [switch]$Force,
  [switch]$Open
)

# Dev bootstrap helper for STAGING_SIMPLE_AUTH=1 environment.
# 1. Logs in as admin (demo auth)
# 2. Creates site & department if IDs not supplied
# 3. Enables ff.weekview.enabled
# 4. Prints Weekview URL
# Usage:
#   pwsh -File scripts/dev_boot.ps1 -Week 47 -Open
#   pwsh -File scripts/dev_boot.ps1 -SiteId 10 -DepartmentId 22 -Year 2025 -Week 48 -Open

$ErrorActionPreference = 'Stop'
$base = "http://localhost:5000"

Write-Host "[dev_boot] Starting bootstrap against $base" -ForegroundColor Cyan

# Web session for cookie persistence
$s = New-Object Microsoft.PowerShell.Commands.WebRequestSession

function Get-CsrfToken($session) {
  ($session.Cookies.GetCookies($base) | Where-Object { $_.Name -eq 'csrf_token' }).Value
}

# Demo login (requires STAGING_SIMPLE_AUTH=1 in app env)
Write-Host "[dev_boot] Logging in as demo admin" -ForegroundColor Cyan
$loginBody = @{ role = 'admin' } | ConvertTo-Json
$login = Invoke-RestMethod -Method POST -Uri "$base/auth/login" -WebSession $s -ContentType 'application/json' -Body $loginBody
$csrf = Get-CsrfToken -session $s
if(-not $csrf){ throw "Missing CSRF cookie after login." }
$headers = @{ 'X-CSRF-Token' = $csrf }

if(-not $SiteId -or -not $DepartmentId -or $Force) {
  Write-Host "[dev_boot] Creating site & department" -ForegroundColor Cyan
  if($SiteId -and -not $Force) { Write-Host "[dev_boot] Using provided IDs (skip create)." -ForegroundColor Yellow }
  if(-not $SiteId -or $Force) {
    $siteName = "Demo Site $(Get-Random -Minimum 100 -Maximum 999)"
    $siteBody = @{ name = $siteName } | ConvertTo-Json
    $siteResp = Invoke-RestMethod -Method POST -Uri "$base/admin/sites" -WebSession $s -Headers $headers -ContentType 'application/json' -Body $siteBody
    $SiteId = [string]$siteResp.id
    Write-Host "[dev_boot] Created site: $siteName (ID=$SiteId)" -ForegroundColor Green
  }
  if(-not $DepartmentId -or $Force) {
    $deptName = "Avd $(Get-Random -Minimum 1 -Maximum 9)"
    $deptBody = @{ site_id = $SiteId; name = $deptName; resident_count_mode = 'fixed'; resident_count_fixed = 0 } | ConvertTo-Json
    $deptResp = Invoke-RestMethod -Method POST -Uri "$base/admin/departments" -WebSession $s -Headers $headers -ContentType 'application/json' -Body $deptBody
    $DepartmentId = [string]$deptResp.id
    Write-Host "[dev_boot] Created department: $deptName (ID=$DepartmentId)" -ForegroundColor Green
  }
}

# Enable feature flag (tenant context comes from session)
Write-Host "[dev_boot] Enabling ff.weekview.enabled" -ForegroundColor Cyan
$ffBody = @{ name = 'ff.weekview.enabled'; enabled = $true } | ConvertTo-Json
$ffResp = Invoke-RestMethod -Method POST -Uri "$base/admin/feature_flags" -WebSession $s -Headers $headers -ContentType 'application/json' -Body $ffBody
Write-Host "[dev_boot] Feature flag enabled: $($ffResp.feature)=$($ffResp.enabled)" -ForegroundColor Green

$url = "$base/ui/weekview?site_id=$SiteId&department_id=$DepartmentId&year=$Year&week=$Week"
Write-Host "[dev_boot] Weekview URL:" -ForegroundColor Cyan
Write-Host "          $url" -ForegroundColor Magenta

if ($Open) {
  try {
    Start-Process $url | Out-Null
    Write-Host "[dev_boot] Opened browser." -ForegroundColor Green
  } catch {
    Write-Host "[dev_boot] Could not auto-open browser. Run: Start-Process '$url'" -ForegroundColor Yellow
  }
} else {
  Write-Host "[dev_boot] Open in browser with: Start-Process '$url'" -ForegroundColor Cyan
}
