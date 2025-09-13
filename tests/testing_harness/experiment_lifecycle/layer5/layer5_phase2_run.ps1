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
# Filename: tests/testing_harness/experiment_lifecycle/layer5/layer5_phase2_run.ps1

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer5_sandbox"
$TestConfigPath = Join-Path $SandboxDir "config.ini"

function Write-TestHeader { param($Message, $Color = 'Blue') Write-Host "`n--- $($Message) ---" -ForegroundColor $Color }

Write-Host "--- Layer 5 Integration Testing: Experiment Migration ---" -ForegroundColor Magenta
Write-Host "Phase 2: Run Test Workflow" -ForegroundColor Cyan

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
    throw
}

# === End of tests/testing_harness/experiment_lifecycle/layer5/layer5_phase2_run.ps1 ===
