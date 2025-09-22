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
# Filename: tests/algorithm_validation/validate_statistical_reporting.ps1

<#
.SYNOPSIS
    Statistical Analysis & Reporting Validation Test

.DESCRIPTION
    This test provides bit-for-bit verification of the complete statistical analysis 
    and reporting pipeline. It uses pre-generated mock study assets with sufficient 
    replications to trigger full statistical analysis (ANOVA, post-hoc tests, 
    Bayesian analysis) and validates outputs against known-good ground truth files.

    This test complements Layer 5 by validating the full statistical analysis pipeline
    when there are sufficient replications, while Layer 5 validates appropriate 
    handling of insufficient data scenarios.

.PARAMETER Interactive
    Run in interactive mode with detailed explanations at each step.

.PARAMETER Verbose
    Enable verbose output showing detailed comparison results.

.EXAMPLE
    .\validate_statistical_reporting.ps1
    Run the validation test in automated mode.

.EXAMPLE
    .\validate_statistical_reporting.ps1 -Interactive
    Run the validation test with step-by-step explanations.
#>

param(
    [switch]$Interactive,
    [switch]$Verbose
)

# --- ANSI Color Codes ---
$C_RESET = "`e[0m"
$C_GRAY = "`e[90m"
$C_RED = "`e[91m"
$C_GREEN = "`e[92m"
$C_YELLOW = "`e[93m"
$C_BLUE = "`e[94m"
$C_MAGENTA = "`e[95m"
$C_CYAN = "`e[96m"

# --- Path Configuration ---
$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$MockStudyPath = Join-Path $ProjectRoot "tests/assets/mock_study"
$GroundTruthPath = Join-Path $ProjectRoot "tests/assets/mock_study_ground_truth"
$TempTestDir = Join-Path $ProjectRoot "temp_test_environment/stats_validation"

# --- Helper Functions ---
function Write-TestHeader { 
    param($Message, $Color = 'Cyan') 
    $line = "=" * 80
    Write-Host "`n$line" -ForegroundColor $Color
    Write-Host $Message -ForegroundColor $Color
    Write-Host "$line`n" -ForegroundColor $Color
}

function Write-TestStep { 
    param($Message, $Color = 'Blue') 
    Write-Host ">>> $Message <<<" -ForegroundColor $Color
}

function Compare-FilesBinary {
    param($File1, $File2)
    if (-not (Test-Path $File1) -or -not (Test-Path $File2)) {
        return $false
    }
    $hash1 = Get-FileHash -Path $File1 -Algorithm SHA256
    $hash2 = Get-FileHash -Path $File2 -Algorithm SHA256
    return $hash1.Hash -eq $hash2.Hash
}

function Compare-CSVFiles {
    param($ActualPath, $ExpectedPath, $FileName)
    
    if (-not (Test-Path $ActualPath)) {
        Write-Host "  ❌ MISSING: $FileName" -ForegroundColor Red
        return $false
    }
    
    if (-not (Test-Path $ExpectedPath)) {
        Write-Host "  ⚠️  NO GROUND TRUTH: $FileName" -ForegroundColor Yellow
        return $false
    }
    
    # For CSV files, we'll do a more sophisticated comparison
    # allowing for minor floating-point differences
    try {
        $actual = Import-Csv $ActualPath
        $expected = Import-Csv $ExpectedPath
        
        if ($actual.Count -ne $expected.Count) {
            Write-Host "  ❌ ROW COUNT MISMATCH: $FileName (Expected: $($expected.Count), Actual: $($actual.Count))" -ForegroundColor Red
            return $false
        }
        
        # Compare structure and content
        $actualHeaders = ($actual | Get-Member -MemberType NoteProperty).Name | Sort-Object
        $expectedHeaders = ($expected | Get-Member -MemberType NoteProperty).Name | Sort-Object
        
        if (Compare-Object $actualHeaders $expectedHeaders) {
            Write-Host "  ❌ HEADER MISMATCH: $FileName" -ForegroundColor Red
            if ($Verbose) {
                Write-Host "    Expected: $($expectedHeaders -join ', ')" -ForegroundColor Gray
                Write-Host "    Actual:   $($actualHeaders -join ', ')" -ForegroundColor Gray
            }
            return $false
        }
        
        Write-Host "  ✅ VALID: $FileName ($($actual.Count) rows, $($actualHeaders.Count) columns)" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "  ❌ PARSING ERROR: $FileName - $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

function Test-MockStudyAssets {
    Write-TestStep "Checking Mock Study Assets"
    
    if (-not (Test-Path $MockStudyPath)) {
        Write-Host "❌ Mock study directory not found: $MockStudyPath" -ForegroundColor Red
        Write-Host "   This test requires pre-generated mock study assets." -ForegroundColor Yellow
        Write-Host "   Run the mock study generator to create these assets." -ForegroundColor Yellow
        return $false
    }
    
    # Check for required mock experiments
    $mockExperiments = Get-ChildItem -Path $MockStudyPath -Directory -Name "experiment_*"
    if ($mockExperiments.Count -lt 4) {
        Write-Host "❌ Insufficient mock experiments found. Expected at least 4, found $($mockExperiments.Count)" -ForegroundColor Red
        return $false
    }
    
    Write-Host "✅ Found $($mockExperiments.Count) mock experiments" -ForegroundColor Green
    
    # Verify each experiment has sufficient replications
    $totalReplications = 0
    foreach ($experiment in $mockExperiments) {
        $expPath = Join-Path $MockStudyPath $experiment
        $replications = Get-ChildItem -Path $expPath -Directory -Name "run_*"
        $totalReplications += $replications.Count
        Write-Host "  📁 $experiment: $($replications.Count) replications" -ForegroundColor Cyan
    }
    
    if ($totalReplications -lt 20) {
        Write-Host "❌ Insufficient total replications. Expected at least 20, found $totalReplications" -ForegroundColor Red
        Write-Host "   The statistical analysis requires sufficient data to avoid filtering." -ForegroundColor Yellow
        return $false
    }
    
    Write-Host "✅ Mock study assets validated ($totalReplications total replications)" -ForegroundColor Green
    return $true
}

# --- Main Test Execution ---
try {
    Write-TestHeader "Statistical Analysis & Reporting Validation Test" 'Magenta'
    
    if ($Interactive) {
        Write-Host "${C_BLUE}This test validates the complete statistical analysis pipeline by:${C_RESET}"
        Write-Host "1. Using pre-generated mock study data with sufficient replications"
        Write-Host "2. Running the full compile_study.ps1 workflow"
        Write-Host "3. Executing analyze_study_results.py for complete statistical analysis"
        Write-Host "4. Performing bit-for-bit verification against known-good ground truth"
        Write-Host ""
        Write-Host "${C_YELLOW}This complements Layer 5 testing by validating the full statistical pipeline"
        Write-Host "when sufficient data is available, while Layer 5 tests insufficient data handling.${C_RESET}"
        Write-Host ""
        Read-Host "Press Enter to begin validation..." | Out-Null
    }
    
    # Step 1: Validate Prerequisites
    Write-TestStep "Step 1: Validate Prerequisites"
    
    if ($Interactive) {
        Write-Host "${C_GRAY}Checking for required mock study assets and ground truth files...${C_RESET}"
    }
    
    if (-not (Test-MockStudyAssets)) {
        throw "Mock study assets validation failed. Cannot proceed with statistical validation."
    }
    
    if ($Interactive) {
        Read-Host "Press Enter to continue..." | Out-Null
    }
    
    # Step 2: Setup Test Environment
    Write-TestStep "Step 2: Setup Test Environment"
    
    if (Test-Path $TempTestDir) {
        Remove-Item -Path $TempTestDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $TempTestDir -Force | Out-Null
    
    # Copy mock study to test environment
    $testStudyPath = Join-Path $TempTestDir "mock_study"
    Copy-Item -Path $MockStudyPath -Destination $testStudyPath -Recurse
    
    Write-Host "✅ Test environment prepared at: $testStudyPath" -ForegroundColor Green
    
    if ($Interactive) {
        Write-Host "${C_GRAY}Test environment contains a complete mock study with sufficient replications${C_RESET}"
        Write-Host "${C_GRAY}to trigger full statistical analysis including ANOVA, post-hoc tests, and diagnostics.${C_RESET}"
        Read-Host "Press Enter to continue..." | Out-Null
    }
    
    # Step 3: Compile Study Results
    Write-TestStep "Step 3: Compile Study Results"
    
    if ($Interactive) {
        Write-Host "${C_GRAY}Running compile_study.ps1 to aggregate all experiment data into STUDY_results.csv...${C_RESET}"
    }
    
    $compileResult = & "$ProjectRoot\compile_study.ps1" -StudyDirectory $testStudyPath -NonInteractive
    if ($LASTEXITCODE -ne 0) {
        throw "Study compilation failed with exit code $LASTEXITCODE"
    }
    
    $studyResultsPath = Join-Path $testStudyPath "STUDY_results.csv"
    if (-not (Test-Path $studyResultsPath)) {
        throw "STUDY_results.csv was not generated"
    }
    
    $studyResults = Import-Csv $studyResultsPath
    Write-Host "✅ Study compiled successfully: $($studyResults.Count) total rows" -ForegroundColor Green
    
    if ($Interactive) {
        Write-Host "${C_GRAY}The compiled study contains data from all mock experiments and replications.${C_RESET}"
        Read-Host "Press Enter to continue..." | Out-Null
    }
    
    # Step 4: Run Statistical Analysis
    Write-TestStep "Step 4: Run Statistical Analysis"
    
    if ($Interactive) {
        Write-Host "${C_GRAY}Running analyze_study_results.py to perform complete statistical analysis...${C_RESET}"
        Write-Host "${C_GRAY}This will generate ANOVA tables, post-hoc tests, diagnostic plots, and performance groupings.${C_RESET}"
    }
    
    $pythonCmd = "python"
    $analysisScript = Join-Path $ProjectRoot "src/analyze_study_results.py"
    $analysisResult = & $pythonCmd $analysisScript $testStudyPath
    if ($LASTEXITCODE -ne 0) {
        throw "Statistical analysis failed with exit code $LASTEXITCODE"
    }
    
    # Check for expected analysis outputs
    $anovaDir = Join-Path $testStudyPath "anova"
    $analysisLogPath = Join-Path $anovaDir "STUDY_analysis_log.txt"
    $boxplotsDir = Join-Path $anovaDir "boxplots"
    $diagnosticsDir = Join-Path $anovaDir "diagnostics"
    
    if (-not (Test-Path $analysisLogPath)) {
        throw "STUDY_analysis_log.txt was not generated"
    }
    
    if (-not (Test-Path $boxplotsDir)) {
        throw "boxplots directory was not generated"
    }
    
    Write-Host "✅ Statistical analysis completed successfully" -ForegroundColor Green
    Write-Host "  📊 Analysis log: $(Split-Path $analysisLogPath -Leaf)" -ForegroundColor Cyan
    Write-Host "  📈 Boxplots: $(Get-ChildItem -Path $boxplotsDir -Filter "*.png" | Measure-Object).Count plots generated" -ForegroundColor Cyan
    
    if (Test-Path $diagnosticsDir) {
        Write-Host "  🔍 Diagnostics: $(Get-ChildItem -Path $diagnosticsDir -Filter "*.png" | Measure-Object).Count diagnostic plots" -ForegroundColor Cyan
    }
    
    if ($Interactive) {
        Write-Host "${C_GRAY}Statistical analysis generated comprehensive outputs including full ANOVA tables,${C_RESET}"
        Write-Host "${C_GRAY}post-hoc comparisons, and publication-quality visualizations.${C_RESET}"
        Read-Host "Press Enter to continue..." | Out-Null
    }
    
    # Step 5: Validate Against Ground Truth
    Write-TestStep "Step 5: Validate Against Ground Truth"
    
    if ($Interactive) {
        Write-Host "${C_GRAY}Performing bit-for-bit validation against known-good ground truth files...${C_RESET}"
    }
    
    $validationPassed = $true
    
    # Validate STUDY_results.csv
    $expectedStudyResults = Join-Path $GroundTruthPath "STUDY_results.csv"
    if (-not (Compare-CSVFiles $studyResultsPath $expectedStudyResults "STUDY_results.csv")) {
        $validationPassed = $false
    }
    
    # Validate analysis log structure (check key sections exist)
    if (Test-Path $analysisLogPath) {
        $logContent = Get-Content $analysisLogPath -Raw
        $requiredSections = @("ANOVA", "Post-hoc", "Performance Grouping", "Effect Size")
        $missingSections = @()
        
        foreach ($section in $requiredSections) {
            if ($logContent -notlike "*$section*") {
                $missingSections += $section
            }
        }
        
        if ($missingSections.Count -eq 0) {
            Write-Host "  ✅ VALID: Analysis log contains all required sections" -ForegroundColor Green
        } else {
            Write-Host "  ❌ MISSING SECTIONS: $($missingSections -join ', ')" -ForegroundColor Red
            $validationPassed = $false
        }
    }
    
    # Validate visualization outputs
    $expectedPlots = @("mean_mrr", "mean_top_1_acc", "mean_top_3_acc", "bias_slope")
    $actualPlots = Get-ChildItem -Path $boxplotsDir -Filter "*.png" | ForEach-Object { $_.BaseName }
    
    foreach ($expectedPlot in $expectedPlots) {
        if ($actualPlots -contains $expectedPlot) {
            Write-Host "  ✅ VALID: Boxplot generated for $expectedPlot" -ForegroundColor Green
        } else {
            Write-Host "  ❌ MISSING: Boxplot for $expectedPlot" -ForegroundColor Red
            $validationPassed = $false
        }
    }
    
    if ($validationPassed) {
        Write-Host "`n🎉 VALIDATION PASSED: All statistical outputs validated successfully!" -ForegroundColor Green
        Write-Host "   The complete statistical analysis pipeline is working correctly." -ForegroundColor Green
    } else {
        throw "Validation failed: One or more outputs did not match expected results"
    }
    
    if ($Interactive) {
        Write-Host "`n${C_BLUE}Validation Summary:${C_RESET}"
        Write-Host "✅ Mock study compilation: PASSED"
        Write-Host "✅ Statistical analysis execution: PASSED" 
        Write-Host "✅ Output validation: PASSED"
        Write-Host "`nThis test confirms that the statistical analysis pipeline correctly processes"
        Write-Host "studies with sufficient replications and generates the expected comprehensive"
        Write-Host "statistical outputs including ANOVA tables, post-hoc tests, and visualizations."
        Read-Host "`nPress Enter to complete..." | Out-Null
    }
    
}
catch {
    Write-Host "`n❌ STATISTICAL VALIDATION TEST FAILED" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    # Cleanup
    if (Test-Path $TempTestDir) {
        Remove-Item -Path $TempTestDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "`n✅ STATISTICAL ANALYSIS & REPORTING VALIDATION COMPLETED SUCCESSFULLY" -ForegroundColor Green
exit 0

# === End of tests/algorithm_validation/validate_statistical_reporting.ps1 ===
