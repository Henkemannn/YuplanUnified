Param(
  [string]$Host = "127.0.0.1",
  [int]$Port = 5000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Install-Deps {
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  try { pip install openapi-spec-validator requests | Out-Null } catch { Write-Warning "Optional extra deps failed: $_" }
}

function Start-App {
  python run.py
}

function Test-App {
  pytest -q
}

function Lint-App {
  ruff check .
}

function Format-App {
  ruff format .
}

function Fetch-OpenAPI {
  $uri = "http://$Host:$Port/openapi.json"
  Write-Host "Fetching $uri"
  $json = Invoke-RestMethod -Uri $uri
  $json | ConvertTo-Json -Depth 100 | Out-File -Encoding utf8 openapi.json
  Write-Host "Wrote openapi.json"
}

function Smoke {
  $body = @{ items = @(@{ name = "Spaghetti Bolognese" }) } | ConvertTo-Json
  $resp = Invoke-RestMethod -Method Post -Uri "http://$Host:$Port/import/menu" -ContentType "application/json" -Body $body
  $resp | ConvertTo-Json -Depth 10
  Write-Host "smoke ok"
}

<#+
Examples:
  # Install dependencies
  .\scripts\dev.ps1; Install-Deps

  # Run app
  .\scripts\dev.ps1; Start-App

  # Lint + test
  .\scripts\dev.ps1; Lint-App; Test-App

  # Fetch spec then spectral lint (if spectral installed globally via npm)
  .\scripts\dev.ps1; Fetch-OpenAPI
#>
