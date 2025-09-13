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
# Filename: tests/testing_harness/experiment_lifecycle/layer5/layer5_phase1_setup.ps1

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent
$TestEnvRoot = Join-Path $ProjectRoot "temp_test_environment"
$SandboxDir = Join-Path $TestEnvRoot "layer5_sandbox"
$SandboxDataDir = Join-Path $SandboxDir "data"
$TestConfigPath = Join-Path $SandboxDir "config.ini"
$TestDbPath = Join-Path $SandboxDataDir "personalities_db.txt"
$NewExperimentsDir = Join-Path $ProjectRoot "output/new_experiments"

try {

    # --- Cleanup from previous failed runs ---
    if (Test-Path $SandboxDir) {
        Write-Host "Cleaning up previous Layer 5 sandbox..."
        Remove-Item -Path $SandboxDir -Recurse -Force
    }
    Get-ChildItem -Path $NewExperimentsDir -Directory "l5_test_exp_*" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    Get-ChildItem -Path (Join-Path $ProjectRoot "output/migrated_experiments") -Directory "l5_test_exp_*" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

    # --- Create the test environment ---
    New-Item -ItemType Directory -Path $TestEnvRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $SandboxDataDir -Force | Out-Null

    # --- Create minimal, test-specific seed files ---
$dbContent = @"
1,Biography 1,Personality Text 1
2,Biography 2,Personality Text 2
3,Biography 3,Personality Text 3
4,Biography 4,Personality Text 4
"@
$dbContent.Trim() | Set-Content -Path $TestDbPath -Encoding UTF8

$configContent = @"
[Study]
num_replications = 1
num_trials = 2
group_size = 4
mapping_strategy = random
[LLM]
model_name = google/gemini-flash-1.5
temperature = 0.2
[DataGeneration]
personalities_db_file = $($TestDbPath -replace [regex]::Escape($ProjectRoot + "\"), "" -replace "\\", "/")
"@
$configContent.Trim() | Set-Content -Path $TestConfigPath -Encoding UTF8

    Write-Host ""
    Write-Host "--- Layer 5 Integration Testing: Experiment Migration ---" -ForegroundColor Magenta
    Write-Host "--- Phase 1: Automated Setup ---" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "1. Creating a valid base experiment using the sandbox config..."
    $output = & "$ProjectRoot\new_experiment.ps1" -ConfigPath $TestConfigPath -Verbose
    if ($LASTEXITCODE -ne 0) { throw "Setup failed: new_experiment.ps1 could not create the base experiment." }

    $OriginalExpPath = ($output | Out-String) -split '\r?\n' | Select-Object -Last 1
    if (-not (Test-Path $OriginalExpPath)) { throw "Setup failed: Could not parse the new experiment path from output." }

    # Rename the experiment to make it identifiable for this test layer
    $CorruptedExpPath = Join-Path $NewExperimentsDir "l5_test_exp_corrupted_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Rename-Item -Path $OriginalExpPath -NewName $CorruptedExpPath.Split('\')[-1]
    Write-Host "  -> Base experiment created and renamed to: $($CorruptedExpPath.Split('\')[-1])"

    Write-Host "`n2. Deliberately corrupting the experiment..."
    $runDir = Get-ChildItem -Path $CorruptedExpPath -Directory "run_*" | Select-Object -First 1
    if (-not $runDir) { throw "Setup failed: No run directory found in the new experiment." }

    # Corruption 1: Delete the archived config (CONFIG_ISSUE)
    Remove-Item -Path (Join-Path $runDir.FullName "config.ini.archived") -Force
    Write-Host "  -> Deleted archived config file."
    # Corruption 2: Delete a response file (RESPONSE_ISSUE)
    $responseFile = Get-ChildItem -Path $runDir.FullName -Filter "llm_response_*.txt" -Recurse | Select-Object -First 1
    Remove-Item -Path $responseFile.FullName -Force
    Write-Host "  -> Deleted a response file."

    Write-Host "`nIntegration test sandbox for Layer 5 created and corrupted successfully."
    Write-Host "Your next action is Step 2: Execute the Test Workflow."

}
catch {
    Write-Host "`nERROR: Layer 5 setup script failed.`n$($_.Exception.Message)" -ForegroundColor Red
    throw
}

# === End of tests/testing_harness/experiment_lifecycle/layer5/layer5_phase1_setup.ps1 ===
