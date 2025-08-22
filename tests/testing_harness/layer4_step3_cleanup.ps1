#!/usr/bin/env pwsh
# --- Layer 4: Main Workflow Integration Testing ---
# --- Step 3: Automated Cleanup ---

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer4_sandbox"
$NewExperimentsDir = Join-Path $ProjectRoot "output/new_experiments"

Write-Host ""
Write-Host "--- Layer 4: Main Workflow Integration Testing ---" -ForegroundColor Cyan
Write-Host "--- Step 3: Automated Cleanup ---" -ForegroundColor Cyan
Write-Host ""

if (Test-Path $SandboxDir) {
    Write-Host "Removing Layer 4 sandbox directory..."
    Remove-Item -Path $SandboxDir -Recurse -Force
    Write-Host "  -> Done."
} else {
    Write-Host "Layer 4 sandbox directory not found. Nothing to remove."
}

$testExperiments = Get-ChildItem -Path $NewExperimentsDir -Directory "experiment_*" -ErrorAction SilentlyContinue
if ($testExperiments) {
    Write-Host "Removing temporary experiment directories from 'output/new_experiments'..."
    $testExperiments | Remove-Item -Recurse -Force
    Write-Host "  -> Done."
} else {
    Write-Host "No temporary experiment directories found. Nothing to remove."
}

Write-Host "`nCleanup complete." -ForegroundColor Green