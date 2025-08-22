#!/usr/bin/env pwsh
# --- Layer 5: Migration Workflow Integration Testing ---
# --- Step 3: Automated Cleanup ---

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer5_sandbox"
$NewExperimentsDir = Join-Path $ProjectRoot "output/new_experiments"
$MigratedExperimentsDir = Join-Path $ProjectRoot "output/migrated_experiments"

Write-Host ""
Write-Host "--- Layer 5: Migration Workflow Integration Testing ---" -ForegroundColor Cyan
Write-Host "--- Step 3: Automated Cleanup ---" -ForegroundColor Cyan
Write-Host ""

if (Test-Path $SandboxDir) {
    Write-Host "Removing Layer 5 sandbox directory..."
    Remove-Item -Path $SandboxDir -Recurse -Force
    Write-Host "  -> Done."
} else {
    Write-Host "Layer 5 sandbox directory not found. Nothing to remove."
}

$corruptedExp = Get-ChildItem -Path $NewExperimentsDir -Directory "l5_test_exp_*" -ErrorAction SilentlyContinue
if ($corruptedExp) {
    Write-Host "Removing corrupted test experiment..."
    $corruptedExp | Remove-Item -Recurse -Force
    Write-Host "  -> Done."
}

$migratedExp = Get-ChildItem -Path $MigratedExperimentsDir -Directory "l5_test_exp_*" -ErrorAction SilentlyContinue
if ($migratedExp) {
    Write-Host "Removing migrated test experiment..."
    $migratedExp | Remove-Item -Recurse -Force
    Write-Host "  -> Done."
}

Write-Host "`nCleanup complete." -ForegroundColor Green