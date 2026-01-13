param(
  [ValidateSet('major','minor','patch','rc')] [string]$Kind = 'patch',
  [switch]$NoPush
)

$ErrorActionPreference = 'Stop'

function Assert-Clean {
  $status = git status --porcelain
  if ($status) { throw "Working tree not clean. Commit or stash first." }
}

Assert-Clean

if ($Kind -eq 'rc') {
  # Create a release candidate tag without bumping VERSION.
  if (-not (Test-Path -Path "VERSION")) { throw "VERSION file not found" }
  $baseVersion = (Get-Content -Raw VERSION).Trim()
  if (-not $baseVersion) { throw "VERSION is empty" }

  # Determine next rc number based on existing tags v<version>-rcN
  $pattern = "v$baseVersion-rc*"
  $existing = git tag --list $pattern | ForEach-Object { $_ }
  $next = 1
  if ($existing) {
    $nums = @()
    foreach ($t in $existing) {
      if ($t -match "^v" + [regex]::Escape($baseVersion) + "-rc(\d+)$") {
        $nums += [int]$Matches[1]
      }
    }
    if ($nums.Count -gt 0) { $next = ([int]($nums | Measure-Object -Maximum).Maximum) + 1 }
  }

  $tag = "v$baseVersion-rc$next"
  git tag $tag

  if (-not $NoPush) {
    git push
    git push --tags
    Write-Host "Pushed $tag. GitHub Actions release workflow will create the RC release if configured."
  } else {
    Write-Host "Created tag $tag locally (NoPush)."
  }

  Write-Host "Done: $tag"
  exit 0
}

# 1) Bump VERSION via existing script (for major/minor/patch)
$python = (Get-Command python -ErrorAction SilentlyContinue)?.Source
if (-not $python) { throw "python not found on PATH" }

$newVersion = & $python tools/bump_version.py $Kind
if ($LASTEXITCODE -ne 0) { throw "Version bump failed" }

# 2) Commit + tag
git add VERSION
git commit -m "chore(release): bump version to $newVersion"
$tag = "v$newVersion"
git tag $tag

# 3) Push (optional)
if (-not $NoPush) {
  git push
  git push --tags
  Write-Host "Pushed $tag. GitHub Actions release workflow will create the Release body."
} else {
  Write-Host "Created tag $tag locally (NoPush)."
}

Write-Host "Done: $tag"