#!/usr/bin/env pwsh
# --- Layer 3: Data Pipeline Integration Testing ---
# --- Step 3: Automated Cleanup ---

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer3_sandbox"

Write-Host ""
Write-Host "--- Layer 3: Data Pipeline Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 3: Automated Cleanup ---" -ForegroundColor Cyan
Write-Host ""

if (Test-Path $SandboxDir) {
    Write-Host "Removing Layer 3 sandbox directory..."
    Remove-Item -Path $SandboxDir -Recurse -Force
    Write-Host "  -> Done."
} else {
    Write-Host "Layer 3 sandbox directory not found. Nothing to remove."
}

Write-Host "`nCleanup complete." -ForegroundColor Green
Write-Host ""