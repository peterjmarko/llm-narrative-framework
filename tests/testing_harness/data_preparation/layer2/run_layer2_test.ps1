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
# Filename: tests/testing_harness/data_preparation/layer2/run_layer2_test.ps1

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

# --- Helper Functions ---
function Get-ProjectRoot {
    param($StartPath)
    $currentDir = $StartPath
    while ($currentDir -ne $null -and $currentDir -ne "") {
        if (Test-Path (Join-Path $currentDir "pyproject.toml")) { return $currentDir }
        $currentDir = Split-Path -Parent -Path $currentDir
    }
    throw "FATAL: Could not find project root (pyproject.toml) by searching up from '$StartPath'."
}

# --- Define Paths ---
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Get-ProjectRoot -StartPath $PSScriptRoot
$TestDir = Join-Path $ProjectRoot "temp_test_environment/layer2_mock_sandbox"
$OrchestratorSource = Join-Path $ProjectRoot "prepare_data.ps1"
function Test-OrchestratorState {
    param($StepName, [switch]$ShouldExist, [string[]]$Files)
    $pass = $true
    foreach ($file in $Files) {
        if ($ShouldExist -and -not (Test-Path $file)) {
            Write-Host "  -> FAIL [$StepName]: Expected file not found: $file" -ForegroundColor Red
            $pass = $false
        } elseif (-not $ShouldExist -and (Test-Path $file)) {
            Write-Host "  -> FAIL [$StepName]: Unexpected file found: $file" -ForegroundColor Red
            $pass = $false
        }
    }
    if ($pass) { Write-Host "  -> PASS [$StepName]: State verified." -ForegroundColor Green }
    if (-not $pass) { throw "State verification failed for step: $StepName" }
}

# --- Main Test Logic ---
Write-Host "`n--- Layer 2: Data Pipeline Orchestration Testing ---" -ForegroundColor Magenta
$cleanupPath = $null
try {
    # --- Phase 1: Automated Setup ---
    Write-Host "`n--- Phase 1: Automated Setup ---" -ForegroundColor Cyan
    if (Test-Path $TestDir) { Remove-Item -Path $TestDir -Recurse -Force }
    $cleanupPath = $TestDir # Mark for cleanup even if script fails
    New-Item -Path $TestDir -ItemType Directory | Out-Null
    $srcDir = New-Item -Path (Join-Path $TestDir "src") -ItemType Directory
    @("sources", "reports", "processed", "intermediate", "foundational_assets/neutralized_delineations") | ForEach-Object {
        New-Item -Path (Join-Path $TestDir "data/$_") -ItemType Directory -Force | Out-Null
    }

    Write-Host "  -> Copying orchestrator to test sandbox..."
    Copy-Item -Path $OrchestratorSource -Destination $TestDir

    Write-Host "  -> Parsing orchestrator to build mock scripts..."
    $pipelineContent = Get-Content $OrchestratorSource -Raw
    # Directly find all lines that define an automated step by looking for the Script and Output keys.
    # This is more robust than parsing the entire multi-line block.
    $automatedSteps = $pipelineContent | Select-String -Pattern 'Script="([^"]+?)".*?Output="([^"]+?)"' -AllMatches | ForEach-Object { $_.Matches }

    foreach ($match in $automatedSteps) {
        $scriptName = Split-Path $match.Groups[1].Value -Leaf
        $outputFile = $match.Groups[2].Value
        
        $mockContent = ""
        if ($scriptName -eq "generate_eminence_scores.py") {
            $mockContent = @"
import sys
from pathlib import Path
# This mock simulates creating the output file AND its summary file.
output = Path('$outputFile')
output.parent.mkdir(parents=True, exist_ok=True)
output.touch()
summary_file = Path('data/reports/eminence_scores_summary.txt')
summary_file.parent.mkdir(parents=True, exist_ok=True)
summary_file.write_text('Total in Source: 100\nTotal Scored: 100')
sys.exit(0)
"@
        } elseif ($scriptName -eq "generate_ocean_scores.py") {
            $mockContent = @"
import sys
from pathlib import Path
# This mock simulates creating the output file AND its summary file.
output = Path('$outputFile')
output.parent.mkdir(parents=True, exist_ok=True)
output.touch()
summary_file = Path('data/reports/ocean_scores_summary.txt')
summary_file.parent.mkdir(parents=True, exist_ok=True)
summary_file.write_text('Total in Source: 100\nTotal Scored: 100')
sys.exit(0)
"@
        } elseif ($scriptName -eq "neutralize_delineations.py") {
            $mockContent = @"
import sys
from pathlib import Path
# This mock simulates creating the full directory of neutralized files.
output_dir = Path('$outputFile').parent
output_dir.mkdir(parents=True, exist_ok=True)
expected_files = [
    "balances_elements.csv", "balances_modes.csv", "balances_hemispheres.csv",
    "balances_quadrants.csv", "balances_signs.csv", "points_in_signs.csv"
]
for f in expected_files:
    (output_dir / f).touch()
sys.exit(0)
"@
        } else {
            $mockContent = @"
import sys
from pathlib import Path
# This mock simulates the creation of the expected output file.
output = Path('$outputFile')
output.parent.mkdir(parents=True, exist_ok=True)
output.touch()
sys.exit(0)
"@
        }
        Set-Content -Path (Join-Path $srcDir $scriptName) -Value $mockContent
    }
    Write-Host "  -> Successfully created $($automatedSteps.Count) mock scripts."

    Set-Location $TestDir

    # --- Phase 2: Execute Test Workflow ---
    Write-Host "`n--- Phase 2: Execute Test Workflow ---" -ForegroundColor Cyan
    
    # Test 1: Default run, should halt at first manual step
    Write-Host "`n--> Testing initial run (halts on manual step)..."
    $output = & .\prepare_data.ps1 -Force -TestMode 2>&1
    if ($LASTEXITCODE -ne 1) { throw "Expected pipeline to halt with exit code 1, but got $($LASTEXITCODE)." }
    Test-OrchestratorState "Halt 1" -ShouldExist -Files "data/intermediate/sf_data_import.txt"
    Test-OrchestratorState "Halt 1" -Files "data/foundational_assets/sf_chart_export.csv" # Should NOT exist

    # Test 2: Simulate first manual step, should halt at second
    Write-Host "`n--> Testing resumed run (halts on second manual step)..."
    New-Item -Path "data/foundational_assets/sf_chart_export.csv" -ItemType File | Out-Null
    $output = & .\prepare_data.ps1 -Force -TestMode -Resumed 2>&1
    if ($LASTEXITCODE -ne 1) { throw "Expected pipeline to halt with exit code 1, but got $($LASTEXITCODE)." }
    # Verify that the pipeline has halted at the 'Delineation Export' step, BEFORE running 'Neutralize Delineations'.
    Test-OrchestratorState "Halt 2" -ShouldExist -Files "data/foundational_assets/sf_chart_export.csv"
    Test-OrchestratorState "Halt 2" -Files "data/foundational_assets/neutralized_delineations/balances_quadrants.csv" # Should NOT exist

    # Test 3: Simulate final manual step, should complete successfully
    Write-Host "`n--> Testing final resumed run (completes successfully)..."
    New-Item -Path "data/foundational_assets/sf_delineations_library.txt" -ItemType File | Out-Null
    $output = & .\prepare_data.ps1 -Force -TestMode -Resumed 2>&1
    if ($LASTEXITCODE -ne 0 -or $output -notmatch "Pipeline Completed Successfully") { throw "Expected pipeline to complete but it did not." }
    Test-OrchestratorState "Completion" -ShouldExist -Files "data/personalities_db.txt"

    Write-Host "`nSUCCESS: Layer 2 orchestrator test completed successfully." -ForegroundColor Green
}
finally {
    # --- Phase 3: Automated Cleanup ---
    Set-Location $ProjectRoot
    if ($cleanupPath -and (Test-Path $cleanupPath)) {
        Write-Host "`n--- Phase 3: Automated Cleanup ---" -ForegroundColor Cyan
        Remove-Item -Path $cleanupPath -Recurse -Force
        Write-Host "  -> Mock test environment cleaned up successfully."
    }
}

# === End of tests/testing_harness/data_preparation/layer2/run_layer2_test.ps1 ===
