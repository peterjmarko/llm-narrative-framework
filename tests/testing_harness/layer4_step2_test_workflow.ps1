#!/usr/bin/env pwsh
# --- Layer 4: Main Workflow Integration Testing ---
# --- Step 2: Execute the Test Workflow ---

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer4_sandbox"
$TestConfigPath = Join-Path $SandboxDir "config.ini"

function Write-TestHeader { param($Message) Write-Host "`n--- $($Message) ---" -ForegroundColor Cyan }

try {
    Write-TestHeader "STEP 1: Creating a new experiment using the sandboxed config..."
    $output = & "$ProjectRoot\new_experiment.ps1" -ConfigPath $TestConfigPath -Verbose
    if ($LASTEXITCODE -ne 0) { throw "new_experiment.ps1 failed." }
    
    $NewExperimentPath = ($output | Out-String) -split '\r?\n' | Select-Object -Last 1
    if (-not (Test-Path $NewExperimentPath -PathType Container)) { throw "Could not parse new experiment path from output." }
    Write-Host "  -> New experiment created at: $NewExperimentPath"

    Write-TestHeader "STEP 2: Auditing the new experiment (should be VALIDATED)..."
    & "$ProjectRoot\audit_experiment.ps1" -ExperimentDirectory $NewExperimentPath -ConfigPath $TestConfigPath
    if ($LASTEXITCODE -ne 0) { throw "Initial audit failed. Experiment should be VALIDATED." }

    Write-TestHeader "STEP 3: Deliberately breaking the experiment..."
    $responseFile = Get-ChildItem -Path $NewExperimentPath -Filter "llm_response_*.txt" -Recurse | Select-Object -First 1
    if (-not $responseFile) { throw "Could not find a response file to delete." }
    Remove-Item -Path $responseFile.FullName -Force
    Write-Host "  -> Deleted response file: $($responseFile.Name)"

    Write-TestHeader "STEP 4: Auditing the broken experiment (should need REPAIR)..."
    & "$ProjectRoot\audit_experiment.ps1" -ExperimentDirectory $NewExperimentPath -ConfigPath $TestConfigPath
    if ($LASTEXITCODE -ne 2) { throw "Audit did not correctly identify the experiment as needing REPAIR (Exit Code 2)." }

    Write-TestHeader "STEP 5: Fixing the experiment automatically..."
    & "$ProjectRoot\fix_experiment.ps1" -ExperimentDirectory $NewExperimentPath -ConfigPath $TestConfigPath -NonInteractive -Verbose
    if ($LASTEXITCODE -ne 0) { throw "fix_experiment.ps1 failed to repair the experiment." }

    Write-TestHeader "STEP 6: Running final verification audit (should be VALIDATED)..."
    & "$ProjectRoot\audit_experiment.ps1" -ExperimentDirectory $NewExperimentPath -ConfigPath $TestConfigPath
    if ($LASTEXITCODE -ne 0) { throw "Final verification audit failed. Experiment should be VALIDATED." }
    
    Write-Host "`nSUCCESS: The full 'new -> audit -> break -> fix' lifecycle completed successfully." -ForegroundColor Green
    Write-Host "Inspect the artifacts, then run Step 3 to clean up."
}
catch {
    Write-Host "`nERROR: Layer 4 test workflow failed.`n$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}