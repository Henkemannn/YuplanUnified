param(
  [string]$BaseUrl = $env:BASE_URL
)
if (-not $BaseUrl) { $BaseUrl = "https://yuplan-unified-staging.fly.dev" }
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$body = '{"role":"admin"}'
$res = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/auth/login" -Method Post -ContentType 'application/json' -Body $body -WebSession $session -ErrorAction SilentlyContinue
if ($res.StatusCode -lt 200 -or $res.StatusCode -ge 300) { Write-Error "Login failed: $($res.StatusCode)"; exit 1 }
# Print cookies
$cookies = $session.Cookies.GetCookies($BaseUrl)
foreach ($c in $cookies) { Write-Host "$($c.Name)=$([System.Web.HttpUtility]::UrlDecode($c.Value))" }
Write-Host "Login OK" -ForegroundColor Green
