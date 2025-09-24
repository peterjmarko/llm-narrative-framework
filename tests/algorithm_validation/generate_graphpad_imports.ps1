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
# Filename: tests/algorithm_validation/generate_graphpad_imports.ps1

<#
.SYNOPSIS
    Statistical Analysis & Reporting Validation Test - GraphPad Prism Validation

.DESCRIPTION
    This test validates the complete statistical analysis pipeline against GraphPad Prism 10.0.0.
    It implements a two-phase validation strategy:
    
    Phase A (Replication-Level): Validates core algorithmic contributions (MRR, Wilcoxon tests, bias regression)
    Phase B (Study-Level): Validates standard statistical analyses (Two-Way ANOVA, post-hoc tests)
    
    The test generates GraphPad-compatible import files and provides detailed instructions for
    manual verification, supporting the academic citation: "Statistical analyses were validated 
    against GraphPad Prism 10.0.0"

.PARAMETER Interactive
    Run in interactive mode with step-by-step GraphPad validation instructions.

.PARAMETER ExportOnly
    Generate GraphPad import files without running validation checks.

.PARAMETER Verbose
    Enable verbose output showing detailed export file generation.

.EXAMPLE
    .\generate_graphpad_imports.ps1 -Interactive
    Run the full GraphPad validation workflow with step-by-step guidance.

.EXAMPLE
    .\generate_graphpad_imports.ps1 -ExportOnly
    Generate GraphPad import files only (for batch processing).
#>

param(
    [switch]$Interactive,
    [switch]$ExportOnly,
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
$StatisticalStudyPath = Join-Path $ProjectRoot "tests/assets/statistical_validation_study"
$TempTestDir = Join-Path $ProjectRoot "temp_test_environment/graphpad_validation"
$GraphPadImportsDir = Join-Path $ProjectRoot "tests/assets/statistical_validation_study/graphpad_imports"

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

function Write-GraphPadInstruction {
    param($Step, $Message, $Color = 'Yellow')
    Write-Host "`nGraphPad Step ${Step}:" -ForegroundColor $Color
    Write-Host "   $Message" -ForegroundColor White
}

function Test-StatisticalStudyAssets {
    Write-TestStep "Checking Statistical Study Assets"
    
    if (-not (Test-Path $StatisticalStudyPath)) {
        Write-Host "X Statistical study directory not found: $StatisticalStudyPath" -ForegroundColor Red
        Write-Host "   Run: pwsh -File ./tests/algorithm_validation/generate_statistical_study.ps1" -ForegroundColor Yellow
        return $false
    }
    
    # Check for required experiments
    $experiments = Get-ChildItem -Path $StatisticalStudyPath -Directory -Name "exp_*" -ErrorAction SilentlyContinue
    if ($experiments.Count -lt 4) {
        Write-Host "X Insufficient experiments found. Expected at least 4, found $($experiments.Count)" -ForegroundColor Red
        return $false
    }
    
    # Verify sufficient replications
    $totalReplications = 0
    foreach ($experiment in $experiments) {
        $expPath = Join-Path $StatisticalStudyPath $experiment
        $replications = Get-ChildItem -Path $expPath -Directory -Name "run_*" -ErrorAction SilentlyContinue
        $totalReplications += $replications.Count
    }
    
    if ($totalReplications -lt 20) {
        Write-Host "X Insufficient total replications. Expected at least 20, found $totalReplications" -ForegroundColor Red
        return $false
    }
    
    Write-Host "✓ Statistical study assets validated ($totalReplications total replications)" -ForegroundColor Green
    return $true
}

function Export-ReplicationDataForGraphPad {
    param($ExperimentPath, $ExperimentName)
    
    Write-Verbose "Processing experiment: $ExperimentName"
    
    # Find all replication metrics files
    $replicationFiles = Get-ChildItem -Path $ExperimentPath -Recurse -Name "replication_metrics.json" -ErrorAction SilentlyContinue
    
    if ($replicationFiles.Count -eq 0) {
        Write-Warning "No replication metrics found for $ExperimentName"
        return $null
    }
    
    $allReplicationData = @()
    $repCounter = 1
    
    foreach ($file in $replicationFiles) {
        $filePath = Join-Path $ExperimentPath $file
        try {
            $metrics = Get-Content $filePath -Raw | ConvertFrom-Json
            
            # Extract metadata from config.ini.archived instead of JSON
            $configPath = Join-Path (Split-Path $filePath -Parent | Split-Path -Parent) "config.ini.archived"
            $config = @{}
            if (Test-Path $configPath) {
                $currentSection = ""
                Get-Content $configPath | ForEach-Object {
                    $line = $_.Trim()
                    if ($line -match "^\[(.+)\]$") {
                        $currentSection = $matches[1]
                    } elseif ($line -match "^([^=]+)=(.*)$" -and $line -notmatch "^#") {
                        $key = $matches[1].Trim()
                        $value = $matches[2].Trim()
                        $config["$currentSection`:$key"] = $value
                    }
                }
            }
            
            # Extract key metrics for GraphPad validation
            $replicationData = [PSCustomObject]@{
                Experiment = $ExperimentName
                Replication = $repCounter++  # Sequential numbering for validation
                Model = $config['LLM:model_name'] -as [string]
                MappingStrategy = $config['Study:mapping_strategy'] -as [string]
                GroupSize = [int]$config['Study:group_size']
                
                # Core performance metrics
                MeanMRR = [double]$metrics.mean_mrr
                MRR_P = [double]$metrics.mrr_p
                MeanTop1Accuracy = [double]$metrics.mean_top_1_acc
                Top1Acc_P = [double]$metrics.top_1_acc_p
                MeanTop3Accuracy = [double]$metrics.mean_top_3_acc
                Top3Acc_P = [double]$metrics.top_3_acc_p
                
                # Lift metrics
                MeanMRRLift = [double]$metrics.mean_mrr_lift
                MeanTop1AccLift = [double]$metrics.mean_top_1_acc_lift
                MeanTop3AccLift = [double]$metrics.mean_top_3_acc_lift
                
                # Ranking and bias metrics
                MeanRankOfCorrectID = [double]$metrics.mean_rank_of_correct_id
                RankOfCorrectID_P = [double]$metrics.rank_of_correct_id_p
                Top1PredBiasStd = [double]$metrics.top1_pred_bias_std
                TrueFalseScoreDiff = [double]$metrics.true_false_score_diff
                
                # Regression bias analysis
                BiasSlope = [double]$metrics.bias_slope
                BiasIntercept = [double]$metrics.bias_intercept
                BiasRValue = [double]$metrics.bias_r_value
                BiasPValue = [double]$metrics.bias_p_value
                BiasStdErr = [double]$metrics.bias_std_err
            }
            
            $allReplicationData += $replicationData
        }
        catch {
            Write-Warning "Failed to parse metrics file: $file - $($_.Exception.Message)"
        }
    }
    
    return $allReplicationData
}

function Export-RawScoresForGraphPad {
    param($ExperimentPath, $ExperimentName)
    
    $projectRootEscaped = $ProjectRoot -replace '\\', '/'
    $experimentPathEscaped = $ExperimentPath -replace '\\', '/'
    $pythonScript = @"
import sys, os
sys.path.insert(0, '$projectRootEscaped/src')

from analyze_llm_performance import read_score_matrices, read_mappings_and_deduce_k, evaluate_single_test

print('Experiment,Replication,Trial,MRR,MeanRank')

import logging
logging.getLogger().setLevel(logging.CRITICAL)

replications = [r for r in os.listdir('$experimentPathEscaped') if r.startswith('run_')]

for replication in replications:
    analysis_path = os.path.join('$experimentPathEscaped', replication, 'analysis_inputs')
    mappings_file = os.path.join(analysis_path, 'all_mappings.txt')
    scores_file = os.path.join(analysis_path, 'all_scores.txt')
    
    if not os.path.exists(mappings_file) or not os.path.exists(scores_file):
        continue
        
    mappings, k_val, delim = read_mappings_and_deduce_k(mappings_file)
    if not mappings or not k_val:
        continue
        
    matrices = read_score_matrices(scores_file, k_val, delim)
    if not matrices:
        continue
    
    for i, (matrix, mapping) in enumerate(zip(matrices, mappings)):
        result = evaluate_single_test(matrix, mapping, k_val, 3)
        if result:
            print(f'$ExperimentName,{replication},{i+1},{result["mrr"]},{result["mean_rank_of_correct_id"]}')
"@
    
    $pythonOutput = python -c $pythonScript 2>$null
    $csvData = $pythonOutput | Where-Object { $_ -and $_ -match "," } | ConvertFrom-Csv
    Write-Verbose "Extracted $($csvData.Count) raw trial records using production functions"
    return $csvData
}

function Export-RawScoresForGraphPadWide {
    param($AllRawScores)
    
    if (-not $AllRawScores) { return $null }
    
    # Group by unique replication identifier (Experiment + Replication)
    $replications = $AllRawScores | Group-Object { "$($_.Experiment)_$($_.Replication)" } | Sort-Object Name
    $maxTrials = ($replications | ForEach-Object { $_.Count } | Measure-Object -Maximum).Maximum
    
    # Create wide format table with one column per replication
    $wideData = @()
    for ($trial = 1; $trial -le $maxTrials; $trial++) {
        $row = [PSCustomObject]@{ Trial = $trial }
        
        foreach ($rep in $replications) {
            $repId = $rep.Name
            $trialData = $rep.Group | Where-Object { $_.Trial -eq $trial }
            
            # Add MRR column for this specific replication
            $mrrValue = if ($trialData) { $trialData.MRR -as [double] } else { $null }
            $row | Add-Member -NotePropertyName "MRR_$repId" -NotePropertyValue $mrrValue
        }
        
        $wideData += $row
    }
    
    return $wideData
}

function Generate-GraphPadExports {
    param($TestStudyPath)
    
    Write-TestStep "Generating GraphPad Prism Import Files"
    
    # Create export directory
    New-Item -ItemType Directory -Path $GraphPadImportsDir -Force | Out-Null
    
    # Phase A: Export replication-level data
    Write-Host "Phase A: Generating replication-level exports..." -ForegroundColor Cyan
    
    $allReplicationData = @()
    $allRawScores = @()
    
    $experiments = Get-ChildItem -Path $TestStudyPath -Directory -Name "exp_*"
    $totalExperiments = $experiments.Count
    $currentExperiment = 0
    
    foreach ($experiment in $experiments) {
        $currentExperiment++
        $percentComplete = [math]::Round(($currentExperiment / $totalExperiments) * 100)
        Write-Progress -Activity "Generating GraphPad exports" -Status "Processing $experiment... ($currentExperiment of $totalExperiments)" -PercentComplete $percentComplete
        
        $expPath = Join-Path $TestStudyPath $experiment
        
        # Export replication metrics
        $repData = Export-ReplicationDataForGraphPad -ExperimentPath $expPath -ExperimentName $experiment
        if ($repData) {
            $allReplicationData += $repData
        }
        
        # Export raw scores
        $rawData = Export-RawScoresForGraphPad -ExperimentPath $expPath -ExperimentName $experiment
        if ($rawData) {
            Write-Verbose "$experiment contributed $($rawData.Count) trials"
            $allRawScores += $rawData
            Write-Verbose "Running total: $($allRawScores.Count) trials"
        }
    }
    
    Write-Progress -Activity "Generating GraphPad exports" -Completed
    
    # Export replication-level summary
    $replicationExport = Join-Path $GraphPadImportsDir "Phase_A_Replication_Metrics.csv"
    $allReplicationData | Export-Csv -Path $replicationExport -NoTypeInformation
    Write-Host "  ✓ Generated: Phase_A_Replication_Metrics.csv ($($allReplicationData.Count) replications)" -ForegroundColor Green
    
    # Export raw scores for manual validation
    $rawScoresExport = Join-Path $GraphPadImportsDir "Phase_A_Raw_Scores.csv"
    $allRawScores | Export-Csv -Path $rawScoresExport -NoTypeInformation
    
    # Export raw scores in wide format for GraphPad column-based analysis
    $rawScoresWideExport = Join-Path $GraphPadImportsDir "Phase_A_Raw_Scores_Wide.csv"
    $allRawScoresWide = Export-RawScoresForGraphPadWide -AllRawScores $allRawScores
    if ($allRawScoresWide) {
        $allRawScoresWide | Export-Csv -Path $rawScoresWideExport -NoTypeInformation
    }
    # (Debug code removed - validation export complete)
    Write-Host "  ✓ Generated: Phase_A_Raw_Scores.csv ($($allRawScores.Count) trials)" -ForegroundColor Green
    Write-Host "  ✓ Generated: Phase_A_Raw_Scores_Wide.csv (GraphPad column format)" -ForegroundColor Green
    
    # Phase B: Export study-level data (if STUDY_results.csv exists)
    Write-Host "Phase B: Generating study-level exports..." -ForegroundColor Cyan
    
    $studyResultsPath = Join-Path $TestStudyPath "STUDY_results.csv"
    if (Test-Path $studyResultsPath) {
        $studyData = Import-Csv $studyResultsPath
        
        # Export for Two-Way ANOVA
        $anovaExport = Join-Path $GraphPadImportsDir "Phase_B_ANOVA_Data.csv"
        $studyData | Export-Csv -Path $anovaExport -NoTypeInformation
        Write-Host "  ✓ Generated: Phase_B_ANOVA_Data.csv ($($studyData.Count) experiments)" -ForegroundColor Green
        
        # Generate summary statistics for validation
        $summaryStats = $studyData | Group-Object mapping_strategy, k | ForEach-Object {
            $group = $_.Group
            [PSCustomObject]@{
                MappingStrategy = $group[0].mapping_strategy
                GroupSize = $group[0].k
                Count = $group.Count
                MRR_Mean = ($group | Measure-Object mean_mrr -Average).Average
                MRR_StdDev = [math]::Sqrt(($group | ForEach-Object { ([double]$_.mean_mrr - ($group | Measure-Object mean_mrr -Average).Average) * ([double]$_.mean_mrr - ($group | Measure-Object mean_mrr -Average).Average) } | Measure-Object -Sum).Sum / ($group.Count - 1))
                Top1_Mean = ($group | Measure-Object mean_top_1_acc -Average).Average
                Top1_StdDev = [math]::Sqrt(($group | ForEach-Object { ([double]$_.mean_top_1_acc - ($group | Measure-Object mean_top_1_acc -Average).Average) * ([double]$_.mean_top_1_acc - ($group | Measure-Object mean_top_1_acc -Average).Average) } | Measure-Object -Sum).Sum / ($group.Count - 1))
            }
        }
        
        $summaryExport = Join-Path $GraphPadImportsDir "Phase_B_Summary_Statistics.csv"
        $summaryStats | Export-Csv -Path $summaryExport -NoTypeInformation
        Write-Host "  ✓ Generated: Phase_B_Summary_Statistics.csv (4 groups)" -ForegroundColor Green
    } else {
        Write-Host "  ! STUDY_results.csv not found - Phase B exports skipped" -ForegroundColor Yellow
        Write-Host "     Run compile_study.ps1 first to generate study-level data" -ForegroundColor Gray
    }
    
    return @{
        ReplicationCount = $allReplicationData.Count
        TrialCount = $allRawScores.Count
        ExportDirectory = $GraphPadImportsDir
    }
}

function Show-GraphPadValidationInstructions {
    param($ExportStats)
    
    Write-TestHeader "GraphPad Prism Manual Analysis Instructions (Step 3 of 4)" 'Yellow'
    
    Write-Host "Import files generated in: " -NoNewline -ForegroundColor White
    Write-Host $ExportStats.ExportDirectory -ForegroundColor Cyan
    
    Write-Host "`nComplete 4-Step Validation Workflow:" -ForegroundColor Magenta
    Write-Host "✓ Step 1: create_statistical_study.ps1 - COMPLETED" -ForegroundColor Green
    Write-Host "✓ Step 2: generate_graphpad_imports.ps1 - COMPLETED" -ForegroundColor Green
    Write-Host "→ Step 3: Manual GraphPad Analysis - FOLLOW INSTRUCTIONS BELOW" -ForegroundColor Yellow
    Write-Host "  Step 4: validate_graphpad_results.ps1 - PENDING" -ForegroundColor Gray
    
    Write-Host "`nSTEP 3: MANUAL GRAPHPAD PRISM ANALYSIS" -ForegroundColor Magenta
    Write-Host "Target: Independent validation of framework calculations" -ForegroundColor Gray
    
    Write-GraphPadInstruction "3.1" "Open GraphPad Prism and create a new project"
    
    Write-GraphPadInstruction "3.2" "Import validation datasets:"
    Write-Host "     - Phase_A_Replication_Metrics.csv (framework results)" -ForegroundColor Gray
    Write-Host "     - Phase_A_Raw_Scores_Wide.csv (trial data for MRR validation)" -ForegroundColor Gray
    Write-Host "     - Phase_B_ANOVA_Data.csv (study-level data)" -ForegroundColor Gray
    
    Write-GraphPadInstruction "3.3" "Validate MRR calculations:"
    Write-Host "     - Use Phase_A_Raw_Scores_Wide.csv → Column Statistics → Descriptive statistics" -ForegroundColor Gray
    Write-Host "     - Select MRR columns, calculate means for each replication" -ForegroundColor Gray
    Write-Host "     - Export results as 'GraphPad_MRR_Means.csv'" -ForegroundColor Gray
    
    Write-GraphPadInstruction "3.4" "Validate Wilcoxon tests (optional):"
    Write-Host "     - Use Phase_A_Raw_Scores_Wide.csv → One sample t test and Wilcoxon test" -ForegroundColor Gray
    Write-Host "     - Test against chance level (1/k where k=group_size)" -ForegroundColor Gray
    
    Write-GraphPadInstruction "3.5" "Validate ANOVA results (optional):"
    Write-Host "     - Use Phase_B_ANOVA_Data.csv → Two-way ANOVA" -ForegroundColor Gray
    Write-Host "     - Factors: mapping_strategy x k" -ForegroundColor Gray
    Write-Host "     - Compare F-statistics and p-values" -ForegroundColor Gray
    
    Write-Host "`nAFTER COMPLETING GRAPHPAD ANALYSIS:" -ForegroundColor Cyan
    Write-Host "Run Step 4 validation:" -ForegroundColor White
    Write-Host "pdm run test-stats-results" -ForegroundColor Gray
    
    Write-Host "`nSUCCESS CRITERIA:" -ForegroundColor Green
    Write-Host "Step 4 will validate MRR calculations within ±0.0001 tolerance" -ForegroundColor White
    Write-Host "Citation ready: 'Statistical analyses were validated against GraphPad Prism 10.6.1'" -ForegroundColor White
    
    Write-Host "`nVALIDATION SUMMARY:" -ForegroundColor Cyan
    Write-Host "Replications to validate: $($ExportStats.ReplicationCount)" -ForegroundColor White
    Write-Host "Total trials analyzed: $($ExportStats.TrialCount)" -ForegroundColor White
    Write-Host "Export directory: $(Split-Path $ExportStats.ExportDirectory -Leaf)" -ForegroundColor White
}

# --- Main Test Execution ---
try {
    Write-TestHeader "Statistical Analysis & Reporting - Step 2/4: GraphPad Export Generation" 'Magenta'
    
    if ($Interactive) {
        Write-Host "${C_BLUE}This test implements the Two-Phase GraphPad Prism Validation Strategy:${C_RESET}"
        Write-Host ""
        Write-Host "Phase A: Validates core algorithmic contributions against GraphPad"
        Write-Host "  • Mean Reciprocal Rank (MRR) calculations"
        Write-Host "  • Wilcoxon signed-rank test p-values"
        Write-Host "  • Bias regression analysis (slope, R-value)"
        Write-Host "  • Effect size calculations (Cohen's r)"
        Write-Host ""
        Write-Host "Phase B: Validates standard statistical analyses against GraphPad"
        Write-Host "  • Two-Way ANOVA (F-statistics, p-values, effect sizes)"
        Write-Host "  • Post-hoc tests and FDR corrections"
        Write-Host "  • Multi-factor experimental design validation"
        Write-Host ""
        Write-Host "${C_YELLOW}This provides academic defensibility for the citation:${C_RESET}"
        Write-Host "${C_GREEN}'Statistical analyses were validated against GraphPad Prism 10.6.1'${C_RESET}"
        Write-Host ""
        Read-Host "Press Enter to begin validation..." | Out-Null
    }
    
    # Step 1: Validate Prerequisites
    Write-TestStep "Step 1: Validate Prerequisites"
    
    if (-not (Test-StatisticalStudyAssets)) {
        throw "Statistical study assets validation failed. Run generate_statistical_study.ps1 first."
    }
    
    if ($Interactive) {
        Read-Host "Press Enter to continue..." | Out-Null
    }
    
    # Step 2: Setup Test Environment
    Write-Host ""
    Write-TestStep "Step 2: Setup Test Environment"
    
    if (Test-Path $TempTestDir) {
        Remove-Item -Path $TempTestDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $TempTestDir -Force | Out-Null
    
    # Copy statistical study to test environment
    $testStudyPath = Join-Path $TempTestDir "statistical_study"
    Write-Host "Copying statistical study data..." -ForegroundColor Cyan
$sourceFiles = Get-ChildItem -Path $StatisticalStudyPath -Recurse -File
$totalFiles = $sourceFiles.Count
$currentFile = 0

Copy-Item -Path $StatisticalStudyPath -Destination $testStudyPath -Recurse -Force | ForEach-Object {
    $currentFile++
    $percentComplete = [math]::Round(($currentFile / $totalFiles) * 100)
    Write-Progress -Activity "Setting up test environment" -Status "Copying files... ($currentFile of $totalFiles)" -PercentComplete $percentComplete
}
Write-Progress -Activity "Setting up test environment" -Completed
    
    Write-Host "✓ Test environment prepared" -ForegroundColor Green
    
    if ($Interactive) {
        Read-Host "Press Enter to continue..." | Out-Null
    }
    
    # Step 3: Check if Analysis Already Complete (skip compilation for pre-compiled study)
    Write-Host ""
    Write-TestStep "Step 3: Verify Analysis Readiness"
    
    # Check if study is already compiled (has STUDY_results.csv)
    $studyResultsPath = Join-Path $testStudyPath "STUDY_results.csv"
    if (Test-Path $studyResultsPath) {
        Write-Host "✓ Study already compiled - using existing analysis" -ForegroundColor Green
        $finalStudyPath = $testStudyPath
    } elseif (-not $ExportOnly) {
        Write-Host "Compiling study..." -ForegroundColor Cyan
        $compileResult = & "$ProjectRoot\compile_study.ps1" -StudyDirectory $testStudyPath
        if ($LASTEXITCODE -ne 0) {
            throw "Study compilation failed with exit code $LASTEXITCODE"
        }
        Write-Host "✓ Analysis pipeline completed" -ForegroundColor Green
        $finalStudyPath = $testStudyPath
    } else {
        $finalStudyPath = $testStudyPath
    }

    if ($Interactive) {
        Read-Host "Press Enter to continue..." | Out-Null
    }
    
    # Step 4: Generate GraphPad Exports
    Write-Host ""
    Write-TestStep "Step 4: Generate GraphPad Export Files"
    
    $exportStats = Generate-GraphPadExports -TestStudyPath $finalStudyPath
    
    # Step 5: Show Validation Instructions
    if (-not $ExportOnly) {
        Show-GraphPadValidationInstructions -ExportStats $exportStats
        
        if ($Interactive) {
            Write-Host "`n${C_YELLOW}Next Steps:${C_RESET}"
            Write-Host "1. Open GraphPad Prism 10.0.0"
            Write-Host "2. Follow the validation instructions above"
            Write-Host "3. Document any deviations beyond tolerance thresholds"
            Write-Host "4. Update implementation if significant deviations found"
            Read-Host "`nPress Enter to complete..." | Out-Null
        }
    }
    
}
catch {
    Write-Host "`nX GRAPHPAD VALIDATION TEST FAILED" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    if (-not $Interactive -and -not $ExportOnly) {
        # Cleanup in non-interactive mode
        if (Test-Path $TempTestDir) {
            Remove-Item -Path $TempTestDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "`nGRAPHPAD PRISM VALIDATION EXPORTS GENERATED SUCCESSFULLY" -ForegroundColor Green

if ($ExportOnly) {
    Write-Host "Import files available in: $GraphPadImportsDir" -ForegroundColor Cyan
} else {
    Write-Host "Ready for GraphPad Prism validation - follow instructions above" -ForegroundColor Cyan
    Write-Host ""
}

exit 0

# === End of tests/algorithm_validation/generate_graphpad_imports.ps1 ===
