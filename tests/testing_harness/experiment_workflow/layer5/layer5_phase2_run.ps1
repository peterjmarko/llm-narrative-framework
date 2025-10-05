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
# Filename: tests/testing_harness/experiment_workflow/layer5/layer5_phase2_run.ps1

$C_ORANGE = "`e[38;5;208m"
$C_RESET = "`e[0m"

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer5_sandbox"
$StudyDir = Join-Path $SandboxDir "test_study"

function Write-TestHeader { param($Message, $Color = 'Blue') Write-Host "--- $($Message) ---" -ForegroundColor $Color }

Write-Host ""
Write-Host "--- Layer 5 Integration Testing: Study Compilation ---" -ForegroundColor Magenta
Write-Host "--- Phase 2: Run Test Workflow ---" -ForegroundColor Cyan

try {
    Write-TestHeader "STEP 1: Auditing the study (should be READY for compilation)..."

    # Use the same approach as Layer 4: create a test config that matches the experiments
    $TestConfigPath = Join-Path $StudyDir "test_config.ini"
    # Find config file - try experiment level first, then replication level
    $firstExp = Get-ChildItem -Path $StudyDir -Directory -Filter "experiment_*" | Select-Object -First 1
    $firstExpConfig = Join-Path $firstExp.FullName "config.ini.archived"
    if (-not (Test-Path $firstExpConfig)) {
        $runDir = Get-ChildItem -Path $firstExp.FullName -Directory -Filter "run_*" | Select-Object -First 1
        if ($runDir) {
            $firstExpConfig = Join-Path $runDir.FullName "config.ini.archived"
        }
    }
    # Use complete project config but override replication count from experiment
    $expReplicationCount = (Get-Content $firstExpConfig | Select-String "num_replications.*=.*(\d+)").Matches[0].Groups[1].Value
    Copy-Item -Path "$ProjectRoot\config.ini" -Destination $TestConfigPath -Force
    (Get-Content $TestConfigPath) -replace "num_replications\s*=\s*\d+", "num_replications = $expReplicationCount" | Set-Content $TestConfigPath

    # Audit the study using the same pattern as Layer 4
    & "$ProjectRoot\audit_study.ps1" -StudyDirectory $StudyDir -ConfigPath $TestConfigPath -NoHeader
    if ($LASTEXITCODE -ne 0) {
        throw "Study audit failed. Expected experiments to be VALIDATED (Exit Code 0), but got Exit Code $LASTEXITCODE"
    }
    Write-Host "  -> Study ready for compilation." -ForegroundColor Green
    Write-Host ""

    Write-TestHeader "STEP 2: Running the compile_study.ps1 workflow..."
    
    # Run the main compile_study.ps1 workflow - this will handle its own pre-flight audit
    # Use -NoLog to prevent transcript issues in the test environment
    & "$ProjectRoot\compile_study.ps1" -StudyDirectory $StudyDir -ConfigPath $TestConfigPath -NoLog -Verbose
    if ($LASTEXITCODE -ne 0) { throw "compile_study.ps1 failed with exit code $LASTEXITCODE" }
    
    Write-Host "  -> Study compilation and analysis completed successfully." -ForegroundColor Green
    Write-Host ""

    Write-TestHeader "STEP 3: Verifying generated artifacts..."
    
    # Check that the main study results file was created
    $studyResultsFile = Join-Path $StudyDir "STUDY_results.csv"
    if (-not (Test-Path $studyResultsFile)) {
        throw "Expected STUDY_results.csv was not created"
    }
    Write-Host "  -> ✓ STUDY_results.csv created successfully" -ForegroundColor Green

    # Check that the analysis directory was created
    $anovaDir = Join-Path $StudyDir "anova"
    if (-not (Test-Path $anovaDir -PathType Container)) {
        throw "Expected anova/ directory was not created"
    }
    Write-Host "  -> ✓ anova/ analysis directory created" -ForegroundColor Green

    # Check for key analysis files
    $analysisLog = Join-Path $anovaDir "STUDY_analysis_log.txt"
    $boxplotsDir = Join-Path $anovaDir "boxplots"
    $diagnosticsDir = Join-Path $anovaDir "diagnostics"

    if (-not (Test-Path $analysisLog)) {
        throw "Expected STUDY_analysis_log.txt was not created"
    }
    Write-Host "  -> ✓ STUDY_analysis_log.txt created" -ForegroundColor Green

    if (-not (Test-Path $boxplotsDir -PathType Container)) {
        throw "Expected boxplots/ directory was not created"
    }
    Write-Host "  -> ✓ boxplots/ directory created" -ForegroundColor Green

    if (-not (Test-Path $diagnosticsDir -PathType Container)) {
        throw "Expected diagnostics/ directory was not created"
    }
    Write-Host "  -> ✓ diagnostics/ directory created" -ForegroundColor Green

    # Verify the content of STUDY_results.csv has the expected structure
    $studyContent = Get-Content $studyResultsFile
    if ($studyContent.Length -lt 2) {
        throw "STUDY_results.csv appears to be empty or missing header"
    }
    
    $headerLine = $studyContent[0]
    $expectedColumns = @("run_directory", "mapping_strategy", "k", "mean_mrr", "mean_top_1_acc")
    $missingColumns = $expectedColumns | Where-Object { $headerLine -notlike "*$_*" }
    if ($missingColumns) {
        throw "STUDY_results.csv missing expected columns: $($missingColumns -join ', ')"
    }
    Write-Host "  -> ✓ STUDY_results.csv has expected column structure" -ForegroundColor Green

    # Verify we have data for all 4 experiments
    $dataRowCount = $studyContent.Length - 1
    $expectedRows = 4  # 4 experiments in factorial design
    if ($dataRowCount -ne $expectedRows) {
        throw "Expected $expectedRows data rows in STUDY_results.csv, but found $dataRowCount"
    }
    Write-Host "  -> ✓ STUDY_results.csv contains expected number of data rows ($dataRowCount)" -ForegroundColor Green
    Write-Host ""

    Write-TestHeader "STEP 4: Running final verification audit (should still be COMPLETE)..."
    
    # Verify the study is still marked as complete after analysis
    & "$ProjectRoot\audit_study.ps1" -StudyDirectory $StudyDir -ConfigPath $TestConfigPath -NoHeader
    if ($LASTEXITCODE -ne 0) { 
        throw "Final audit failed. Study should be marked as COMPLETE (Exit Code 0), but got Exit Code $LASTEXITCODE" 
    }
    Write-Host "  -> ✓ Study correctly identified as COMPLETE" -ForegroundColor Green
    Write-Host ""

    Write-TestHeader "STEP 5: Verifying analysis log content..."
    
    # Check that the analysis log contains expected content or explains why analysis was skipped
    $logContent = Get-Content $analysisLog -Raw
    if ($logContent -like "*All models were filtered out*") {
        Write-Host "  -> ✓ Analysis correctly filtered out models with insufficient data (expected for test data)" -ForegroundColor Green
    } else {
        $expectedSections = @("ANOVA Results", "Descriptive Statistics", "mapping_strategy", "k")
        $missingSections = $expectedSections | Where-Object { $logContent -notlike "*$_*" }
        if ($missingSections) {
            throw "Analysis log missing expected sections: $($missingSections -join ', ')"
        }
        Write-Host "  -> ✓ Analysis log contains expected statistical sections" -ForegroundColor Green
    }
    
    # Additional validation for statistical quality
    if ($logContent -notlike "*p-value*" -and $logContent -notlike "*F-statistic*" -and $logContent -notlike "*p_value*") {
        Write-Host "  -> ⚠ Warning: Analysis log may be missing statistical test results" -ForegroundColor Yellow
    } else {
        Write-Host "  -> ✓ Analysis log contains statistical test results" -ForegroundColor Green
    }

    Write-Host "`nSUCCESS: The full 'audit -> compile -> verify' study lifecycle completed successfully." -ForegroundColor Green
    Write-Host "All artifacts were generated correctly and the study is now complete." -ForegroundColor Green
}
catch {
    Write-Host "`nERROR: Layer 5 test workflow failed.`n$($_.Exception.Message)" -ForegroundColor Red
    # Re-throw the original exception to the master runner.
    throw
}

# === End of tests/testing_harness/experiment_workflow/layer5/layer5_phase2_run.ps1 ===
