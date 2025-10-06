param(
  [ValidateSet('major','minor','patch')] [string]$Kind = 'patch',
  [switch]$NoPush
)

$ErrorActionPreference = 'Stop'

function Assert-Clean {
  $status = git status --porcelain
  if ($status) { throw "Working tree not clean. Commit or stash first." }
}

Assert-Clean

# 1) Bump VERSION via existing script
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