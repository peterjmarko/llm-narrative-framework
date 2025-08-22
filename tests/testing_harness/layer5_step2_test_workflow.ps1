#!/usr/bin/env pwsh
# --- Layer 5: Migration Workflow Integration Testing ---
# --- Step 2: Execute the Test Workflow ---

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer5_sandbox"
$TestConfigPath = Join-Path $SandboxDir "config.ini"

function Write-TestHeader { param($Message) Write-Host "`n--- $($Message) ---" -ForegroundColor Cyan }

try {
    $CorruptedExp = Get-ChildItem -Path (Join-Path $ProjectRoot "output/new_experiments") -Directory "l5_test_exp_*"
    if (-not $CorruptedExp) { throw "Could not find the corrupted experiment directory. Please run Step 1 first." }

    Write-TestHeader "STEP 1: Auditing the corrupted experiment (should need MIGRATION)..."
    & "$ProjectRoot\audit_experiment.ps1" -ExperimentDirectory $CorruptedExp.FullName -ConfigPath $TestConfigPath
    if ($LASTEXITCODE -ne 3) { throw "Audit did not correctly identify the experiment as needing MIGRATION (Exit Code 3)." }

    Write-TestHeader "STEP 2: Running the migration..."
    & "$ProjectRoot\migrate_experiment.ps1" -ExperimentDirectory $CorruptedExp.FullName -ConfigPath $TestConfigPath -NonInteractive
    if ($LASTEXITCODE -ne 0) { throw "migrate_experiment.ps1 failed." }

    $MigratedExp = Get-ChildItem -Path (Join-Path $ProjectRoot "output/migrated_experiments") -Directory ($CorruptedExp.Name + "_migrated_*") | Sort-Object CreationTime -Descending | Select-Object -First 1
    if (-not $MigratedExp) { throw "Could not find the output directory for the migrated experiment." }
    Write-Host "  -> Migration created new experiment at: $($MigratedExp.Name)"

    Write-TestHeader "STEP 3: Running final verification audit on the migrated experiment (should be VALIDATED)..."
    & "$ProjectRoot\audit_experiment.ps1" -ExperimentDirectory $MigratedExp.FullName -ConfigPath $TestConfigPath
    if ($LASTEXITCODE -ne 0) { throw "Final verification audit failed. The migrated experiment should be VALIDATED." }
    
    Write-Host "`nSUCCESS: The full 'corrupt -> audit -> migrate -> validate' lifecycle completed successfully." -ForegroundColor Green
    Write-Host "Inspect the artifacts, then run Step 3 to clean up."
}
catch {
    Write-Host "`nERROR: Layer 5 test workflow failed.`n$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}