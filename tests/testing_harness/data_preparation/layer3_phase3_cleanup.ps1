#!/usr/bin/env pwsh
# --- Layer 3: Data Pipeline Integration Testing ---
# --- Step 3: Automated Cleanup ---

param(
    [Parameter(Mandatory=$false)]
    [switch]$Force
)

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent
$SandboxParentDir = Join-Path $ProjectRoot "temp_test_environment"
$SandboxDir = Join-Path $SandboxParentDir "layer3_sandbox"

Write-Host ""
Write-Host "--- Layer 3: Data Pipeline Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Stage 3: Automated Cleanup ---" -ForegroundColor Cyan
Write-Host ""

if (Test-Path $SandboxDir) {
    if (-not $Force) {
        $confirmation = Read-Host -Prompt "This will permanently delete the Layer 3 test sandbox. Are you sure? (Y/N)"
        if ($confirmation -ne 'y') {
            Write-Host "`nOperation cancelled by user." -ForegroundColor Yellow
            exit 0
        }
    }
    Write-Host "Removing Layer 3 sandbox directory..."
    Remove-Item -Path $SandboxDir -Recurse -Force
    Write-Host "  -> Done."

    # Bonus: If this was the last test sandbox, remove the parent temp dir.
    if (-not (Get-ChildItem -Path $SandboxParentDir)) {
        Write-Host "Parent 'temp_test_environment' is now empty. Removing it as well."
        Remove-Item -Path $SandboxParentDir -Recurse -Force
        Write-Host "  -> Done."
    }
} else {
    Write-Host "Layer 3 sandbox directory not found. Nothing to remove."
}

Write-Host "`nCleanup complete." -ForegroundColor Green
Write-Host ""