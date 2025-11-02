param(
  [string]$Base = "feat/admin-limits-inspection",
  [string]$Name = "feat/admin-authz-phase3"
)

# Creates Phase 3 branch from default base and pushes it
# Usage:
#   pwsh ./scripts/make_phase3_branch.ps1
#   pwsh ./scripts/make_phase3_branch.ps1 -Base main -Name feat/phase3

$ErrorActionPreference = "Stop"

Write-Host "Fetching remotes..." -ForegroundColor Cyan
git fetch origin --prune

Write-Host "Checking out base '$Base'..." -ForegroundColor Cyan
git checkout $Base

git pull --ff-only origin $Base

Write-Host "Creating new branch '$Name' from '$Base'..." -ForegroundColor Cyan
# If branch exists locally, delete it first (safe if no uncommitted changes)
git rev-parse --verify $Name | Out-Null
if ($LASTEXITCODE -eq 0) {
  Write-Host "Local branch exists; deleting..." -ForegroundColor Yellow
  git branch -D $Name | Out-Null
}

git checkout -b $Name

Write-Host "Pushing branch to origin..." -ForegroundColor Cyan
git push -u origin $Name

Write-Host "Done. New branch is '$Name'." -ForegroundColor Green
