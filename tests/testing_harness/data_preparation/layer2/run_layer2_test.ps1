#!/usr/bin/env pwsh
#-*- coding: utf-8 -*-
#
# A Framework for Testing Complex Narrative Systems
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
    
    Write-Host "  -> Copying config.ini to test sandbox..."
    $configSource = Join-Path $ProjectRoot "config.ini"
    if (Test-Path $configSource) {
        Copy-Item -Path $configSource -Destination $TestDir
    }

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
import os
import sys
# This mock simulates creating the output file AND its summary file.
output_path = '$outputFile'
os.makedirs(os.path.dirname(output_path), exist_ok=True)
open(output_path, 'a').close()
summary_path = 'data/reports/eminence_scores_summary.txt'
os.makedirs(os.path.dirname(summary_path), exist_ok=True)
with open(summary_path, 'w') as f:
    f.write('Total in Source: 100\nTotal Scored: 100')
sys.exit(0)
"@
        } elseif ($scriptName -eq "generate_ocean_scores.py") {
            $mockContent = @"
import os
import sys
# This mock simulates creating the output file AND its summary file.
output_path = '$outputFile'
os.makedirs(os.path.dirname(output_path), exist_ok=True)
open(output_path, 'a').close()
summary_path = 'data/reports/ocean_scores_summary.txt'
os.makedirs(os.path.dirname(summary_path), exist_ok=True)
with open(summary_path, 'w') as f:
    f.write('Total in Source: 100\nTotal Scored: 100')
    
# Also create the validation summary file that the pipeline summary script needs
validation_summary_path = 'data/reports/adb_validation_summary.txt'
os.makedirs(os.path.dirname(validation_summary_path), exist_ok=True)
with open(validation_summary_path, 'w') as f:
    f.write('Total Records in Report: 100\nValid Records: 100 (100.0%)\nFailed Records: 0 (0.0%)')

sys.exit(0)
"@
        } elseif ($scriptName -eq "neutralize_delineations.py") {
            $mockContent = @"
import os
import sys
import json
# This mock simulates creating the full directory of neutralized files.
output_path = '$outputFile'
output_dir = os.path.dirname(output_path)
os.makedirs(output_dir, exist_ok=True)
expected_files = {
    'balances_elements.csv': 8,
    'balances_modes.csv': 6,
    'balances_hemispheres.csv': 4,
    'balances_quadrants.csv': 4,
    'balances_signs.csv': 12,
    'points_in_signs.csv': 144
}
for filename, line_count in expected_files.items():
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        lines = [f'mock_line_{i+1}' for i in range(line_count)]
        f.write('\n'.join(lines) + '\n')

# Also create pipeline_completion_info.json with matching LLM from config
import configparser
config = configparser.ConfigParser()
config.read('config.ini')
current_llm = config.get('DataGeneration', 'neutralization_model', fallback='mock_model')

completion_info_path = 'data/reports/pipeline_completion_info.json'
os.makedirs(os.path.dirname(completion_info_path), exist_ok=True)
completion_info = {
    'neutralize_delineations': {
        'llm_used': current_llm
    }
}
with open(completion_info_path, 'w') as f:
    json.dump(completion_info, f)
sys.exit(0)
"@
        } else {
            $mockContent = @"
import os
import sys
# This mock simulates the creation of the expected output file.
output_path = '$outputFile'
os.makedirs(os.path.dirname(output_path), exist_ok=True)
open(output_path, 'a').close()
sys.exit(0)
"@
        }
        Set-Content -Path (Join-Path $srcDir $scriptName) -Value $mockContent
    }
    Write-Host "  -> Successfully created $($automatedSteps.Count) mock scripts."

    Set-Location $TestDir

    # Set environment variable for additional sandbox detection
    $env:PROJECT_SANDBOX_PATH = $TestDir

    # --- Phase 2: Execute Test Workflow ---
    Write-Host "`n--- Phase 2: Execute Test Workflow ---" -ForegroundColor Cyan
    
    # Test 1: Default run, should halt at first manual step
    Write-Host "`n--> Testing initial run (halts on manual step)..."
    # Ensure manual step files don't exist in production (they would cause test to fail)
    # Move files to a temp directory to preserve timestamps
    $prodDelineations = Join-Path $ProjectRoot "data/foundational_assets/sf_delineations_library.txt"
    $prodChartExport = Join-Path $ProjectRoot "data/foundational_assets/sf_chart_export.csv"
    
    # Also hide Solar Fire export directory files
    $documentsFolder = [System.Environment]::GetFolderPath('Personal')
    $sfDelineations = Join-Path $documentsFolder "Solar Fire User Files\Export\sf_delineations_library.txt"
    $sfChartExport = Join-Path $documentsFolder "Solar Fire User Files\Export\sf_chart_export.csv"
    
    # Create temp backup directory
    $tempBackupDir = Join-Path $TestDir ".test_file_backup"
    New-Item -Path $tempBackupDir -ItemType Directory -Force | Out-Null
    
    if (Test-Path $prodDelineations) { 
        Write-Host "  -> WARNING: Temporarily hiding production delineations file for test isolation" -ForegroundColor Yellow
        Move-Item $prodDelineations (Join-Path $tempBackupDir "prod_sf_delineations_library.txt") -Force 
    }
    if (Test-Path $prodChartExport) { 
        Write-Host "  -> WARNING: Temporarily hiding production chart export for test isolation" -ForegroundColor Yellow
        Move-Item $prodChartExport (Join-Path $tempBackupDir "prod_sf_chart_export.csv") -Force 
    }
    if (Test-Path $sfDelineations) { 
        Write-Host "  -> WARNING: Temporarily hiding Solar Fire delineations file for test isolation" -ForegroundColor Yellow
        Move-Item $sfDelineations (Join-Path $tempBackupDir "sf_sf_delineations_library.txt") -Force 
    }
    if (Test-Path $sfChartExport) { 
        Write-Host "  -> WARNING: Temporarily hiding Solar Fire chart export for test isolation" -ForegroundColor Yellow
        Move-Item $sfChartExport (Join-Path $tempBackupDir "sf_sf_chart_export.csv") -Force 
    }
    
    $output = & .\prepare_data.ps1 -Force -TestMode -SuppressConfigDisplay 2>&1
    if ($LASTEXITCODE -ne 1) { throw "Expected pipeline to halt with exit code 1, but got $($LASTEXITCODE)." }
    Test-OrchestratorState "Halt 1" -ShouldExist -Files "data/intermediate/sf_data_import.txt"
    Test-OrchestratorState "Halt 1" -Files "data/foundational_assets/sf_chart_export.csv" # Should NOT exist

    # Test 2: Simulate first manual step (Step 9), should halt at second manual step (Step 10)
    Write-Host "`n--> Testing resumed run (halts on second manual step)..."
    # Restore Solar Fire delineations file to simulate user completing Step 9
    $backedUpSfDelin = Join-Path $tempBackupDir "sf_sf_delineations_library.txt"
    if (Test-Path $backedUpSfDelin) {
        Move-Item $backedUpSfDelin $sfDelineations -Force
    }
    $output = & .\prepare_data.ps1 -Force -TestMode -Resumed -SuppressConfigDisplay 2>&1
    if ($LASTEXITCODE -ne 1) { throw "Expected pipeline to halt with exit code 1, but got $($LASTEXITCODE)." }
    # Verify that the pipeline has completed Step 9 and halted at Step 10 (Astrology Data Export)
    Test-OrchestratorState "Halt 2" -ShouldExist -Files "data/foundational_assets/sf_delineations_library.txt"
    Test-OrchestratorState "Halt 2" -Files "data/foundational_assets/sf_chart_export.csv" # Should NOT exist yet

    # Test 3: Simulate final manual step (Step 10), should complete successfully
    Write-Host "`n--> Testing final resumed run (completes successfully)..."
    # Restore Solar Fire chart export file to simulate user completing Step 10
    $backedUpSfChart = Join-Path $tempBackupDir "sf_sf_chart_export.csv"
    if (Test-Path $backedUpSfChart) {
        Move-Item $backedUpSfChart $sfChartExport -Force
    }
    $output = & .\prepare_data.ps1 -Force -TestMode -Resumed -SuppressConfigDisplay 2>&1
    Write-Host "Pipeline output:"
    Write-Host $output
    Write-Host "LASTEXITCODE: $LASTEXITCODE"
    if ($LASTEXITCODE -ne 0 -or $output -notmatch "Pipeline Completed Successfully") { 
        Write-Host "Pipeline failed. Exit code: $LASTEXITCODE"
        Write-Host "Output content:"
        $output | ForEach-Object { Write-Host "  $_" }
        throw "Expected pipeline to complete but it did not." 
    }
    Test-OrchestratorState "Completion" -ShouldExist -Files "data/personalities_db.txt"

    Write-Host "`nSUCCESS: Layer 2 orchestrator test completed successfully." -ForegroundColor Green
}
finally {
    # --- Phase 3: Automated Cleanup ---
    Set-Location $ProjectRoot
    
    # Restore production files if they were backed up
    $prodDelineations = Join-Path $ProjectRoot "data/foundational_assets/sf_delineations_library.txt"
    $prodChartExport = Join-Path $ProjectRoot "data/foundational_assets/sf_chart_export.csv"
    $documentsFolder = [System.Environment]::GetFolderPath('Personal')
    $sfDelineations = Join-Path $documentsFolder "Solar Fire User Files\Export\sf_delineations_library.txt"
    $sfChartExport = Join-Path $documentsFolder "Solar Fire User Files\Export\sf_chart_export.csv"
    $tempBackupDir = Join-Path $TestDir ".test_file_backup"
    
    # Restore from temp backup directory
    $backedUpProdDelin = Join-Path $tempBackupDir "prod_sf_delineations_library.txt"
    $backedUpProdChart = Join-Path $tempBackupDir "prod_sf_chart_export.csv"
    $backedUpSfDelin = Join-Path $tempBackupDir "sf_sf_delineations_library.txt"
    $backedUpSfChart = Join-Path $tempBackupDir "sf_sf_chart_export.csv"
    
    if (Test-Path $backedUpProdDelin) {
        Move-Item $backedUpProdDelin $prodDelineations -Force
        Write-Host "  -> Restored production delineations file" -ForegroundColor Cyan
    }
    if (Test-Path $backedUpProdChart) {
        Move-Item $backedUpProdChart $prodChartExport -Force
        Write-Host "  -> Restored production chart export file" -ForegroundColor Cyan
    }
    if (Test-Path $backedUpSfDelin) {
        Move-Item $backedUpSfDelin $sfDelineations -Force
        Write-Host "  -> Restored Solar Fire delineations file" -ForegroundColor Cyan
    }
    if (Test-Path $backedUpSfChart) {
        Move-Item $backedUpSfChart $sfChartExport -Force
        Write-Host "  -> Restored Solar Fire chart export file" -ForegroundColor Cyan
    }
    
    if ($cleanupPath -and (Test-Path $cleanupPath)) {
        Write-Host "`n--- Phase 3: Automated Cleanup ---" -ForegroundColor Cyan
        Remove-Item -Path $cleanupPath -Recurse -Force
        Write-Host "  -> Mock test environment cleaned up successfully."
    }
}

# === End of tests/testing_harness/data_preparation/layer2/run_layer2_test.ps1 ===
