param(
  [string]$BaseUrl = "https://yuplan-unified-staging.fly.dev"
)
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$body = '{"role":"admin"}'
$res = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/auth/login" -Method Post -ContentType 'application/json' -Body $body -WebSession $session
if ($res.StatusCode -lt 200 -or $res.StatusCode -ge 300) { throw "login_failed: $($res.StatusCode)" }
$sites = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/admin/sites" -Method Get -WebSession $session
$sites.Content
