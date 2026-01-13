Param(
  [string]$AppHost = "127.0.0.1",
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

function Get-OpenAPISpec {
  $uri = "http://${AppHost}:$Port/openapi.json"
  Write-Host "Fetching $uri"
  $json = Invoke-RestMethod -Uri $uri
  $json | ConvertTo-Json -Depth 100 | Out-File -Encoding utf8 openapi.json
  Write-Host "Wrote openapi.json"
}

function Test-OpenAPIDiff {
  if (-not (Test-Path openapi.json)) { Get-OpenAPISpec }
  if (-not (Test-Path specs\openapi.baseline.json)) {
    Write-Error "Baseline specs/openapi.baseline.json missing. Create it first."
    return
  }
  python scripts/openapi_diff.py specs/openapi.baseline.json openapi.json --report openapi-diff.txt --json-report openapi-diff.json
  if ($LASTEXITCODE -eq 0) {
    Write-Host 'Semantic diff: OK (no breaking)' -ForegroundColor Green
  } else {
    Write-Warning 'Semantic diff reported breaking changes (see openapi-diff.txt)'
  }
}

function Test-OpenAPILint {
  if (-not (Get-Command spectral -ErrorAction SilentlyContinue)) {
    Write-Warning 'spectral not installed (npm install -g @stoplight/spectral-cli)'
    return
  }
  if (-not (Test-Path openapi.json)) { Get-OpenAPISpec }
  spectral lint openapi.json
}

function Invoke-OpenAPITests {
  # Run only OpenAPI-related tests if they exist
  $tests = Get-ChildItem tests/test_openapi_*.py -ErrorAction SilentlyContinue
  if (-not $tests) {
    Write-Warning 'No OpenAPI-specific test files found.'
    return
  }
  pytest -q $($tests | ForEach-Object { $_.FullName })
}

function Invoke-OpenAPIWorkflow {
  Get-OpenAPISpec
  Test-OpenAPIDiff
  Test-OpenAPILint
  Invoke-OpenAPITests
  Write-Host 'OpenAPI workflow complete.'
}

function Invoke-SmokeTest {
  $body = @{ items = @(@{ name = "Spaghetti Bolognese" }) } | ConvertTo-Json
  $resp = Invoke-RestMethod -Method Post -Uri "http://${AppHost}:$Port/import/menu" -ContentType "application/json" -Body $body
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
  .\scripts\dev.ps1; Test-App

  # Fetch spec then spectral lint (if spectral installed globally via npm)
  .\scripts\dev.ps1; Get-OpenAPISpec

  # Full OpenAPI workflow
  .\scripts\dev.ps1; Invoke-OpenAPIWorkflow
#>
