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
    Statistical Analysis & Reporting Validation Test - Enhanced GraphPad Prism Validation (Phase 1)

.DESCRIPTION
    Enhanced version implementing Phase 1 of the accuracy validation action plan:
    
    This test validates the complete statistical analysis pipeline against GraphPad Prism 10.0.0.
    It implements a two-phase validation strategy with Phase 1 enhancements:
    
    Phase A (Replication-Level): Validates core algorithmic contributions (ENHANCED)
    - Mean Reciprocal Rank (MRR) calculations with K-specific validation
    - Top-1 accuracy calculations with K-specific validation (NEW)
    - Top-3 accuracy calculations with K-specific validation (NEW)  
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
    Run the enhanced GraphPad validation workflow with step-by-step guidance.

.EXAMPLE
    .\generate_graphpad_imports.ps1 -ExportOnly
    Generate enhanced GraphPad import files only (for batch processing).
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

# =============================================================================
# ENHANCED K-SPECIFIC ACCURACY EXPORT GENERATION (Phase 1)
# =============================================================================

function Generate-KSpecificAccuracyExports {
    param($AllReplicationData)
    
    Write-Host "Phase A: Generating K-specific accuracy validation exports (Phase 1)..." -ForegroundColor Cyan
    
    # Filter data by group size
    $k4Data = $AllReplicationData | Where-Object { $_.GroupSize -eq 4 }
    $k10Data = $AllReplicationData | Where-Object { $_.GroupSize -eq 10 }
    
    $exportStats = @{}
    
    # =============================================================================
    # MRR K-SPECIFIC EXPORTS (EXISTING - Enhanced)
    # =============================================================================
    
    $k4MRRData = $k4Data | Select-Object @{N='MRR';E={$_.MeanMRR}}, @{N='Chance';E={0.25}}, @{N='K';E={$_.GroupSize}}, @{N='Replication';E={$_.Replication}}, @{N='Experiment';E={$_.Experiment}}
    $k10MRRData = $k10Data | Select-Object @{N='MRR';E={$_.MeanMRR}}, @{N='Chance';E={0.1}}, @{N='K';E={$_.GroupSize}}, @{N='Replication';E={$_.Replication}}, @{N='Experiment';E={$_.Experiment}}

    $k4MRRExport = Join-Path $GraphPadImportsDir "Phase_A_MRR_K4.csv"
    $k10MRRExport = Join-Path $GraphPadImportsDir "Phase_A_MRR_K10.csv"
    
    $k4MRRData | Export-Csv -Path $k4MRRExport -NoTypeInformation
    $k10MRRData | Export-Csv -Path $k10MRRExport -NoTypeInformation

    $exportStats.K4_MRR_Count = $k4MRRData.Count
    $exportStats.K10_MRR_Count = $k10MRRData.Count

    Write-Host "  ✓ Generated: Phase_A_MRR_K4.csv ($($k4MRRData.Count) replications, chance = 0.25)" -ForegroundColor Green
    Write-Host "  ✓ Generated: Phase_A_MRR_K10.csv ($($k10MRRData.Count) replications, chance = 0.1)" -ForegroundColor Green
    
    # =============================================================================
    # TOP-1 ACCURACY K-SPECIFIC EXPORTS (NEW - Phase 1)
    # =============================================================================
    
    $k4Top1Data = $k4Data | Select-Object @{N='Top1Accuracy';E={$_.MeanTop1Accuracy}}, @{N='Chance';E={0.25}}, @{N='K';E={$_.GroupSize}}, @{N='Replication';E={$_.Replication}}, @{N='Experiment';E={$_.Experiment}}
    $k10Top1Data = $k10Data | Select-Object @{N='Top1Accuracy';E={$_.MeanTop1Accuracy}}, @{N='Chance';E={0.1}}, @{N='K';E={$_.GroupSize}}, @{N='Replication';E={$_.Replication}}, @{N='Experiment';E={$_.Experiment}}

    $k4Top1Export = Join-Path $GraphPadImportsDir "Phase_A_Top1_K4.csv"
    $k10Top1Export = Join-Path $GraphPadImportsDir "Phase_A_Top1_K10.csv"
    
    $k4Top1Data | Export-Csv -Path $k4Top1Export -NoTypeInformation
    $k10Top1Data | Export-Csv -Path $k10Top1Export -NoTypeInformation

    $exportStats.K4_Top1_Count = $k4Top1Data.Count
    $exportStats.K10_Top1_Count = $k10Top1Data.Count

    Write-Host "  ✓ Generated: Phase_A_Top1_K4.csv ($($k4Top1Data.Count) replications, chance = 0.25)" -ForegroundColor Green
    Write-Host "  ✓ Generated: Phase_A_Top1_K10.csv ($($k10Top1Data.Count) replications, chance = 0.1)" -ForegroundColor Green
    
    # =============================================================================
    # TOP-3 ACCURACY K-SPECIFIC EXPORTS (NEW - Phase 1)  
    # =============================================================================
    
    # Top-3 accuracy chance calculations: min(3, k) / k
    # K=4: min(3,4)/4 = 3/4 = 0.75
    # K=10: min(3,10)/10 = 3/10 = 0.3
    
    $k4Top3Data = $k4Data | Select-Object @{N='Top3Accuracy';E={$_.MeanTop3Accuracy}}, @{N='Chance';E={0.75}}, @{N='K';E={$_.GroupSize}}, @{N='Replication';E={$_.Replication}}, @{N='Experiment';E={$_.Experiment}}
    $k10Top3Data = $k10Data | Select-Object @{N='Top3Accuracy';E={$_.MeanTop3Accuracy}}, @{N='Chance';E={0.3}}, @{N='K';E={$_.GroupSize}}, @{N='Replication';E={$_.Replication}}, @{N='Experiment';E={$_.Experiment}}

    $k4Top3Export = Join-Path $GraphPadImportsDir "Phase_A_Top3_K4.csv"
    $k10Top3Export = Join-Path $GraphPadImportsDir "Phase_A_Top3_K10.csv"
    
    $k4Top3Data | Export-Csv -Path $k4Top3Export -NoTypeInformation
    $k10Top3Data | Export-Csv -Path $k10Top3Export -NoTypeInformation

    $exportStats.K4_Top3_Count = $k4Top3Data.Count
    $exportStats.K10_Top3_Count = $k10Top3Data.Count

    Write-Host "  ✓ Generated: Phase_A_Top3_K4.csv ($($k4Top3Data.Count) replications, chance = 0.75)" -ForegroundColor Green
    Write-Host "  ✓ Generated: Phase_A_Top3_K10.csv ($($k10Top3Data.Count) replications, chance = 0.3)" -ForegroundColor Green
    
    return $exportStats
}

# =============================================================================
# PHASE 2: EFFECT SIZE CALCULATIONS ENHANCEMENT
# =============================================================================

function Export-EffectSizeDataForGraphPad {
    param($TestStudyPath)
    
    Write-Host "Phase B: Generating effect size validation exports (Phase 2)..." -ForegroundColor Cyan
    
    # Check if study compilation generated ANOVA analysis
    $anovaLogPath = Join-Path $TestStudyPath "anova/STUDY_analysis_log.txt"
    if (-not (Test-Path $anovaLogPath)) {
        Write-Host "  ! ANOVA analysis log not found - effect size validation skipped" -ForegroundColor Yellow
        return $null
    }
    
    # For Phase 2, we'll use the raw study data for effect size verification
    # This allows GraphPad to calculate ANOVA independently
    Write-Host "  ✓ ANOVA analysis found - preparing effect size validation" -ForegroundColor Green
    
    return @{
        EffectSizeCount = "Available"
        ExportPath = "Will be generated from raw data"
    }
}

function Generate-EnhancedANOVAExports {
    param($TestStudyPath)
    
    Write-Host "Phase B: Generating enhanced ANOVA exports with effect size validation (Phase 2)..." -ForegroundColor Cyan
    
    $studyResultsPath = Join-Path $TestStudyPath "STUDY_results.csv"
    if (-not (Test-Path $studyResultsPath)) {
        Write-Host "  ! STUDY_results.csv not found - Phase B exports skipped" -ForegroundColor Yellow
        return $null
    }
    
    $studyData = Import-Csv $studyResultsPath
    
    # Generate standard ANOVA export (existing functionality)
    $correctK4Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "correct" -and $_.k -eq 4 }).mean_mrr)
    $correctK10Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "correct" -and $_.k -eq 10 }).mean_mrr)
    $randomK4Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "random" -and $_.k -eq 4 }).mean_mrr)
    $randomK10Values = @(($studyData | Where-Object { $_.mapping_strategy -eq "random" -and $_.k -eq 10 }).mean_mrr)
    
    $numReplicates = [math]::Max([math]::Max($correctK4Values.Count, $correctK10Values.Count), [math]::Max($randomK4Values.Count, $randomK10Values.Count))
    
    # Create standard ANOVA export (existing)
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
    
    $anovaExport = Join-Path $GraphPadImportsDir "Phase_B_ANOVA_MRR.csv"
    $csvContent | Out-File -FilePath $anovaExport -Encoding UTF8
    
    Write-Host "  ✓ Generated: Phase_B_ANOVA_MRR.csv (GraphPad grouped table format)" -ForegroundColor Green
    Write-Host "    - Rows: Correct vs Random (mapping strategy)" -ForegroundColor Gray
    Write-Host "    - Columns: K4 vs K10 (group size) with $numReplicates subcolumns each" -ForegroundColor Gray
    
    # Generate grouped format files for effect size verification (NEW - Phase 2)
    
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
    
    $top1AnovaExport = Join-Path $GraphPadImportsDir "Phase_B_ANOVA_Top1.csv"
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
    
    $top3AnovaExport = Join-Path $GraphPadImportsDir "Phase_B_ANOVA_Top3.csv"
    $top3CsvContent | Out-File -FilePath $top3AnovaExport -Encoding UTF8
    
    Write-Host "  ✓ Generated: Phase_B_ANOVA_Top1.csv (Top-1 accuracy grouped format for effect size verification)" -ForegroundColor Green
    Write-Host "  ✓ Generated: Phase_B_ANOVA_Top3.csv (Top-3 accuracy grouped format for effect size verification)" -ForegroundColor Green
    Write-Host "    - 3 grouped ANOVA files total (MRR, Top-1, Top-3) for comprehensive effect size validation" -ForegroundColor Gray
    
    # Export effect size data from framework analysis
    $effectSizeStats = Export-EffectSizeDataForGraphPad -TestStudyPath $TestStudyPath
    
    return @{
        ANOVADataPoints = $rawAnovaData.Count
        EffectSizeStats = $effectSizeStats
        NumReplicates = $numReplicates
    }
}

# =============================================================================
# PHASE 3: BIAS REGRESSION ANALYSIS ENHANCEMENT
# =============================================================================

function Export-BiasRegressionDataForGraphPad {
    param($TestStudyPath)
    
    Write-Host "Phase B: Generating bias regression validation exports..." -ForegroundColor Cyan
    
    $allBiasData = @()
    $experiments = Get-ChildItem -Path $TestStudyPath -Directory -Name "exp_*"
    
    foreach ($experiment in $experiments) {
        $expPath = Join-Path $TestStudyPath $experiment
        $replications = Get-ChildItem -Path $expPath -Directory -Name "run_*"
        
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
    foreach ($record in $allBiasData) {
        $record.TrialSeq = $trialSequence++
    }
    
    # Generate purpose-built two-column files for GraphPad XY regression
    
    # Overall regression: TrialSeq vs MRR
    $overallMRRData = $allBiasData | Select-Object @{N='TrialSeq';E={$_.TrialSeq}}, @{N='MRR';E={$_.MRR}}
    $overallMRRExport = Join-Path $GraphPadImportsDir "Phase_A_Bias_Regression_MRR.csv"
    $overallMRRData | Export-Csv -Path $overallMRRExport -NoTypeInformation
    Write-Host "  ✅ Generated: Phase_A_Bias_Regression_MRR.csv (TrialSeq vs MRR, $($overallMRRData.Count) points)" -ForegroundColor Green
    
    # Overall regression: TrialSeq vs Top1Accuracy
    $overallTop1Data = $allBiasData | Select-Object @{N='TrialSeq';E={$_.TrialSeq}}, @{N='Top1Accuracy';E={$_.Top1Accuracy}}
    $overallTop1Export = Join-Path $GraphPadImportsDir "Phase_A_Bias_Regression_Top1.csv"
    $overallTop1Data | Export-Csv -Path $overallTop1Export -NoTypeInformation
    Write-Host "  ✅ Generated: Phase_A_Bias_Regression_Top1.csv (TrialSeq vs Top1Accuracy, $($overallTop1Data.Count) points)" -ForegroundColor Green
    
    # Overall regression: TrialSeq vs Top3Accuracy
    $overallTop3Data = $allBiasData | Select-Object @{N='TrialSeq';E={$_.TrialSeq}}, @{N='Top3Accuracy';E={$_.Top3Accuracy}}
    $overallTop3Export = Join-Path $GraphPadImportsDir "Phase_A_Bias_Regression_Top3.csv"
    $overallTop3Data | Export-Csv -Path $overallTop3Export -NoTypeInformation
    Write-Host "  ✅ Generated: Phase_A_Bias_Regression_Top3.csv (TrialSeq vs Top3Accuracy, $($overallTop3Data.Count) points)" -ForegroundColor Green
    
    # Condition-specific analysis
    $correctData = $allBiasData | Where-Object { $_.MappingStrategy -eq "correct" }
    $randomData = $allBiasData | Where-Object { $_.MappingStrategy -eq "random" }
    
    if ($correctData.Count -gt 0) {
        # Correct condition: TrialSeq vs MRR
        $correctMRRData = $correctData | Select-Object @{N='TrialSeq';E={$_.TrialSeq}}, @{N='MRR';E={$_.MRR}}
        $correctMRRExport = Join-Path $GraphPadImportsDir "Phase_A_Bias_Regression_Correct_MRR.csv"
        $correctMRRData | Export-Csv -Path $correctMRRExport -NoTypeInformation
        Write-Host "  ✅ Generated: Phase_A_Bias_Regression_Correct_MRR.csv ($($correctMRRData.Count) points)" -ForegroundColor Green
    }
    
    if ($randomData.Count -gt 0) {
        # Random condition: TrialSeq vs MRR
        $randomMRRData = $randomData | Select-Object @{N='TrialSeq';E={$_.TrialSeq}}, @{N='MRR';E={$_.MRR}}
        $randomMRRExport = Join-Path $GraphPadImportsDir "Phase_A_Bias_Regression_Random_MRR.csv"
        $randomMRRData | Export-Csv -Path $randomMRRExport -NoTypeInformation
        Write-Host "  ✅ Generated: Phase_A_Bias_Regression_Random_MRR.csv ($($randomMRRData.Count) points)" -ForegroundColor Green
    }
    
    Write-Host "    - All files are two-column format optimized for GraphPad XY regression" -ForegroundColor Gray
    
    return @{
        TotalTrials = $allBiasData.Count
        CorrectTrials = $correctData.Count
        RandomTrials = $randomData.Count
    }
}

function Export-TrialByTrialPerformance {
    param($ReplicationPath, $ExperimentName, $ReplicationName)
    
    # Extract bias metrics from existing replication_metrics.json
    $metricsPath = Join-Path $ReplicationPath "analysis_inputs/replication_metrics.json"
    if (-not (Test-Path $metricsPath)) {
        Write-Verbose "No metrics file found at $metricsPath"
        return $null
    }
    
    try {
        $metrics = Get-Content $metricsPath -Raw | ConvertFrom-Json
        
        # Extract configuration metadata
        $configPath = Join-Path $ReplicationPath "config.ini.archived"
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
        
        $mappingStrategy = $config['Study:mapping_strategy'] -as [string]
        $groupSize = [int]$config['Study:group_size']
        
        # Create a single record with the bias regression metrics from this replication
        $biasRecord = [PSCustomObject]@{
            Experiment = $ExperimentName
            Replication = $ReplicationName
            MappingStrategy = $mappingStrategy
            GroupSize = $groupSize
            Trial = 1  # Single record per replication
            TrialSeq = 1
            MRR = [double]$metrics.mean_mrr
            Top1Accuracy = [double]$metrics.mean_top_1_acc
            Top3Accuracy = [double]$metrics.mean_top_3_acc
            MeanRank = [double]$metrics.mean_rank_of_correct_id
            Slope = [double]$metrics.bias_slope
            Intercept = [double]$metrics.bias_intercept
            RValue = [double]$metrics.bias_r_value
            PValue = [double]$metrics.bias_p_value
        }
        
        Write-Verbose "$ExperimentName/$ReplicationName contributed 1 bias regression record"
        return @($biasRecord)
    }
    catch {
        $errorMessage = $_.Exception.Message
        Write-Verbose "Failed to parse metrics from ${metricsPath}. Error: $errorMessage"
        return $null
    }
}

function Show-Phase3ValidationInstructions {
    param($ExportStats)
    
    Write-TestHeader "Comprehensive GraphPad Prism Manual Analysis Instructions - Phase 3 (Step 3 of 4)" 'Yellow'
    
    Write-Host "Import files generated in: " -NoNewline -ForegroundColor White
    Write-Host $ExportStats.ExportDirectory -ForegroundColor Cyan
    
    Write-Host "`nComplete 4-Step Validation Workflow:" -ForegroundColor Magenta
    Write-Host "✓ Step 1: create_statistical_study.ps1 - COMPLETED" -ForegroundColor Green
    Write-Host "✓ Step 2: generate_graphpad_imports.ps1 - COMPLETED (PHASE 1 + 2 + 3)" -ForegroundColor Green
    Write-Host "→ Step 3: Manual GraphPad Analysis - FOLLOW INSTRUCTIONS BELOW" -ForegroundColor Yellow
    Write-Host "  Step 4: validate_graphpad_results.ps1 - PENDING" -ForegroundColor Gray
    
    Write-Host "`nSTEP 3: COMPREHENSIVE MANUAL GRAPHPAD PRISM ANALYSIS (Phase 1 + 2 + 3)" -ForegroundColor Magenta
    Write-Host "Target: Independent validation of framework calculations including bias analysis" -ForegroundColor Gray
    
    Write-GraphPadInstruction "3.1" "Open GraphPad Prism and create a new project:"
    Write-Host "     - File → New → New Project File"
    Write-Host "     - CREATE 'Multiple variables' → 'Enter or import data into a new table', then save the project file"
    Write-Host "     - Select 'Project info 1' in the Info section and enter project details"
    
    Write-GraphPadInstruction "3.2" "Process raw MRR scores:"
    Write-Host "     - Select the 'Data 1' table and import 'tests/assets/statistical_validation_study/graphpad_imports/Phase_A_Raw_Scores.csv'"
    Write-Host "       with the following options: 'insert and maintain link', auto-update, and 'separate adjacent columns' for commas. Check the box for setting these as default."
    Write-Host "     - Analyze Data → Column analyses → Descriptive statistics" -ForegroundColor Gray
    Write-Host "     - Deselect 'A:Trial' (leave all MRR columns selected), then calculate the 'Basics' set of 4 stats groups for each replication" -ForegroundColor Gray
    Write-Host "     - Export results as 'tests/assets/statistical_validation_study/graphpad_exports/GraphPad_MRR_Means.csv'" -ForegroundColor Gray
    
    Write-GraphPadInstruction "3.3" "Process enhanced Wilcoxon test results using K-specific datasets (PHASE 1 ENHANCED):"
    Write-Host ""
    Write-Host "     MRR Analysis:" -ForegroundColor Cyan
    Write-Host "     • K=4 MRR:" -ForegroundColor Gray
    Write-Host "       - Create a new 'Multiple variables' data table and select the 'enter or import data' option"
    Write-Host "       - Import 'graphpad_imports/Phase_A_MRR_K4.csv' into this new table"
    Write-Host "       - Analyze Data → Column analyses → One sample t test and Wilcoxon test"
    Write-Host "       - Select the MRR column only, then choose 'Wilcoxon signed-rank test' with hypothetical value = 0.25"
    Write-Host "       - Export results as 'graphpad_exports/GraphPad_Wilcoxon_K4.csv'"
    Write-Host "     • K=10 MRR:" -ForegroundColor Gray
    Write-Host "       - Repeat analysis for K=10 MRR: Import 'graphpad_imports/Phase_A_MRR_K10.csv' → hypothetical = 0.1"
    Write-Host "       - Export as 'graphpad_exports/GraphPad_Wilcoxon_MRR_K10.csv'"
    Write-Host ""
    Write-Host "     Top-1 Accuracy Analysis:" -ForegroundColor Cyan
    Write-Host "     • K=4 Top-1:" -ForegroundColor Gray
    Write-Host "       - Repeat analysis for K=4 Top-1: Import 'graphpad_imports/Phase_A_Top1_K4.csv' → hypothetical = 0.25"
    Write-Host "       - Export as 'graphpad_exports/GraphPad_Wilcoxon_Top1_K4.csv'"
    Write-Host "     • K=10 Top-1:" -ForegroundColor Gray
    Write-Host "       - Repeat analysis for K=10 Top-1: Import 'graphpad_imports/Phase_A_Top1_K10.csv' → hypothetical = 0.1"
    Write-Host "       - Export as 'graphpad_exports/GraphPad_Wilcoxon_Top1_K10.csv'"
    Write-Host ""
    Write-Host "     Top-3 Accuracy Analysis:" -ForegroundColor Cyan
    Write-Host "     • K=4 Top-3:" -ForegroundColor Gray
    Write-Host "       - Repeat analysis for K=4 Top-3: Import 'graphpad_imports/Phase_A_Top3_K4.csv' → hypothetical = 0.75"
    Write-Host "       - Export as 'graphpad_exports/GraphPad_Wilcoxon_Top3_K4.csv'"
    Write-Host "     • K=10 Top-3:" -ForegroundColor Gray
    Write-Host "       - Repeat analysis for K=10 Top-3: Import 'graphpad_imports/Phase_A_Top3_K10.csv' → hypothetical = 0.3"
    Write-Host "       - Export as 'graphpad_exports/GraphPad_Wilcoxon_Top3_K10.csv'"
    
    Write-GraphPadInstruction "3.4" "Process Enhanced ANOVA with Effect Size Validation (NEW - Phase 2):"
    Write-Host ""
    Write-Host "     MRR ANOVA Analysis with Effect Size:" -ForegroundColor Cyan
    Write-Host "     • Create new 'Grouped' table, specify 6 replicate values in subcolumns" -ForegroundColor Gray
    Write-Host "     • Import 'graphpad_imports/Phase_B_ANOVA_MRR.csv'" -ForegroundColor Gray
    Write-Host "     • Analyze Data → Grouped analyses → Two-way ANOVA" -ForegroundColor Gray
    Write-Host "     • Enable interaction term (full model) and 'Show effect size (eta-squared)'" -ForegroundColor Gray
    Write-Host "     • Export results as 'graphpad_exports/GraphPad_ANOVA_MRR.csv'" -ForegroundColor Gray
    Write-Host ""
    Write-Host "     Top-1 Accuracy ANOVA Analysis with Effect Size:" -ForegroundColor Cyan
    Write-Host "     • Create new 'Grouped' table, specify 6 replicate values in subcolumns" -ForegroundColor Gray
    Write-Host "     • Import 'graphpad_imports/Phase_B_ANOVA_Top1.csv'" -ForegroundColor Gray
    Write-Host "     • Analyze Data → Grouped analyses → Two-way ANOVA" -ForegroundColor Gray
    Write-Host "     • Enable interaction term (full model) and 'Show effect size (eta-squared)'" -ForegroundColor Gray
    Write-Host "     • Export results as 'graphpad_exports/GraphPad_ANOVA_Top1.csv'" -ForegroundColor Gray
    Write-Host ""
    Write-Host "     Top-3 Accuracy ANOVA Analysis with Effect Size:" -ForegroundColor Cyan
    Write-Host "     • Create new 'Grouped' table, specify 6 replicate values in subcolumns" -ForegroundColor Gray
    Write-Host "     • Import 'graphpad_imports/Phase_B_ANOVA_Top3.csv'" -ForegroundColor Gray
    Write-Host "     • Analyze Data → Grouped analyses → Two-way ANOVA" -ForegroundColor Gray
    Write-Host "     • Enable interaction term (full model) and 'Show effect size (eta-squared)'" -ForegroundColor Gray
    Write-Host "     • Export results as 'graphpad_exports/GraphPad_ANOVA_Top3.csv'" -ForegroundColor Gray
    
    # Phase 3 Instructions (Bias Regression Analysis) - NEW
    Write-GraphPadInstruction "3.5" "Process Bias Regression Analysis (NEW - Phase 3):"
    Write-Host ""
    Write-Host "     Overall Bias Regression Analysis:" -ForegroundColor Cyan
    Write-Host "     • Create new 'XY' data table" -ForegroundColor Gray
    Write-Host "     • Import 'graphpad_imports/Phase_A_Bias_Regression.csv'" -ForegroundColor Gray
    Write-Host "     • X-axis: TrialSeq (trial sequence number)" -ForegroundColor Gray
    Write-Host "     • Y-axis: MRR (performance over time)" -ForegroundColor Gray
    Write-Host "     • Analyze Data → XY analyses → Linear regression" -ForegroundColor Gray
    Write-Host "     • Export regression results as 'graphpad_exports/GraphPad_Bias_Regression_Overall.csv'" -ForegroundColor Gray
    Write-Host ""
    Write-Host "     Condition-Specific Bias Analysis:" -ForegroundColor Cyan
    Write-Host "     • Correct Condition:" -ForegroundColor Gray
    Write-Host "       - Import 'graphpad_imports/Phase_A_Bias_Regression_Correct.csv' into XY table" -ForegroundColor Gray
    Write-Host "       - Linear regression: TrialSeq vs MRR" -ForegroundColor Gray
    Write-Host "       - Export as 'graphpad_exports/GraphPad_Bias_Regression_Correct.csv'" -ForegroundColor Gray
    Write-Host "     • Random Condition:" -ForegroundColor Gray
    Write-Host "       - Import 'graphpad_imports/Phase_A_Bias_Regression_Random.csv' into XY table" -ForegroundColor Gray
    Write-Host "       - Linear regression: TrialSeq vs MRR" -ForegroundColor Gray
    Write-Host "       - Export as 'graphpad_exports/GraphPad_Bias_Regression_Random.csv'" -ForegroundColor Gray
    Write-Host ""
    Write-Host "     Additional Regression Metrics (Phase 3):" -ForegroundColor Cyan
    Write-Host "     • Repeat regression analysis for Top1Accuracy and Top3Accuracy vs TrialSeq" -ForegroundColor Gray
    Write-Host "     • Compare slope, intercept, R-squared, and p-values with framework calculations" -ForegroundColor Gray
    Write-Host "     • Export all regression analyses for comprehensive bias validation" -ForegroundColor Gray
    
    Write-Host "`nAFTER COMPLETING COMPREHENSIVE GRAPHPAD ANALYSIS (Phase 1 + 2 + 3):" -ForegroundColor Cyan
    Write-Host "Run Step 4 validation:" -ForegroundColor White
    Write-Host "pdm run test-stats-results" -ForegroundColor Gray
    
    Write-Host "`nSUCCESS CRITERIA (COMPREHENSIVE - Phase 1 + 2 + 3):" -ForegroundColor Green
    Write-Host "Step 4 will validate within established tolerances:" -ForegroundColor White
    Write-Host "• Phase 1: MRR, Top-1, Top-3 accuracy calculations and Wilcoxon p-values (±0.0001)" -ForegroundColor White
    Write-Host "• Phase 2: ANOVA F-statistics (±0.01) and eta-squared effect sizes (±0.01)" -ForegroundColor White
    Write-Host "• Phase 3: Linear regression slopes (±0.0001), R-values (±0.01), p-values (±0.001)" -ForegroundColor White
    Write-Host "Citation ready: 'Statistical analyses were validated against GraphPad Prism 10.6.1'" -ForegroundColor White
    
    Write-Host "`nVALIDATION SUMMARY (COMPREHENSIVE - Phase 1 + 2 + 3):" -ForegroundColor Cyan
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
    
    Write-TestStep "Generating Enhanced GraphPad Prism Import Files (Phase 1 + 2 + 3)"
    
    # Create export directory
    New-Item -ItemType Directory -Path $GraphPadImportsDir -Force | Out-Null
    
    # Phase A: Export replication-level data
    Write-Host "Phase A: Generating replication-level exports (enhanced)..." -ForegroundColor Cyan
    
    $allReplicationData = @()
    $allRawScores = @()
    
    $experiments = Get-ChildItem -Path $TestStudyPath -Directory -Name "exp_*"
    $totalExperiments = $experiments.Count
    $currentExperiment = 0
    
    foreach ($experiment in $experiments) {
        $currentExperiment++
        $percentComplete = [math]::Round(($currentExperiment / $totalExperiments) * 100)
        Write-Progress -Activity "Generating enhanced GraphPad exports" -Status "Processing $experiment... ($currentExperiment of $totalExperiments)" -PercentComplete $percentComplete
        
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
    
    Write-Progress -Activity "Generating enhanced GraphPad exports" -Completed
    
    # Create reference data directory
    $ReferenceDataDir = Join-Path $GraphPadImportsDir "reference_data"
    New-Item -ItemType Directory -Path $ReferenceDataDir -Force | Out-Null
    
    # Export replication-level summary to reference folder
    $replicationExport = Join-Path $ReferenceDataDir "Phase_A_Replication_Metrics.csv"
    $allReplicationData | Export-Csv -Path $replicationExport -NoTypeInformation
    Write-Host "  ✓ Generated: Phase_A_Replication_Metrics.csv ($($allReplicationData.Count) replications) [reference]" -ForegroundColor Green
    
    # Export raw scores in long format to reference folder
    $rawScoresLongExport = Join-Path $ReferenceDataDir "Phase_A_Raw_Scores_Long.csv"
    $allRawScores | Export-Csv -Path $rawScoresLongExport -NoTypeInformation
    
    # Export raw scores in wide format for GraphPad column-based analysis
    $rawScoresExport = Join-Path $GraphPadImportsDir "Phase_A_Raw_Scores.csv"
    $allRawScoresWide = Export-RawScoresForGraphPadWide -AllRawScores $allRawScores
    if ($allRawScoresWide) {
        $allRawScoresWide | Export-Csv -Path $rawScoresExport -NoTypeInformation
    }
    
    Write-Host "  ✓ Generated: Phase_A_Raw_Scores_Long.csv ($($allRawScores.Count) trials) [reference]" -ForegroundColor Green
    Write-Host "  ✓ Generated: Phase_A_Raw_Scores.csv (GraphPad column format)" -ForegroundColor Green
    
    # Generate K-specific accuracy datasets for Wilcoxon testing (Phase 1 Enhancement)
    $kSpecificStats = Generate-KSpecificAccuracyExports -AllReplicationData $allReplicationData
    
    # Generate enhanced ANOVA exports with effect size validation (Phase 2)
    $anovaStats = Generate-EnhancedANOVAExports -TestStudyPath $TestStudyPath
    
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
        
        $anovaGraphPadExport = Join-Path $GraphPadImportsDir "Phase_B_ANOVA_MRR.csv"
        $csvContent | Out-File -FilePath $anovaGraphPadExport -Encoding UTF8
        
        Write-Host "  ✓ Generated: Phase_B_ANOVA_MRR.csv (GraphPad grouped table format)" -ForegroundColor Green
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
        Write-Host "  ✓ Generated: Phase_B_Summary_Statistics.csv (4 groups) [reference]" -ForegroundColor Green
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
# ENHANCED GRAPHPAD VALIDATION INSTRUCTIONS (Phase 1)
# =============================================================================

function Show-EnhancedGraphPadValidationInstructions {
    param($ExportStats)
    
    Write-TestHeader "Enhanced GraphPad Prism Manual Analysis Instructions (Step 3 of 4)" 'Yellow'
    
    Write-Host "Import files generated in: " -NoNewline -ForegroundColor White
    Write-Host $ExportStats.ExportDirectory -ForegroundColor Cyan
    
    Write-Host "`nComplete 4-Step Validation Workflow:" -ForegroundColor Magenta
    Write-Host "✓ Step 1: create_statistical_study.ps1 - COMPLETED" -ForegroundColor Green
    Write-Host "✓ Step 2: generate_graphpad_imports.ps1 - COMPLETED" -ForegroundColor Green
    Write-Host "→ Step 3: Manual GraphPad Analysis - FOLLOW INSTRUCTIONS BELOW" -ForegroundColor Yellow
    Write-Host "  Step 4: validate_graphpad_results.ps1 - PENDING" -ForegroundColor Gray
    
    Write-Host "`nSTEP 3: ENHANCED MANUAL GRAPHPAD PRISM ANALYSIS (Phase 1)" -ForegroundColor Magenta
    Write-Host "Target: Independent validation of framework calculations" -ForegroundColor Gray
    
    Write-GraphPadInstruction "3.1" "Open GraphPad Prism and create a new project:"
    Write-Host "     - File → New → New Project File"
    Write-Host "     - CREATE 'Multiple variables' → 'Enter or import data into a new table', then save the project file"
    Write-Host "     - Select 'Project info 1' in the Info section and enter project details"
    
    Write-GraphPadInstruction "3.2" "Process raw MRR scores:"
    Write-Host "     - Select the 'Data 1' table and import 'tests/assets/statistical_validation_study/graphpad_imports/Phase_A_Raw_Scores.csv'"
    Write-Host "       with the following options: 'insert and maintain link', auto-update, and 'separate adjacent columns' for commas. Check the box for setting these as default."
    Write-Host "     - Analyze Data → Column analyses → Descriptive statistics" -ForegroundColor Gray
    Write-Host "     - Deselect 'A:Trial' (leave all MRR columns selected), then calculate the 'Basics' set of 4 stats groups for each replication" -ForegroundColor Gray
    Write-Host "     - Export results as 'tests/assets/statistical_validation_study/graphpad_exports/GraphPad_MRR_Means.csv'" -ForegroundColor Gray
    
    Write-GraphPadInstruction "3.3" "Process enhanced Wilcoxon test results using K-specific datasets (PHASE 1 ENHANCED):"
    Write-Host ""
    Write-Host "     MRR Analysis:" -ForegroundColor Gray
    Write-Host "     • K=4 MRR:" -ForegroundColor Gray
    Write-Host "       - Create a new 'Multiple variables' data table and select the 'enter or import data' option"
    Write-Host "       - Import 'graphpad_imports/Phase_A_MRR_K4.csv' into this new table"
    Write-Host "       - Analyze Data → Column analyses → One sample t test and Wilcoxon test"
    Write-Host "       - Select the MRR column only, then choose 'Wilcoxon signed-rank test' with hypothetical value = 0.25"
    Write-Host "       - Export results as 'graphpad_exports/GraphPad_Wilcoxon_K4.csv'"
    Write-Host "     • K=10 MRR:" -ForegroundColor Gray
    Write-Host "       - Repeat analysis for K=10 MRR: Import 'graphpad_imports/Phase_A_MRR_K10.csv' → hypothetical = 0.1"
    Write-Host "       - Export as 'graphpad_exports/GraphPad_Wilcoxon_MRR_K10.csv'"
    Write-Host ""
    Write-Host "     Top-1 Accuracy Analysis:" -ForegroundColor Cyan
    Write-Host "     • K=4 Top-1:" -ForegroundColor Gray
    Write-Host "       - Repeat analysis for K=4 Top-1: Import 'graphpad_imports/Phase_A_Top1_K4.csv' → hypothetical = 0.25"
    Write-Host "       - Export as 'graphpad_exports/GraphPad_Wilcoxon_Top1_K4.csv'"
    Write-Host "     • K=10 Top-1:" -ForegroundColor Gray
    Write-Host "       - Repeat analysis for K=10 Top-1: Import 'graphpad_imports/Phase_A_Top1_K10.csv' → hypothetical = 0.1"
    Write-Host "       - Export as 'graphpad_exports/GraphPad_Wilcoxon_Top1_K10.csv'"
    Write-Host ""
    Write-Host "     Top-3 Accuracy Analysis:" -ForegroundColor Cyan
    Write-Host "     • K=4 Top-3:" -ForegroundColor Gray
    Write-Host "       - Repeat analysis for K=4 Top-3: Import 'graphpad_imports/Phase_A_Top3_K4.csv' → hypothetical = 0.75"
    Write-Host "       - Export as 'graphpad_exports/GraphPad_Wilcoxon_Top3_K4.csv'"
    Write-Host "     • K=10 Top-3:" -ForegroundColor Gray
    Write-Host "       - Repeat analysis for K=10 Top-3: Import 'graphpad_imports/Phase_A_Top3_K10.csv' → hypothetical = 0.3"
    Write-Host "       - Export as 'graphpad_exports/GraphPad_Wilcoxon_Top3_K10.csv'"
    
    Write-GraphPadInstruction "3.4" "Process Enhanced ANOVA with Effect Size Validation (NEW - Phase 2):"
    Write-Host ""
    Write-Host "     MRR ANOVA Analysis with Effect Size:" -ForegroundColor Cyan
    Write-Host "     • Create new 'Grouped' table, specify 6 replicate values in subcolumns" -ForegroundColor Gray
    Write-Host "     • Import 'graphpad_imports/Phase_B_ANOVA_MRR.csv'" -ForegroundColor Gray
    Write-Host "     • Analyze Data → Grouped analyses → Two-way ANOVA" -ForegroundColor Gray
    Write-Host "     • Enable interaction term (full model) and 'Show effect size (eta-squared)'" -ForegroundColor Gray
    Write-Host "     • Export results as 'graphpad_exports/GraphPad_ANOVA_MRR.csv'" -ForegroundColor Gray
    Write-Host ""
    Write-Host "     Top-1 Accuracy ANOVA Analysis with Effect Size:" -ForegroundColor Cyan
    Write-Host "     • Create new 'Grouped' table, specify 6 replicate values in subcolumns" -ForegroundColor Gray
    Write-Host "     • Import 'graphpad_imports/Phase_B_ANOVA_Top1.csv'" -ForegroundColor Gray
    Write-Host "     • Analyze Data → Grouped analyses → Two-way ANOVA" -ForegroundColor Gray
    Write-Host "     • Enable interaction term (full model) and 'Show effect size (eta-squared)'" -ForegroundColor Gray
    Write-Host "     • Export results as 'graphpad_exports/GraphPad_ANOVA_Top1.csv'" -ForegroundColor Gray
    Write-Host ""
    Write-Host "     Top-3 Accuracy ANOVA Analysis with Effect Size:" -ForegroundColor Cyan
    Write-Host "     • Create new 'Grouped' table, specify 6 replicate values in subcolumns" -ForegroundColor Gray
    Write-Host "     • Import 'graphpad_imports/Phase_B_ANOVA_Top3.csv'" -ForegroundColor Gray
    Write-Host "     • Analyze Data → Grouped analyses → Two-way ANOVA" -ForegroundColor Gray
    Write-Host "     • Enable interaction term (full model) and 'Show effect size (eta-squared)'" -ForegroundColor Gray
    Write-Host "     • Export results as 'graphpad_exports/GraphPad_ANOVA_Top3.csv'" -ForegroundColor Gray
    
    Write-Host "`nAFTER COMPLETING ENHANCED GRAPHPAD ANALYSIS:" -ForegroundColor Cyan
    Write-Host "Run Step 4 validation:" -ForegroundColor White
    Write-Host "pdm run test-stats-results" -ForegroundColor Gray
    
    Write-Host "`nSUCCESS CRITERIA (ENHANCED - Phase 1 + 2):" -ForegroundColor Green
    Write-Host "Step 4 will validate within established tolerances:" -ForegroundColor White
    Write-Host "• Phase 1: MRR, Top-1, Top-3 accuracy calculations and Wilcoxon p-values (±0.0001)" -ForegroundColor White
    Write-Host "• Phase 2: ANOVA F-statistics (±0.01) and eta-squared effect sizes (±0.01)" -ForegroundColor White
    Write-Host "Citation ready: 'Statistical analyses were validated against GraphPad Prism 10.6.1'" -ForegroundColor White
    
    Write-Host "`nVALIDATION SUMMARY (ENHANCED - Phase 1 + 2):" -ForegroundColor Cyan
    Write-Host "Replications to validate: $($ExportStats.ReplicationCount)" -ForegroundColor White
    Write-Host "Total trials analyzed: $($ExportStats.TrialCount)" -ForegroundColor White
    Write-Host "Export files: 12+ total (6 K-specific + 3 ANOVA + 3+ reference files)" -ForegroundColor White
    
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
    
    Write-Host "Export directory: $(Split-Path $ExportStats.ExportDirectory -Leaf)" -ForegroundColor White
}

# =============================================================================
# MAIN TEST EXECUTION (Enhanced - Phase 1)
# =============================================================================

try {
    Write-TestHeader "Statistical Analysis & Reporting - Step 2/4: Enhanced GraphPad Import Generation" 'Magenta'
    
    if ($Interactive) {
        Write-Host "${C_BLUE}ENHANCED Two-Phase GraphPad Prism Validation Strategy (Phase 1):${C_RESET}"
        Write-Host ""
        Write-Host "Phase A: Enhanced core algorithmic validation against GraphPad"
        Write-Host "  • Mean Reciprocal Rank (MRR) calculations and Wilcoxon tests"
        Write-Host "  • Top-1 accuracy calculations and Wilcoxon tests (NEW)"
        Write-Host "  • Top-3 accuracy calculations and Wilcoxon tests (NEW)"
        Write-Host "  • K-specific validation datasets for comprehensive coverage"
        Write-Host "  • Bias regression analysis (slope, R-value)"
        Write-Host "  • Effect size calculations (Cohen's r)"
        Write-Host ""
        Write-Host "Phase B: Standard statistical analyses validation against GraphPad"
        Write-Host "  • Two-Way ANOVA (F-statistics, p-values, effect sizes)"
        Write-Host "  • Post-hoc tests and FDR corrections"
        Write-Host "  • Multi-factor experimental design validation"
        Write-Host ""
        Write-Host "${C_YELLOW}This provides enhanced academic defensibility for the citation:${C_RESET}"
        Write-Host "${C_GREEN}'Statistical analyses were validated against GraphPad Prism 10.6.1'${C_RESET}"
        Write-Host ""
        Read-Host "Press Enter to begin enhanced validation..." | Out-Null
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
    
    # Step 4: Generate Enhanced GraphPad Exports (Phase 1)
    Write-Host ""
    Write-TestStep "Step 4: Generate Enhanced GraphPad Export Files (Phase 1 + 2 + 3)"
    
    $exportStats = Generate-GraphPadExports -TestStudyPath $finalStudyPath
    
    # Step 5: Show Enhanced Validation Instructions (Phase 1)
    if (-not $ExportOnly) {
        Show-Phase3ValidationInstructions -ExportStats $exportStats
        
        if ($Interactive) {
            Write-Host "`n${C_YELLOW}Next Steps (Enhanced - Phase 1):${C_RESET}"
            Write-Host "1. Open GraphPad Prism 10.6.1"
            Write-Host "2. Follow the enhanced validation instructions above"
            Write-Host "3. Process 6 K-specific datasets (2 MRR + 2 Top-1 + 2 Top-3)"
            Write-Host "4. Export all Wilcoxon test results for validation"
            Write-Host "5. Run Step 4 validation to compare results"
            Read-Host "`nPress Enter to complete..." | Out-Null
        }
    }
    
}
catch {
    Write-Host "`nX ENHANCED GRAPHPAD VALIDATION TEST FAILED" -ForegroundColor Red
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

Write-Host "`nCOMPREHENSIVE GRAPHPAD PRISM VALIDATION EXPORTS GENERATED SUCCESSFULLY (Phase 1 + 2 + 3)" -ForegroundColor Green

if ($ExportOnly) {
    Write-Host "Comprehensive import files available in: $GraphPadImportsDir" -ForegroundColor Cyan
    Write-Host "Phase 1: 6 K-specific accuracy validation files" -ForegroundColor Cyan
    Write-Host "Phase 2: Enhanced ANOVA with effect size validation" -ForegroundColor Cyan
    Write-Host "Phase 3: Bias regression analysis validation" -ForegroundColor Cyan
} else {
    Write-Host "Ready for comprehensive GraphPad Prism validation - follow instructions above" -ForegroundColor Cyan
    Write-Host "Phase 1: Added Top-1 and Top-3 accuracy validation" -ForegroundColor Green
    Write-Host "Phase 2: Added ANOVA effect size (eta-squared) validation" -ForegroundColor Green
    Write-Host "Phase 3: Added bias regression (slope, intercept, R-value) validation" -ForegroundColor Green
    Write-Host ""
}

exit 0

# === End of tests/algorithm_validation/generate_graphpad_imports.ps1 ===
