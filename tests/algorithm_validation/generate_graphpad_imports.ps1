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
    
    Phase A (Replication-Level): Validates core algorithmic contributions
    - Mean Reciprocal Rank (MRR) calculations with K-specific validation
    - Top-1 accuracy calculations with K-specific validation
    - Top-3 accuracy calculations with K-specific validation 
    - Wilcoxon signed-rank test p-values for all metrics
    - Bias regression analysis (slope, R-value)
    
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
    Run the GraphPad validation workflow with step-by-step guidance.

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
# GraphPadExportsDir will be created during test setup, not in path configuration

# --- Filename Constants ---
$RAW_SCORES_FILE = "Phase_A_Raw_Scores.csv"
$MRR_K4_FILE = "Phase_A_MRR_K4.csv"
$MRR_K10_FILE = "Phase_A_MRR_K10.csv"
$TOP1_K4_FILE = "Phase_A_Top1_K4.csv"
$TOP1_K10_FILE = "Phase_A_Top1_K10.csv"
$TOP3_K4_FILE = "Phase_A_Top3_K4.csv"
$TOP3_K10_FILE = "Phase_A_Top3_K10.csv"
$ANOVA_MRR_FILE = "Phase_B_ANOVA_MRR.csv"
$ANOVA_TOP1_FILE = "Phase_B_ANOVA_Top1.csv"
$ANOVA_TOP3_FILE = "Phase_B_ANOVA_Top3.csv"
$BIAS_REGRESSION_MRR_FILE = "Phase_B_Bias_Regression_MRR.csv"
$BIAS_REGRESSION_TOP1_FILE = "Phase_B_Bias_Regression_Top1.csv"
$BIAS_REGRESSION_TOP3_FILE = "Phase_B_Bias_Regression_Top3.csv"
$BIAS_REGRESSION_CORRECT_MRR_FILE = "Phase_B_Bias_Regression_Correct_MRR.csv"
$BIAS_REGRESSION_RANDOM_MRR_FILE = "Phase_B_Bias_Regression_Random_MRR.csv"

# --- Helper Functions ---
function Write-TestHeader { 
    param($Message, $Color = 'Cyan') 
    $line = "=" * 85
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
        
        $repCounter = 1
        foreach ($rep in $replications) {
            $trialData = $rep.Group | Where-Object { $_.Trial -eq $trial }
            
            # Add MRR column for this specific replication with a sequential name
            $mrrValue = if ($trialData) { $trialData.MRR -as [double] } else { $null }
            $row | Add-Member -NotePropertyName "MRR_$($repCounter.ToString('00'))" -NotePropertyValue $mrrValue
            $repCounter++
        }
        
        $wideData += $row
    }
    
    return $wideData
}

# =============================================================================
# K-SPECIFIC ACCURACY EXPORT GENERATION
# =============================================================================

function Generate-KSpecificAccuracyExports {
    param($AllReplicationData)
    
    Write-Host "Phase A: Generating K-specific accuracy validation exports..." -ForegroundColor Cyan
    
    # Filter data by group size
    $k4Data = $AllReplicationData | Where-Object { $_.GroupSize -eq 4 }
    $k10Data = $AllReplicationData | Where-Object { $_.GroupSize -eq 10 }
    
    $exportStats = @{}
    
    # =============================================================================
    # MRR K-SPECIFIC EXPORTS
    # =============================================================================
    
    $k4MRRData = $k4Data | Select-Object @{N='MRR';E={$_.MeanMRR}}, @{N='Chance';E={0.5208}}, @{N='K';E={$_.GroupSize}}, @{N='Replication';E={$_.Replication}}, @{N='Experiment';E={$_.Experiment}}
    $k10MRRData = $k10Data | Select-Object @{N='MRR';E={$_.MeanMRR}}, @{N='Chance';E={0.2929}}, @{N='K';E={$_.GroupSize}}, @{N='Replication';E={$_.Replication}}, @{N='Experiment';E={$_.Experiment}}

    $k4MRRExport = Join-Path $GraphPadImportsDir $MRR_K4_FILE
    $k10MRRExport = Join-Path $GraphPadImportsDir $MRR_K10_FILE
    
    $k4MRRData | Export-Csv -Path $k4MRRExport -NoTypeInformation
    $k10MRRData | Export-Csv -Path $k10MRRExport -NoTypeInformation

    $exportStats.K4_MRR_Count = $k4MRRData.Count
    $exportStats.K10_MRR_Count = $k10MRRData.Count

    Write-Host "  Generated: Phase_A_MRR_K4.csv ($($k4MRRData.Count) replications, chance = 0.5208)"
    Write-Host "  Generated: Phase_A_MRR_K10.csv ($($k10MRRData.Count) replications, chance = 0.2929)"
    
    # =============================================================================
    # TOP-1 ACCURACY K-SPECIFIC EXPORTS
    # =============================================================================
    
    $k4Top1Data = $k4Data | Select-Object @{N='Top1Accuracy';E={$_.MeanTop1Accuracy}}, @{N='Chance';E={0.25}}, @{N='K';E={$_.GroupSize}}, @{N='Replication';E={$_.Replication}}, @{N='Experiment';E={$_.Experiment}}
    $k10Top1Data = $k10Data | Select-Object @{N='Top1Accuracy';E={$_.MeanTop1Accuracy}}, @{N='Chance';E={0.1}}, @{N='K';E={$_.GroupSize}}, @{N='Replication';E={$_.Replication}}, @{N='Experiment';E={$_.Experiment}}

    $k4Top1Export = Join-Path $GraphPadImportsDir $TOP1_K4_FILE
    $k10Top1Export = Join-Path $GraphPadImportsDir $TOP1_K10_FILE
    
    $k4Top1Data | Export-Csv -Path $k4Top1Export -NoTypeInformation
    $k10Top1Data | Export-Csv -Path $k10Top1Export -NoTypeInformation

    $exportStats.K4_Top1_Count = $k4Top1Data.Count
    $exportStats.K10_Top1_Count = $k10Top1Data.Count

    Write-Host "  Generated: Phase_A_Top1_K4.csv ($($k4Top1Data.Count) replications, chance = 0.25)"
    Write-Host "  Generated: Phase_A_Top1_K10.csv ($($k10Top1Data.Count) replications, chance = 0.1)"
    
    # =============================================================================
    # TOP-3 ACCURACY K-SPECIFIC EXPORTS  
    # =============================================================================
    
    # Top-3 accuracy chance calculations: min(3, k) / k
    # K=4: min(3,4)/4 = 3/4 = 0.75
    # K=10: min(3,10)/10 = 3/10 = 0.3
    
    $k4Top3Data = $k4Data | Select-Object @{N='Top3Accuracy';E={$_.MeanTop3Accuracy}}, @{N='Chance';E={0.75}}, @{N='K';E={$_.GroupSize}}, @{N='Replication';E={$_.Replication}}, @{N='Experiment';E={$_.Experiment}}
    $k10Top3Data = $k10Data | Select-Object @{N='Top3Accuracy';E={$_.MeanTop3Accuracy}}, @{N='Chance';E={0.3}}, @{N='K';E={$_.GroupSize}}, @{N='Replication';E={$_.Replication}}, @{N='Experiment';E={$_.Experiment}}

    $k4Top3Export = Join-Path $GraphPadImportsDir $TOP3_K4_FILE
    $k10Top3Export = Join-Path $GraphPadImportsDir $TOP3_K10_FILE
    
    $k4Top3Data | Export-Csv -Path $k4Top3Export -NoTypeInformation
    $k10Top3Data | Export-Csv -Path $k10Top3Export -NoTypeInformation

    $exportStats.K4_Top3_Count = $k4Top3Data.Count
    $exportStats.K10_Top3_Count = $k10Top3Data.Count

    Write-Host "  Generated: Phase_A_Top3_K4.csv ($($k4Top3Data.Count) replications, chance = 0.75)"
    Write-Host "  Generated: Phase_A_Top3_K10.csv ($($k10Top3Data.Count) replications, chance = 0.3)"
    
    Write-Host "✓ K-specific accuracy validation exports completed`n" -ForegroundColor Green
    
    return $exportStats
}

# =============================================================================
# PHASE 2: EFFECT SIZE CALCULATIONS
# =============================================================================

function Export-EffectSizeDataForGraphPad {
    param($TestStudyPath)
    
    Write-Host "Phase B: Generating effect size validation exports..." -ForegroundColor Cyan
    
    # Check if study compilation generated ANOVA analysis
    $anovaLogPath = Join-Path $TestStudyPath "anova/STUDY_analysis_log.txt"
    if (-not (Test-Path $anovaLogPath)) {
        Write-Host "  ! ANOVA analysis log not found - effect size validation skipped" -ForegroundColor Yellow
        return $null
    }
    
    # For Phase 2, we'll use the raw study data for effect size verification
    # This allows GraphPad to calculate ANOVA independently
    Write-Host "  ✓ ANOVA analysis found - preparing effect size validation`n" -ForegroundColor Green
    
    return @{
        EffectSizeCount = "Available"
        ExportPath = "Will be generated from raw data"
    }
}

function Generate-ANOVAExports {
    param($TestStudyPath)
    
    Write-Host "Phase B: Generating ANOVA exports with effect size validation..." -ForegroundColor Cyan
    
    $studyResultsPath = Join-Path $TestStudyPath "STUDY_results.csv"
    if (-not (Test-Path $studyResultsPath)) {
        Write-Host "  ! STUDY_results.csv not found - Phase B exports skipped" -ForegroundColor Yellow
        return $null
    }
    
    $studyData = Import-Csv $studyResultsPath
    
    # Generate standard ANOVA export
    $correctK4Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "correct" -and $_.k -eq 4 }).mean_mrr)
    $correctK10Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "correct" -and $_.k -eq 10 }).mean_mrr)
    $randomK4Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "random" -and $_.k -eq 4 }).mean_mrr)
    $randomK10Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "random" -and $_.k -eq 10 }).mean_mrr)
    
    $numReplicates = [math]::Max([math]::Max($correctK4Values.Count, $correctK10Values.Count), [math]::Max($randomK4Values.Count, $randomK10Values.Count))
    
    # Create standard ANOVA export
    $headerParts = @()
    for ($i = 1; $i -le $numReplicates; $i++) { $headerParts += "K4" }
    for ($i = 1; $i -le $numReplicates; $i++) { $headerParts += "K10" }
    $headerRow = "," + ($headerParts -join ",")
    
    $correctRowParts = @("Correct")
    for ($i = 0; $i -lt $numReplicates; $i++) {
        $correctRowParts += if ($i -lt $correctK4Values.Count) { $correctK4Values[$i] } else { "" }
    }
    for ($i = 0; $i -lt $numReplicates; $i++) {
        $correctRowParts += if ($i -lt $correctK10Values.Count) { $correctK10Values[$i] } else { "" }
    }
    $correctRow = $correctRowParts -join ","
    
    $randomRowParts = @("Random")
    for ($i = 0; $i -lt $numReplicates; $i++) {
        $randomRowParts += if ($i -lt $randomK4Values.Count) { $randomK4Values[$i] } else { "" }
    }
    for ($i = 0; $i -lt $numReplicates; $i++) {
        $randomRowParts += if ($i -lt $randomK10Values.Count) { $randomK10Values[$i] } else { "" }
    }
    $randomRow = $randomRowParts -join ","
    
    $csvContent = @($headerRow, $correctRow, $randomRow)
    
    $anovaExport = Join-Path $GraphPadImportsDir $ANOVA_MRR_FILE
    $csvContent | Out-File -FilePath $anovaExport -Encoding UTF8
    
    Write-Host "  Generated: Phase_B_ANOVA_MRR.csv (GraphPad grouped table format)"
    Write-Host "    - Rows: Correct vs Random (mapping strategy)" -ForegroundColor Gray
    Write-Host "    - Columns: K4 vs K10 (group size) with $numReplicates subcolumns each" -ForegroundColor Gray
    
    # Generate grouped format files for effect size verification
    
    # Top-1 Accuracy ANOVA export (grouped format)
    $correctK4Top1Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "correct" -and $_.k -eq 4 }).mean_top_1_acc)
    $correctK10Top1Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "correct" -and $_.k -eq 10 }).mean_top_1_acc)
    $randomK4Top1Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "random" -and $_.k -eq 4 }).mean_top_1_acc)
    $randomK10Top1Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "random" -and $_.k -eq 10 }).mean_top_1_acc)
    
    # Create Top-1 accuracy grouped format
    $top1HeaderRow = "," + ($headerParts -join ",")
    
    $correctTop1RowParts = @("Correct")
    for ($i = 0; $i -lt $numReplicates; $i++) {
        $correctTop1RowParts += if ($i -lt $correctK4Top1Values.Count) { $correctK4Top1Values[$i] } else { "" }
    }
    for ($i = 0; $i -lt $numReplicates; $i++) {
        $correctTop1RowParts += if ($i -lt $correctK10Top1Values.Count) { $correctK10Top1Values[$i] } else { "" }
    }
    $correctTop1Row = $correctTop1RowParts -join ","
    
    $randomTop1RowParts = @("Random")
    for ($i = 0; $i -lt $numReplicates; $i++) {
        $randomTop1RowParts += if ($i -lt $randomK4Top1Values.Count) { $randomK4Top1Values[$i] } else { "" }
    }
    for ($i = 0; $i -lt $numReplicates; $i++) {
        $randomTop1RowParts += if ($i -lt $randomK10Top1Values.Count) { $randomK10Top1Values[$i] } else { "" }
    }
    $randomTop1Row = $randomTop1RowParts -join ","
    
    $top1CsvContent = @($top1HeaderRow, $correctTop1Row, $randomTop1Row)
    
    $top1AnovaExport = Join-Path $GraphPadImportsDir $ANOVA_TOP1_FILE
    $top1CsvContent | Out-File -FilePath $top1AnovaExport -Encoding UTF8
    
    # Top-3 Accuracy ANOVA export (grouped format)
    $correctK4Top3Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "correct" -and $_.k -eq 4 }).mean_top_3_acc)
    $correctK10Top3Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "correct" -and $_.k -eq 10 }).mean_top_3_acc)
    $randomK4Top3Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "random" -and $_.k -eq 4 }).mean_top_3_acc)
    $randomK10Top3Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "random" -and $_.k -eq 10 }).mean_top_3_acc)
    
    # Create Top-3 accuracy grouped format  
    $top3HeaderRow = "," + ($headerParts -join ",")
    
    $correctTop3RowParts = @("Correct")
    for ($i = 0; $i -lt $numReplicates; $i++) {
        $correctTop3RowParts += if ($i -lt $correctK4Top3Values.Count) { $correctK4Top3Values[$i] } else { "" }
    }
    for ($i = 0; $i -lt $numReplicates; $i++) {
        $correctTop3RowParts += if ($i -lt $correctK10Top3Values.Count) { $correctK10Top3Values[$i] } else { "" }
    }
    $correctTop3Row = $correctTop3RowParts -join ","
    
    $randomTop3RowParts = @("Random")
    for ($i = 0; $i -lt $numReplicates; $i++) {
        $randomTop3RowParts += if ($i -lt $randomK4Top3Values.Count) { $randomK4Top3Values[$i] } else { "" }
    }
    for ($i = 0; $i -lt $numReplicates; $i++) {
        $randomTop3RowParts += if ($i -lt $randomK10Top3Values.Count) { $randomK10Top3Values[$i] } else { "" }
    }
    $randomTop3Row = $randomTop3RowParts -join ","
    
    $top3CsvContent = @($top3HeaderRow, $correctTop3Row, $randomTop3Row)
    
    $top3AnovaExport = Join-Path $GraphPadImportsDir $ANOVA_TOP3_FILE
    $top3CsvContent | Out-File -FilePath $top3AnovaExport -Encoding UTF8
    
    Write-Host "  Generated: Phase_B_ANOVA_Top1.csv (Top-1 accuracy grouped format for effect size verification)"
    Write-Host "  Generated: Phase_B_ANOVA_Top3.csv (Top-3 accuracy grouped format for effect size verification)"
    Write-Host "    - 3 grouped ANOVA files total (MRR, Top-1, Top-3) for effect size validation" -ForegroundColor Gray
    
    Write-Host "✓ ANOVA exports with effect size validation completed`n" -ForegroundColor Green
    
    # Export effect size data from framework analysis
    $effectSizeStats = Export-EffectSizeDataForGraphPad -TestStudyPath $TestStudyPath
    
    return @{
        ANOVADataPoints = $rawAnovaData.Count
        EffectSizeStats = $effectSizeStats
        NumReplicates = $numReplicates
    }
}

# =============================================================================
# BIAS REGRESSION ANALYSIS
# =============================================================================

function Export-BiasRegressionDataForGraphPad {
    param($TestStudyPath)
    
    Write-Host "Phase B: Generating bias regression validation exports..." -ForegroundColor Cyan
    
    $allBiasData = @()
    $experiments = Get-ChildItem -Path $TestStudyPath -Directory -Name "exp_*"
    $totalExperiments = $experiments.Count
    $currentExp = 0
    
    foreach ($experiment in $experiments) {
        $currentExp++
        $expPath = Join-Path $TestStudyPath $experiment
        $replications = Get-ChildItem -Path $expPath -Directory -Name "run_*"
        
        Write-Host "  Processing $experiment ($currentExp/$totalExperiments) with $($replications.Count) replications..." -ForegroundColor Blue
        
        foreach ($replication in $replications) {
            $repPath = Join-Path $expPath $replication
            
            # Read the raw trial data to extract trial-by-trial performance
            $trialData = Export-TrialByTrialPerformance -ReplicationPath $repPath -ExperimentName $experiment -ReplicationName $replication
            if ($trialData) {
                $allBiasData += $trialData
            }
        }
    }
    
    if ($allBiasData.Count -eq 0) {
        Write-Host "  ! No trial-by-trial data found for bias regression analysis" -ForegroundColor Yellow
        return $null
    }
    
    # Create sequential trial numbering for regression analysis
    $trialSequence = 1
    $allBiasDataWithSeq = @()
    foreach ($record in $allBiasData) {
        $newRecord = [PSCustomObject]@{
            Experiment = $record.Experiment
            Replication = $record.Replication
            Trial = $record.Trial
            MRR = [double]$record.MRR
            Top1Accuracy = [double]$record.Top1Accuracy
            Top3Accuracy = [double]$record.Top3Accuracy
            MeanRank = [double]$record.MeanRank
            GroupSize = [int]$record.GroupSize
            MappingStrategy = $record.MappingStrategy
            TrialSeq = $trialSequence++
        }
        $allBiasDataWithSeq += $newRecord
    }
    $allBiasData = $allBiasDataWithSeq
    
    # Generate purpose-built two-column files for GraphPad XY regression
    
    # Overall regression: TrialSeq vs MRR (ensure numeric sequencing)
    $overallMRRData = $allBiasData | Select-Object @{N='TrialSeq';E={[int]$_.TrialSeq}}, @{N='MRR';E={[double]$_.MRR}}
    $overallMRRExport = Join-Path $GraphPadImportsDir $BIAS_REGRESSION_MRR_FILE
    $overallMRRData | Export-Csv -Path $overallMRRExport -NoTypeInformation
    Write-Host "  Generated: $BIAS_REGRESSION_MRR_FILE (TrialSeq vs MRR, $($overallMRRData.Count) points)"
    
    # Overall regression: TrialSeq vs Top1Accuracy
    $overallTop1Data = $allBiasData | Select-Object @{N='TrialSeq';E={$_.TrialSeq}}, @{N='Top1Accuracy';E={$_.Top1Accuracy}}
    $overallTop1Export = Join-Path $GraphPadImportsDir $BIAS_REGRESSION_TOP1_FILE
    $overallTop1Data | Export-Csv -Path $overallTop1Export -NoTypeInformation
    Write-Host "  Generated: $BIAS_REGRESSION_TOP1_FILE (TrialSeq vs Top1Accuracy, $($overallTop1Data.Count) points)"
    
    # Overall regression: TrialSeq vs Top3Accuracy
    $overallTop3Data = $allBiasData | Select-Object @{N='TrialSeq';E={$_.TrialSeq}}, @{N='Top3Accuracy';E={$_.Top3Accuracy}}
    $overallTop3Export = Join-Path $GraphPadImportsDir $BIAS_REGRESSION_TOP3_FILE
    $overallTop3Data | Export-Csv -Path $overallTop3Export -NoTypeInformation
    Write-Host "  Generated: $BIAS_REGRESSION_TOP3_FILE (TrialSeq vs Top3Accuracy, $($overallTop3Data.Count) points)"
    
    # Condition-specific analysis
    $correctData = $allBiasData | Where-Object { $_.MappingStrategy -eq "correct" }
    $randomData = $allBiasData | Where-Object { $_.MappingStrategy -eq "random" }
    
    if ($correctData.Count -gt 0) {
        # Correct condition: TrialSeq vs MRR
        $correctMRRData = $correctData | Select-Object @{N='TrialSeq';E={$_.TrialSeq}}, @{N='MRR';E={$_.MRR}}
        $correctMRRExport = Join-Path $GraphPadImportsDir $BIAS_REGRESSION_CORRECT_MRR_FILE
        $correctMRRData | Export-Csv -Path $correctMRRExport -NoTypeInformation
        Write-Host "  Generated: $BIAS_REGRESSION_CORRECT_MRR_FILE ($($correctMRRData.Count) points)"
    }
    
    if ($randomData.Count -gt 0) {
        # Random condition: TrialSeq vs MRR
        $randomMRRData = $randomData | Select-Object @{N='TrialSeq';E={$_.TrialSeq}}, @{N='MRR';E={$_.MRR}}
        $randomMRRExport = Join-Path $GraphPadImportsDir $BIAS_REGRESSION_RANDOM_MRR_FILE
        $randomMRRData | Export-Csv -Path $randomMRRExport -NoTypeInformation
        Write-Host "  Generated: $BIAS_REGRESSION_RANDOM_MRR_FILE ($($randomMRRData.Count) points)"
    }
    
    Write-Host "    - All files are two-column format optimized for GraphPad XY regression" -ForegroundColor Gray
    
    Write-Host "✓ Bias regression validation exports completed`n" -ForegroundColor Green
    
    return @{
        TotalTrials = $allBiasData.Count
        CorrectTrials = $correctData.Count
        RandomTrials = $randomData.Count
    }
}

function Export-TrialByTrialPerformance {
    param($ReplicationPath, $ExperimentName, $ReplicationName)
    
    # Use the same Python extraction logic as Export-RawScoresForGraphPad
    $projectRootEscaped = $ProjectRoot -replace '\\', '/'
    $replicationPathEscaped = $ReplicationPath -replace '\\', '/'
    
    $pythonScript = @"
import sys, os
sys.path.insert(0, '$projectRootEscaped/src')

from analyze_llm_performance import read_score_matrices, read_mappings_and_deduce_k, evaluate_single_test
import logging
logging.getLogger().setLevel(logging.CRITICAL)

analysis_path = os.path.join('$replicationPathEscaped', 'analysis_inputs')
mappings_file = os.path.join(analysis_path, 'all_mappings.txt')
scores_file = os.path.join(analysis_path, 'all_scores.txt')

if not os.path.exists(mappings_file) or not os.path.exists(scores_file):
    exit()
    
mappings, k_val, delim = read_mappings_and_deduce_k(mappings_file)
if not mappings or not k_val:
    exit()
    
matrices = read_score_matrices(scores_file, k_val, delim)
if not matrices:
    exit()

# Extract config info for metadata
config_path = os.path.join('$replicationPathEscaped', 'config.ini.archived')
config_info = {}
if os.path.exists(config_path):
    current_section = ""
    with open(config_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1]
            elif '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                config_info[f'{current_section}:{key.strip()}'] = value.strip()

mapping_strategy = config_info.get('Study:mapping_strategy', 'unknown')
group_size = int(config_info.get('Study:group_size', k_val))

for i, (matrix, mapping) in enumerate(zip(matrices, mappings)):
    result = evaluate_single_test(matrix, mapping, k_val, 3)
    if result:
        print(f'$ExperimentName,$ReplicationName,{i+1},{result["mrr"]},{result["top_1_accuracy"]},{result["top_3_accuracy"]},{result["mean_rank_of_correct_id"]},{group_size},{mapping_strategy}')
"@
    
    $pythonOutput = python -c $pythonScript 2>$null
    $csvData = $pythonOutput | Where-Object { $_ -and $_ -match "," } | ConvertFrom-Csv -Header "Experiment","Replication","Trial","MRR","Top1Accuracy","Top3Accuracy","MeanRank","GroupSize","MappingStrategy"

# Convert Trial to numeric to ensure proper sequencing
$csvData | ForEach-Object { $_.Trial = [int]$_.Trial }
    
    Write-Verbose "Extracted $($csvData.Count) actual trial records from $ReplicationName"
    return $csvData
}

function Show-Phase3ValidationInstructions {
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
    Write-Host "Target: Independent validation of framework calculations including bias analysis." -ForegroundColor Cyan
    
    Write-Host "`nGraphPad Step 3.1:" -ForegroundColor Yellow
    Write-Host "   Open GraphPad Prism and create a new project:" -ForegroundColor Cyan
    Write-Host "     - File → New → New Project File."
    Write-Host "     - CREATE 'Multiple variables' → 'Enter or import data into a new table', then save the project file."
    Write-Host "     - Select 'Project info 1' in the Info section and enter project details."
    Write-Host "     - Note: The steps below are organized by file for clarity. Alternatively," -ForegroundColor Blue
    Write-Host "             all imports, all analyses, and all exports can be performed together in 3 steps." -ForegroundColor Blue
    
    Write-Host "`nGraphPad Step 3.2:" -ForegroundColor Yellow
    Write-Host "   Process raw MRR scores:" -ForegroundColor Cyan
    Write-Host "     - Select the 'Data 1' table and import '$RAW_SCORES_FILE' from 'tests/assets/statistical_validation_study/graphpad_imports/'."
    Write-Host "       with the following options: 'insert and maintain link', auto-update, and 'separate adjacent columns' for commas."
    Write-Host "       Check the box for setting these as the default."
    Write-Host "     - Analyze Data → Multiple variable analyses → Descriptive statistics." -ForegroundColor Gray
    Write-Host "     - Deselect 'A:Trial' (leave all MRR columns selected), then calculate the 'Basics' set of 4 stats groups for each replication." -ForegroundColor Gray
    Write-Host "     - Export analysis results using the default filename ('Descriptive statistics of $RAW_SCORES_FILE') to 'tests/assets/statistical_validation_study/graphpad_exports/'." -ForegroundColor Gray
    
    Write-Host "`nGraphPad Step 3.3:" -ForegroundColor Yellow
    Write-Host "   Process Wilcoxon test results using K-specific datasets:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "     MRR Analysis:" -ForegroundColor Blue
    Write-Host "     • K=4 MRR:" -ForegroundColor Gray
    Write-Host "       - Create a new 'Multiple variables' data table and select the 'enter or import data' option."
    Write-Host "       - Import '$MRR_K4_FILE' into this new table."
    Write-Host "       - Analyze Data → Column analyses → One sample t test and Wilcoxon test."
    Write-Host "       - Select the MRR column only, then choose 'Wilcoxon signed-rank test' with hypothetical value = 0.5208."
    Write-Host "       - Export analysis results using the default filename ('One sample Wilcoxon test of $MRR_K4_FILE')."
    Write-Host "     • K=10 MRR:" -ForegroundColor Gray
    Write-Host "       - Repeat import and analysis for '$MRR_K10_FILE' → hypothetical = 0.2929."
    Write-Host "       - Export analysis results using the default filename ('One sample Wilcoxon test of $MRR_K10_FILE')."
    Write-Host ""
    Write-Host "     Top-1 Accuracy Analysis:" -ForegroundColor Blue
    Write-Host "     • K=4 Top-1:" -ForegroundColor Gray
    Write-Host "       - Repeat import and analysis for '$TOP1_K4_FILE' → hypothetical = 0.25."
    Write-Host "       - Export analysis results using the default filename ('One sample Wilcoxon test of $TOP1_K4_FILE')."
    Write-Host "     • K=10 Top-1:" -ForegroundColor Gray
    Write-Host "       - Repeat import and analysis for '$TOP1_K10_FILE' → hypothetical = 0.1."
    Write-Host "       - Export analysis results using the default filename ('One sample Wilcoxon test of $TOP1_K10_FILE')."
    Write-Host ""
    Write-Host "     Top-3 Accuracy Analysis:" -ForegroundColor Blue
    Write-Host "     • K=4 Top-3:" -ForegroundColor Gray
    Write-Host "       - Repeat import and analysis for '$TOP3_K4_FILE' → hypothetical = 0.75."
    Write-Host "       - Export analysis results using the default filename ('One sample Wilcoxon test of $TOP3_K4_FILE')."
    Write-Host "     • K=10 Top-3:" -ForegroundColor Gray
    Write-Host "       - Repeat import and analysis for '$TOP3_K10_FILE' → hypothetical = 0.3."
    Write-Host "       - Export analysis results using the default filename ('One sample Wilcoxon test of $TOP3_K10_FILE')."
    
    Write-Host "`nGraphPad Step 3.4:" -ForegroundColor Yellow
    Write-Host "   Process ANOVA with Effect Size Validation:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "     MRR ANOVA Analysis with Effect Size:" -ForegroundColor Blue
    Write-Host "     • Create new 'Grouped' table, specify 6 replicate values in subcolumns." -ForegroundColor Gray
    Write-Host "     • Import '$ANOVA_MRR_FILE'." -ForegroundColor Gray
    Write-Host "     • Analyze Data → Grouped analyses → Two-way ANOVA." -ForegroundColor Gray
    Write-Host "     • Enable interaction term (full model) and 'Show effect size (eta-squared)'" -ForegroundColor Gray
    Write-Host "     • Export analysis results using the default filename ('2way ANOVA of $ANOVA_MRR_FILE')." -ForegroundColor Gray
    Write-Host ""
    Write-Host "     Top-1 Accuracy ANOVA Analysis with Effect Size:" -ForegroundColor Blue
    Write-Host "     • Repeat import and analysis for '$ANOVA_TOP1_FILE'." -ForegroundColor Gray
    Write-Host "     • Export analysis results using the default filename ('2way ANOVA of $ANOVA_TOP1_FILE')." -ForegroundColor Gray
    Write-Host ""
    Write-Host "     Top-3 Accuracy ANOVA Analysis with Effect Size:" -ForegroundColor Blue
    Write-Host "     • Repeat import and analysis for '$ANOVA_TOP3_FILE'." -ForegroundColor Gray
    Write-Host "     • Export analysis results using the default filename ('2way ANOVA of $ANOVA_TOP3_FILE')." -ForegroundColor Gray
    
    # Bias Regression Analysis Instructions
    Write-Host "`nGraphPad Step 3.5:" -ForegroundColor Yellow
    Write-Host "   Process Bias Regression Analysis:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "     Overall Bias Regression Analysis:" -ForegroundColor Blue
    Write-Host "     • Create new 'XY' data table with numbers for X and single values for Y." -ForegroundColor Gray
    Write-Host "     • Import '$BIAS_REGRESSION_MRR_FILE'." -ForegroundColor Gray
    Write-Host "     • Analyze Data → XY analyses → Simple linear regression." -ForegroundColor Gray
    Write-Host "     • Include 'Test departure from linearity with runs test' and change sifnificant digits to 6; check 'make default'." -ForegroundColor Gray
    Write-Host "     • Export analysis results using the default filename ('Simple linear regression of $BIAS_REGRESSION_MRR_FILE')." -ForegroundColor Gray
    Write-Host ""
    Write-Host "     Top-1 Accuracy Regression Metrics:" -ForegroundColor Blue
    Write-Host "     • Repeat import and analysis for '$BIAS_REGRESSION_TOP1_FILE'." -ForegroundColor Gray
    Write-Host "     • Export analysis results using the default filename ('Simple linear regression of $BIAS_REGRESSION_TOP1_FILE')." -ForegroundColor Gray
    Write-Host ""
    Write-Host "     Top-3 Accuracy Regression Metrics:" -ForegroundColor Blue
    Write-Host "     • Repeat import and analysis for '$BIAS_REGRESSION_TOP3_FILE'." -ForegroundColor Gray
    Write-Host "     • Export analysis results using the default filename ('Simple linear regression of $BIAS_REGRESSION_TOP3_FILE')." -ForegroundColor Gray
    
    Write-Host "     Condition-Specific Bias Analysis:" -ForegroundColor Blue
    Write-Host "     • Correct Condition:" -ForegroundColor Gray
    Write-Host "       - Repeat import and analysis for '$BIAS_REGRESSION_CORRECT_MRR_FILE'." -ForegroundColor Gray
    Write-Host "       - Export analysis results using the default filename ('Simple linear regression of $BIAS_REGRESSION_CORRECT_MRR_FILE')." -ForegroundColor Gray
    Write-Host "     • Random Condition:" -ForegroundColor Gray
    Write-Host "       - Repeat import and analysis for '$BIAS_REGRESSION_RANDOM_MRR_FILE'." -ForegroundColor Gray
    Write-Host "       - Export analysis results using the default filename ('Simple linear regression of $BIAS_REGRESSION_RANDOM_MRR_FILE')." -ForegroundColor Gray
    Write-Host ""
    Write-Host "`nAFTER COMPLETING GRAPHPAD ANALYSIS:" -ForegroundColor Cyan
    Write-Host "Run Step 4 validation:" -ForegroundColor Yellow
    Write-Host "pdm run test-stats-results" -ForegroundColor Gray
    
    Write-Host "`nSUCCESS CRITERIA:" -ForegroundColor Green
    Write-Host "Step 4 will validate within established tolerances:" -ForegroundColor Cyan
    Write-Host "• MRR, Top-1, Top-3 accuracy calculations and Wilcoxon p-values (±0.0001)" -ForegroundColor White
    Write-Host "• ANOVA F-statistics (±0.01) and eta-squared effect sizes (±0.01)" -ForegroundColor White
    Write-Host "• Linear regression slopes (±0.0001), R-values (±0.01), p-values (±0.001)" -ForegroundColor White
    Write-Host "Citation ready: 'Statistical analyses were validated against GraphPad Prism 10.6.1'" -ForegroundColor Yellow
    
    Write-Host "`nVALIDATION SUMMARY:" -ForegroundColor Cyan
    Write-Host "Replications to validate: $($ExportStats.ReplicationCount)" -ForegroundColor White
    Write-Host "Total trials analyzed: $($ExportStats.TrialCount)" -ForegroundColor White
    Write-Host "Export files: 15+ total (6 K-specific + 3 ANOVA + 3+ Bias + 3+ reference files)" -ForegroundColor White
    
    $kStats = $ExportStats.KSpecificStats
    if ($kStats) {
        Write-Host "K-specific validation counts:" -ForegroundColor White
        Write-Host "  K=4: $($kStats.K4_MRR_Count) MRR, $($kStats.K4_Top1_Count) Top-1, $($kStats.K4_Top3_Count) Top-3" -ForegroundColor Gray
        Write-Host "  K=10: $($kStats.K10_MRR_Count) MRR, $($kStats.K10_Top1_Count) Top-1, $($kStats.K10_Top3_Count) Top-3" -ForegroundColor Gray
    }
    
    $anovaStats = $ExportStats.ANOVAStats
    if ($anovaStats) {
        Write-Host "ANOVA validation data:" -ForegroundColor White
        Write-Host "  Raw data points: $($anovaStats.ANOVADataPoints)" -ForegroundColor Gray
        Write-Host "  Effect size entries: $($anovaStats.EffectSizeStats.EffectSizeCount)" -ForegroundColor Gray
    }
    
    $biasStats = $ExportStats.BiasStats
    if ($biasStats) {
        Write-Host "Bias regression validation data:" -ForegroundColor White
        Write-Host "  Total trial records: $($biasStats.TotalTrials)" -ForegroundColor Gray
        Write-Host "  Correct condition trials: $($biasStats.CorrectTrials)" -ForegroundColor Gray
        Write-Host "  Random condition trials: $($biasStats.RandomTrials)" -ForegroundColor Gray
    }
    
    Write-Host "Export directory: $(Split-Path $ExportStats.ExportDirectory -Leaf)" -ForegroundColor White
}

function Generate-GraphPadExports {
    param($TestStudyPath)
    
    Write-TestStep "Generating GraphPad Prism Import Files"
    
    # Create export directory structure
    New-Item -ItemType Directory -Path $GraphPadImportsDir -Force | Out-Null

    # Create graphpad_exports directory for Step 4 validation
    $GraphPadExportsDir = Join-Path $ProjectRoot "tests/assets/statistical_validation_study/graphpad_exports"
    New-Item -ItemType Directory -Path $GraphPadExportsDir -Force | Out-Null
    
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
    
    # Create reference data directory
    $ReferenceDataDir = Join-Path $GraphPadImportsDir "reference_data"
    New-Item -ItemType Directory -Path $ReferenceDataDir -Force | Out-Null
    
    # Export replication-level summary to reference folder
    $replicationExport = Join-Path $ReferenceDataDir "Phase_A_Replication_Metrics.csv"
    $allReplicationData | Export-Csv -Path $replicationExport -NoTypeInformation
    Write-Host "  Generated: Phase_A_Replication_Metrics.csv ($($allReplicationData.Count) replications) [reference]"
    
    # Export raw scores in long format to reference folder
    $rawScoresLongExport = Join-Path $ReferenceDataDir "Phase_A_Raw_Scores_Long.csv"
    $allRawScores | Export-Csv -Path $rawScoresLongExport -NoTypeInformation
    
    # Export raw scores in wide format for GraphPad column-based analysis
    $rawScoresExport = Join-Path $GraphPadImportsDir $RAW_SCORES_FILE
    $allRawScoresWide = Export-RawScoresForGraphPadWide -AllRawScores $allRawScores
    if ($allRawScoresWide) {
        $allRawScoresWide | Export-Csv -Path $rawScoresExport -NoTypeInformation
    }
    
    Write-Host "  Generated: Phase_A_Raw_Scores_Long.csv ($($allRawScores.Count) trials) [reference]"
    Write-Host "  Generated: Phase_A_Raw_Scores.csv (GraphPad column format)"
    
    Write-Host "✓ Replication-level exports completed`n" -ForegroundColor Green
    
    # Generate K-specific accuracy datasets for Wilcoxon testing
    $kSpecificStats = Generate-KSpecificAccuracyExports -AllReplicationData $allReplicationData
    
    # Generate ANOVA exports with effect size validation
    $anovaStats = Generate-ANOVAExports -TestStudyPath $TestStudyPath
    
    # Generate bias regression exports for linear regression validation (Phase 3)
    $biasStats = Export-BiasRegressionDataForGraphPad -TestStudyPath $TestStudyPath
    
    $studyResultsPath = Join-Path $TestStudyPath "STUDY_results.csv"
    if (Test-Path $studyResultsPath) {
        $studyData = Import-Csv $studyResultsPath
        
        # Generate GraphPad Grouped Table format (rows=mapping_strategy, columns=k, subcolumns=replicates)
        Write-Host "Phase B: Generating GraphPad grouped table format..." -ForegroundColor Cyan
        
        # Extract MRR values by condition
        $correctK4Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "correct" -and $_.k -eq 4 }).mean_mrr)
        $correctK10Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "correct" -and $_.k -eq 10 }).mean_mrr)
        $randomK4Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "random" -and $_.k -eq 4 }).mean_mrr)
        $randomK10Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "random" -and $_.k -eq 10 }).mean_mrr)
        
        # Determine number of replicates (should be 6 each)
        $numReplicates = [math]::Max([math]::Max($correctK4Values.Count, $correctK10Values.Count), [math]::Max($randomK4Values.Count, $randomK10Values.Count))
        
        # Create header row with repeated column factor levels for each subcolumn
        $headerParts = @()
        # K4 repeated 6 times for 6 subcolumns
        for ($i = 1; $i -le $numReplicates; $i++) { $headerParts += "K4" }
        # K10 repeated 6 times for 6 subcolumns  
        for ($i = 1; $i -le $numReplicates; $i++) { $headerParts += "K10" }
        $headerRow = "," + ($headerParts -join ",")
        
        # Create Correct row (mapping_strategy = correct)
        $correctRowParts = @("Correct")
        for ($i = 0; $i -lt $numReplicates; $i++) {
            $correctRowParts += if ($i -lt $correctK4Values.Count) { $correctK4Values[$i] } else { "" }
        }
        for ($i = 0; $i -lt $numReplicates; $i++) {
            $correctRowParts += if ($i -lt $correctK10Values.Count) { $correctK10Values[$i] } else { "" }
        }
        $correctRow = $correctRowParts -join ","
        
        # Create Random row (mapping_strategy = random)
        $randomRowParts = @("Random")
        for ($i = 0; $i -lt $numReplicates; $i++) {
            $randomRowParts += if ($i -lt $randomK4Values.Count) { $randomK4Values[$i] } else { "" }
        }
        for ($i = 0; $i -lt $numReplicates; $i++) {
            $randomRowParts += if ($i -lt $randomK10Values.Count) { $randomK10Values[$i] } else { "" }
        }
        $randomRow = $randomRowParts -join ","
        
        # Combine all rows
        $csvContent = @($headerRow, $correctRow, $randomRow)
        
        $anovaGraphPadExport = Join-Path $GraphPadImportsDir $ANOVA_MRR_FILE
        $csvContent | Out-File -FilePath $anovaGraphPadExport -Encoding UTF8
        
        Write-Host "  Generated: Phase_B_ANOVA_MRR.csv (GraphPad grouped table format)"
        Write-Host "    - Rows: Correct vs Random (mapping strategy)" -ForegroundColor Gray
        Write-Host "    - Columns: K4 vs K10 (group size) with $numReplicates subcolumns each" -ForegroundColor Gray

        # Generate summary statistics for reference
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
        
        $summaryExport = Join-Path $ReferenceDataDir "Phase_B_Summary_Statistics.csv"
        $summaryStats | Export-Csv -Path $summaryExport -NoTypeInformation
        Write-Host "  Generated: Phase_B_Summary_Statistics.csv (4 groups) [reference]"
        
        Write-Host "✓ GraphPad grouped table format completed`n" -ForegroundColor Green
    } else {
        Write-Host "  ! STUDY_results.csv not found - Phase B exports skipped" -ForegroundColor Yellow
        Write-Host "     Run compile_study.ps1 first to generate study-level data" -ForegroundColor Gray
    }
    
    return @{
        ReplicationCount = $allReplicationData.Count
        TrialCount = $allRawScores.Count
        ExportDirectory = $GraphPadImportsDir
        KSpecificStats = $kSpecificStats
        ANOVAStats = $anovaStats
        BiasStats = $biasStats
    }
}

# =============================================================================
# MAIN TEST EXECUTION
# =============================================================================

try {
    Write-TestHeader "Validation of Statistical Analysis & Reporting - Step 2/4: GraphPad Import Generator" 'Magenta'
    
    if ($Interactive) {
        Write-Host "${C_BLUE}Two-Phase GraphPad Prism Validation Strategy:${C_RESET}"
        Write-Host ""
        Write-Host "Phase A: Core algorithmic validation against GraphPad"
        Write-Host "  • Mean Reciprocal Rank (MRR) calculations and Wilcoxon tests"
        Write-Host "  • Top-1 accuracy calculations and Wilcoxon tests"
        Write-Host "  • Top-3 accuracy calculations and Wilcoxon tests"
        Write-Host "  • K-specific validation datasets for comprehensive coverage"
        Write-Host "  • Bias regression analysis (slope, R-value)"
        Write-Host "  • Effect size calculations (Cohen's r)"
        Write-Host ""
        Write-Host "Phase B: Standard statistical analyses validation against GraphPad"
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
    
    # Display study parameters for validation context
    Write-Host "`nStudy Parameters:" -ForegroundColor Cyan
    $relativeStudyPath = [System.IO.Path]::GetRelativePath($ProjectRoot, $StatisticalStudyPath)
    Write-Host "  Study directory: $relativeStudyPath" -ForegroundColor Gray
    
    # Extract study details from first experiment
    $firstExp = Get-ChildItem -Path $StatisticalStudyPath -Directory -Name "exp_*" | Select-Object -First 1
    if ($firstExp) {
        $firstExpPath = Join-Path $StatisticalStudyPath $firstExp
        $configPath = Get-ChildItem -Path $firstExpPath -Recurse -Name "config.ini.archived" | Select-Object -First 1
        if ($configPath) {
            $configFullPath = Join-Path $firstExpPath $configPath
            $config = @{}
            Get-Content $configFullPath | ForEach-Object {
                $line = $_.Trim()
                if ($line -match "^\[(.+)\]$") {
                    $currentSection = $matches[1]
                } elseif ($line -match "^([^=]+)=(.*)$" -and $line -notmatch "^#") {
                    $key = $matches[1].Trim()
                    $value = $matches[2].Trim()
                    $config["$currentSection`:$key"] = $value
                }
            }
            
            Write-Host "  LLM model: $($config['LLM:model_name'])" -ForegroundColor Gray
            Write-Host "  Factorial design: 2×2 (Mapping Strategy × Group Size)" -ForegroundColor Gray
            Write-Host "  Number of experiments: 4 (correct/random × k4/k10)" -ForegroundColor Gray
            Write-Host "  Replications per experiment: $($config['Study:num_replications'])" -ForegroundColor Gray
            Write-Host "  Trials per replication: $($config['Study:num_trials'])" -ForegroundColor Gray
            
            $totalReplications = 4 * [int]$config['Study:num_replications']
            $totalTrials = $totalReplications * [int]$config['Study:num_trials']
            Write-Host "  Total replications: $totalReplications" -ForegroundColor Gray
            Write-Host "  Total trials: $totalTrials" -ForegroundColor Gray
        }
    }
    
    if ($Interactive) {
        Read-Host "Press Enter to continue..." | Out-Null
    }
    
    # Step 2: Setup Test Environment
    Write-Host ""
    Write-TestStep "Step 2: Setup Test Environment"

    # Always ask for confirmation before clearing the directory
    $leafDir = Split-Path $GraphPadImportsDir -Leaf
    $parentDir = Split-Path (Split-Path $GraphPadImportsDir -Parent) -Leaf
    $folderToClear = "$parentDir/$leafDir" # Force forward slash for display

    # Only show the destructive warning prompt if the directory actually exists
    if (Test-Path $GraphPadImportsDir) {
        Write-Host "${C_YELLOW}WARNING: Output directory '$folderToClear' already exists."
        Write-Host "${C_RED}This will permanently delete all existing data in this directory.${C_RESET}"
        Write-Host "" # Blank line
        $choice = Read-Host "Are you sure you want to continue? (Y/N):"
        
        if ($choice.ToLower() -ne 'y') {
            Write-Host "${C_YELLOW}Operation cancelled by user.${C_RESET}"
            exit 1
        }
    }

    Write-Host "Clearing and preparing the GraphPad imports directory..." -ForegroundColor Cyan
    if (Test-Path $GraphPadImportsDir) {
        Get-ChildItem -Path $GraphPadImportsDir -Recurse | Remove-Item -Recurse -Force
    } else {
        New-Item -ItemType Directory -Path $GraphPadImportsDir -Force | Out-Null
    }
    Write-Host "✓ GraphPad imports directory is ready." -ForegroundColor Green
    
    if ($Interactive) {
        Read-Host "Press Enter to continue..." | Out-Null
    }
    
    # Step 3: Check if Analysis Already Complete (skip compilation for pre-compiled study)
    Write-Host ""
    Write-TestStep "Step 3: Verify Analysis Readiness"
    
    # Check if study is already compiled (has STUDY_results.csv)
    $studyResultsPath = Join-Path $StatisticalStudyPath "STUDY_results.csv"
    if (Test-Path $studyResultsPath) {
        Write-Host "✓ Study already compiled - using existing analysis" -ForegroundColor Green
    } elseif (-not $ExportOnly) {
        Write-Host "Compiling study in source directory: '$StatisticalStudyPath'..." -ForegroundColor Cyan
        $compileResult = & "$ProjectRoot\compile_study.ps1" -StudyDirectory $StatisticalStudyPath
        if ($LASTEXITCODE -ne 0) {
            throw "Study compilation failed with exit code $LASTEXITCODE"
        }
        Write-Host "✓ Analysis pipeline completed" -ForegroundColor Green
    }

    if ($Interactive) {
        Read-Host "Press Enter to continue..." | Out-Null
    }
    
    # Step 4: Generate GraphPad Exports
    Write-Host ""
    Write-TestStep "Step 4: Generate GraphPad Export Files"
    
    $exportStats = Generate-GraphPadExports -TestStudyPath $StatisticalStudyPath
    
    # Step 5: Show Enhand Validation Instructions
    if (-not $ExportOnly) {
        Show-Phase3ValidationInstructions -ExportStats $exportStats
        
        if ($Interactive) {
            Write-Host "`n${C_YELLOW}Next Steps:${C_RESET}"
            Write-Host "1. Open GraphPad Prism 10.6.1"
            Write-Host "2. Follow the validation instructions above"
            Write-Host "3. Process 6 K-specific datasets (2 MRR + 2 Top-1 + 2 Top-3)"
            Write-Host "4. Export all Wilcoxon test results for validation"
            Write-Host "5. Run Step 4 validation to compare results"
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
    Write-Host "6 K-specific accuracy validation files" -ForegroundColor Cyan
    Write-Host "ANOVA with effect size validation" -ForegroundColor Cyan
    Write-Host "Bias regression analysis validation" -ForegroundColor Cyan
} else {
    Write-Host "Ready for GraphPad Prism validation - follow instructions above" -ForegroundColor Yellow
    Write-Host ""
}

exit 0

# === End of tests/algorithm_validation/generate_graphpad_imports.ps1 ===
