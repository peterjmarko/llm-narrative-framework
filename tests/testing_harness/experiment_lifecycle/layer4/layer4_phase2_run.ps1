#!/usr/bin/env pwsh
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 Peter J. Marko
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Filename: tests/testing_harness/experiment_lifecycle/layer4/layer4_phase2_run.ps1

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer4_sandbox"
$TestConfigPath = Join-Path $SandboxDir "config.ini"

function Write-TestHeader { param($Message, $Color = 'Blue') Write-Host "`n--- $($Message) ---" -ForegroundColor $Color }

Write-Host "--- Layer 4 Integration Testing: Experiment Creation ---" -ForegroundColor Magenta
Write-Host "--- Phase 2: Run Test Workflow ---" -ForegroundColor Cyan

try {
    Write-TestHeader "STEP 1: Creating a new experiment..."

    # Diagnostic Step: Verify the config file content before running the experiment.
    $configContent = Get-Content $TestConfigPath -Raw
    $modelName = if ($configContent -match 'model_name\s*=\s*(.*)') { $matches[1].Trim() } else { 'NOT_FOUND' }
    $numReps = if ($configContent -match 'num_replications\s*=\s*(.*)') { $matches[1].Trim() } else { 'NOT_FOUND' }
    Write-Host "  -> Verification: Using config with model '$modelName' and $numReps replication(s)." -ForegroundColor Gray
    
    Write-Host "`n`nHALT: Sandbox prepared. Inspect the generated config.ini, then press Enter to create the new experiment..." -ForegroundColor Yellow
    Read-Host | Out-Null # Capture input without echoing

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
    # Re-throw the original exception to the master runner.
    throw
}

# === End of tests/testing_harness/experiment_lifecycle/layer4/layer4_phase2_run.ps1 ===
