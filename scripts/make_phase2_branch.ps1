# Usage: Run this after RC1 is merged into the default branch
# It will update local refs and (re)create/update the phase 2 branch cleanly.

param(
    [string]$DefaultBranch = "feat/admin-limits-inspection",
    [string]$Phase2Branch = "feat/admin-authz-phase2"
)

Write-Host "Fetching latest refs..."
git fetch --all --prune

Write-Host "Checking out default branch: $DefaultBranch"
git checkout $DefaultBranch
git pull --ff-only origin $DefaultBranch

${exists} = git branch --list $Phase2Branch
if ($exists -and ($exists.Trim().Length -gt 0)) {
    Write-Host "Branch $Phase2Branch exists locally. Rebase onto $DefaultBranch..."
    git checkout $Phase2Branch
    git rebase $DefaultBranch
} else {
    Write-Host "Creating new branch $Phase2Branch from $DefaultBranch..."
    git checkout -b $Phase2Branch $DefaultBranch
}

Write-Host "Pushing $Phase2Branch to origin (upstream)..."
git push -u origin $Phase2Branch

Write-Host "Done. You can now work on Admin AuthZ Phase 2."
