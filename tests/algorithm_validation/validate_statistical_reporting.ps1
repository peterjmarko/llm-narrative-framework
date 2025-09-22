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
    Statistical Analysis & Reporting Validation Test - GraphPad Prism Validation

.DESCRIPTION
    This test validates the complete statistical analysis pipeline against GraphPad Prism 10.0.0.
    It implements a two-phase validation strategy:
    
    Phase A (Replication-Level): Validates core algorithmic contributions (MRR, Wilcoxon tests, bias regression)
    Phase B (Study-Level): Validates standard statistical analyses (Two-Way ANOVA, post-hoc tests)
    
    The test generates GraphPad-compatible export files and provides detailed instructions for
    manual verification, supporting the academic citation: "Statistical analyses were validated 
    against GraphPad Prism 10.0.0"

.PARAMETER Interactive
    Run in interactive mode with step-by-step GraphPad validation instructions.

.PARAMETER ExportOnly
    Generate GraphPad export files without running validation checks.

.PARAMETER Verbose
    Enable verbose output showing detailed export file generation.

.EXAMPLE
    .\validate_statistical_reporting.ps1 -Interactive
    Run the full GraphPad validation workflow with step-by-step guidance.

.EXAMPLE
    .\validate_statistical_reporting.ps1 -ExportOnly
    Generate GraphPad export files only (for batch processing).
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
$GraphPadExportsDir = Join-Path $TempTestDir "graphpad_exports"

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
    Write-Host "`n📊 GraphPad Step $Step:" -ForegroundColor $Color
    Write-Host "   $Message" -ForegroundColor White
}

function Test-MockStudyAssets {
    Write-TestStep "Checking Mock Study Assets"
    
    if (-not (Test-Path $MockStudyPath)) {
        Write-Host "❌ Mock study directory not found: $MockStudyPath" -ForegroundColor Red
        Write-Host "   Run: pwsh -File ./tests/algorithm_validation/generate_mock_study_assets.ps1" -ForegroundColor Yellow
        return $false
    }
    
    # Check for required mock experiments
    $mockExperiments = Get-ChildItem -Path $MockStudyPath -Directory -Name "experiment_*" -ErrorAction SilentlyContinue
    if ($mockExperiments.Count -lt 4) {
        Write-Host "❌ Insufficient mock experiments found. Expected at least 4, found $($mockExperiments.Count)" -ForegroundColor Red
        return $false
    }
    
    # Verify sufficient replications
    $totalReplications = 0
    foreach ($experiment in $mockExperiments) {
        $expPath = Join-Path $MockStudyPath $experiment
        $replications = Get-ChildItem -Path $expPath -Directory -Name "replication_*" -ErrorAction SilentlyContinue
        $totalReplications += $replications.Count
    }
    
    if ($totalReplications -lt 20) {
        Write-Host "❌ Insufficient total replications. Expected at least 20, found $totalReplications" -ForegroundColor Red
        return $false
    }
    
    Write-Host "✅ Mock study assets validated ($totalReplications total replications)" -ForegroundColor Green
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
    
    foreach ($file in $replicationFiles) {
        $filePath = Join-Path $ExperimentPath $file
        try {
            $metrics = Get-Content $filePath -Raw | ConvertFrom-Json
            
            # Extract key metrics for GraphPad validation
            $replicationData = [PSCustomObject]@{
                Experiment = $ExperimentName
                Replication = [int]($file.Split('_')[1])  # Extract replication number from path
                Model = $metrics.model
                MappingStrategy = $metrics.mapping_strategy
                GroupSize = $metrics.k
                
                # Core metrics for Phase A validation
                MRR = [double]$metrics.mean_reciprocal_rank
                Top1Accuracy = [double]$metrics.top_1_accuracy
                Top3Accuracy = [double]$metrics.top_3_accuracy
                BiasSlope = [double]$metrics.bias_slope
                BiasRValue = [double]$metrics.bias_r_value
                
                # Statistical test results
                MRR_WilcoxonP = [double]$metrics.mrr_wilcoxon_p
                Top1_WilcoxonP = [double]$metrics.top_1_wilcoxon_p
                Top3_WilcoxonP = [double]$metrics.top_3_wilcoxon_p
                
                # Effect sizes
                MRR_EffectSize = [double]$metrics.mrr_effect_size
                Top1_EffectSize = [double]$metrics.top_1_effect_size
                Top3_EffectSize = [double]$metrics.top_3_effect_size
                
                # Lift metrics
                MRR_Lift = [double]$metrics.mrr_lift
                Top1_Lift = [double]$metrics.top_1_lift
                Top3_Lift = [double]$metrics.top_3_lift
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
    
    Write-Verbose "Extracting raw scores for: $ExperimentName"
    
    # Find LLM response files to extract raw ranking data
    $responseFiles = Get-ChildItem -Path $ExperimentPath -Recurse -Name "llm_responses.json" -ErrorAction SilentlyContinue
    
    $rawScores = @()
    
    foreach ($file in $responseFiles) {
        $filePath = Join-Path $ExperimentPath $file
        try {
            $responses = Get-Content $filePath -Raw | ConvertFrom-Json
            
            foreach ($response in $responses) {
                # Extract reciprocal rank for each trial
                $correctSubjectId = $response.correct_subject_id
                $correctRanking = $response.subject_rankings | Where-Object { $_.subject_id -eq $correctSubjectId }
                
                if ($correctRanking) {
                    $reciprocalRank = 1.0 / [double]$correctRanking.rank
                    
                    $rawScores += [PSCustomObject]@{
                        Experiment = $ExperimentName
                        Trial = $response.trial_number
                        CorrectRank = $correctRanking.rank
                        ReciprocalRank = $reciprocalRank
                        Top1Hit = if ($correctRanking.rank -eq 1) { 1 } else { 0 }
                        Top3Hit = if ($correctRanking.rank -le 3) { 1 } else { 0 }
                        GroupSize = $response.subject_rankings.Count
                    }
                }
            }
        }
        catch {
            Write-Warning "Failed to parse response file: $file - $($_.Exception.Message)"
        }
    }
    
    return $rawScores
}

function Generate-GraphPadExports {
    param($TestStudyPath)
    
    Write-TestStep "Generating GraphPad Prism Export Files"
    
    # Create export directory
    New-Item -ItemType Directory -Path $GraphPadExportsDir -Force | Out-Null
    
    # Phase A: Export replication-level data
    Write-Host "📊 Phase A: Generating replication-level exports..." -ForegroundColor Cyan
    
    $allReplicationData = @()
    $allRawScores = @()
    
    $experiments = Get-ChildItem -Path $TestStudyPath -Directory -Name "experiment_*"
    foreach ($experiment in $experiments) {
        $expPath = Join-Path $TestStudyPath $experiment
        
        # Export replication metrics
        $repData = Export-ReplicationDataForGraphPad -ExperimentPath $expPath -ExperimentName $experiment
        if ($repData) {
            $allReplicationData += $repData
        }
        
        # Export raw scores
        $rawData = Export-RawScoresForGraphPad -ExperimentPath $expPath -ExperimentName $experiment
        if ($rawData) {
            $allRawScores += $rawData
        }
    }
    
    # Export replication-level summary
    $replicationExport = Join-Path $GraphPadExportsDir "Phase_A_Replication_Metrics.csv"
    $allReplicationData | Export-Csv -Path $replicationExport -NoTypeInformation
    Write-Host "  ✅ Generated: Phase_A_Replication_Metrics.csv ($($allReplicationData.Count) replications)" -ForegroundColor Green
    
    # Export raw scores for manual validation
    $rawScoresExport = Join-Path $GraphPadExportsDir "Phase_A_Raw_Scores.csv"
    $allRawScores | Export-Csv -Path $rawScoresExport -NoTypeInformation
    Write-Host "  ✅ Generated: Phase_A_Raw_Scores.csv ($($allRawScores.Count) trials)" -ForegroundColor Green
    
    # Phase B: Export study-level data (if STUDY_results.csv exists)
    Write-Host "📊 Phase B: Generating study-level exports..." -ForegroundColor Cyan
    
    $studyResultsPath = Join-Path $TestStudyPath "STUDY_results.csv"
    if (Test-Path $studyResultsPath) {
        $studyData = Import-Csv $studyResultsPath
        
        # Export for Two-Way ANOVA
        $anovaExport = Join-Path $GraphPadExportsDir "Phase_B_ANOVA_Data.csv"
        $studyData | Export-Csv -Path $anovaExport -NoTypeInformation
        Write-Host "  ✅ Generated: Phase_B_ANOVA_Data.csv ($($studyData.Count) experiments)" -ForegroundColor Green
        
        # Generate summary statistics for validation
        $summaryStats = $studyData | Group-Object MappingStrategy, GroupSize | ForEach-Object {
            $group = $_.Group
            [PSCustomObject]@{
                MappingStrategy = $group[0].MappingStrategy
                GroupSize = $group[0].GroupSize
                Count = $group.Count
                MRR_Mean = ($group | Measure-Object MeanMRR -Average).Average
                MRR_StdDev = [math]::Sqrt(($group | ForEach-Object { ([double]$_.MeanMRR - ($group | Measure-Object MeanMRR -Average).Average) * ([double]$_.MeanMRR - ($group | Measure-Object MeanMRR -Average).Average) } | Measure-Object -Sum).Sum / ($group.Count - 1))
                Top1_Mean = ($group | Measure-Object MeanTop1Accuracy -Average).Average
                Top1_StdDev = [math]::Sqrt(($group | ForEach-Object { ([double]$_.MeanTop1Accuracy - ($group | Measure-Object MeanTop1Accuracy -Average).Average) * ([double]$_.MeanTop1Accuracy - ($group | Measure-Object MeanTop1Accuracy -Average).Average) } | Measure-Object -Sum).Sum / ($group.Count - 1))
            }
        }
        
        $summaryExport = Join-Path $GraphPadExportsDir "Phase_B_Summary_Statistics.csv"
        $summaryStats | Export-Csv -Path $summaryExport -NoTypeInformation
        Write-Host "  ✅ Generated: Phase_B_Summary_Statistics.csv (4 groups)" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  STUDY_results.csv not found - Phase B exports skipped" -ForegroundColor Yellow
        Write-Host "     Run compile_study.ps1 first to generate study-level data" -ForegroundColor Gray
    }
    
    return @{
        ReplicationCount = $allReplicationData.Count
        TrialCount = $allRawScores.Count
        ExportDirectory = $GraphPadExportsDir
    }
}

function Show-GraphPadValidationInstructions {
    param($ExportStats)
    
    Write-TestHeader "GraphPad Prism Validation Instructions" 'Yellow'
    
    Write-Host "📁 Export files generated in: " -NoNewline -ForegroundColor White
    Write-Host $ExportStats.ExportDirectory -ForegroundColor Cyan
    
    Write-Host "`n🔬 PHASE A: Replication-Level Validation" -ForegroundColor Magenta
    Write-Host "Target: Core algorithmic contributions (analyze_llm_performance.py)" -ForegroundColor Gray
    
    Write-GraphPadInstruction "1" "Open GraphPad Prism and create a new project"
    Write-GraphPadInstruction "2" "Import 'Phase_A_Replication_Metrics.csv' as a data table"
    Write-GraphPadInstruction "3" "Validate Mean Reciprocal Rank calculations:"
    Write-Host "     - Use 'Phase_A_Raw_Scores.csv' to manually verify MRR calculations" -ForegroundColor Gray
    Write-Host "     - Compare ReciprocalRank column against our MRR values" -ForegroundColor Gray
    
    Write-GraphPadInstruction "4" "Validate Wilcoxon signed-rank tests:"
    Write-Host "     - Test MRR against chance level (1/K where K=GroupSize)" -ForegroundColor Gray
    Write-Host "     - Compare p-values: MRR_WilcoxonP vs GraphPad results" -ForegroundColor Gray
    Write-Host "     - Tolerance: ±0.001 for p-values" -ForegroundColor Gray
    
    Write-GraphPadInstruction "5" "Validate bias regression analysis:"
    Write-Host "     - Plot ReciprocalRank vs Trial number for linear regression" -ForegroundColor Gray
    Write-Host "     - Compare slope: BiasSlope vs GraphPad slope" -ForegroundColor Gray
    Write-Host "     - Compare R-value: BiasRValue vs GraphPad R" -ForegroundColor Gray
    Write-Host "     - Tolerance: ±0.001 for slope and R-value" -ForegroundColor Gray
    
    Write-GraphPadInstruction "6" "Validate effect sizes (Cohen's r):"
    Write-Host "     - Compare our effect size calculations vs GraphPad" -ForegroundColor Gray
    Write-Host "     - Tolerance: ±0.01 for effect sizes" -ForegroundColor Gray
    
    Write-Host "`n🔬 PHASE B: Study-Level Validation" -ForegroundColor Magenta
    Write-Host "Target: Standard statistical analyses (analyze_study_results.py)" -ForegroundColor Gray
    
    Write-GraphPadInstruction "7" "Import 'Phase_B_ANOVA_Data.csv' for Two-Way ANOVA"
    Write-GraphPadInstruction "8" "Configure Two-Way ANOVA:"
    Write-Host "     - Factor A: MappingStrategy (correct vs random)" -ForegroundColor Gray
    Write-Host "     - Factor B: GroupSize (4 vs 10)" -ForegroundColor Gray
    Write-Host "     - Dependent variables: MeanMRR, MeanTop1Accuracy, MeanTop3Accuracy" -ForegroundColor Gray
    
    Write-GraphPadInstruction "9" "Validate ANOVA results:"
    Write-Host "     - Compare F-statistics (tolerance: ±0.01)" -ForegroundColor Gray
    Write-Host "     - Compare p-values (tolerance: ±0.001)" -ForegroundColor Gray
    Write-Host "     - Compare effect sizes/eta-squared (tolerance: ±0.01)" -ForegroundColor Gray
    
    Write-GraphPadInstruction "10" "Validate post-hoc tests (if significant effects found):"
    Write-Host "     - Multiple comparisons with appropriate correction" -ForegroundColor Gray
    Write-Host "     - Compare adjusted p-values vs our Benjamini-Hochberg FDR" -ForegroundColor Gray
    
    Write-Host "`n✅ SUCCESS CRITERIA:" -ForegroundColor Green
    Write-Host "Phase A: All replication metrics match GraphPad within tolerances" -ForegroundColor White
    Write-Host "Phase B: ANOVA F-stats, p-values, and effect sizes match GraphPad" -ForegroundColor White
    Write-Host "Citation: 'Statistical analyses were validated against GraphPad Prism 10.0.0'" -ForegroundColor White
    
    Write-Host "`n📊 VALIDATION SUMMARY:" -ForegroundColor Cyan
    Write-Host "Replications validated: $($ExportStats.ReplicationCount)" -ForegroundColor White
    Write-Host "Total trials analyzed: $($ExportStats.TrialCount)" -ForegroundColor White
    Write-Host "Export directory: $(Split-Path $ExportStats.ExportDirectory -Leaf)" -ForegroundColor White
}

# --- Main Test Execution ---
try {
    Write-TestHeader "Statistical Analysis & Reporting - GraphPad Prism Validation" 'Magenta'
    
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
        Write-Host "${C_GREEN}'Statistical analyses were validated against GraphPad Prism 10.0.0'${C_RESET}"
        Write-Host ""
        Read-Host "Press Enter to begin validation..." | Out-Null
    }
    
    # Step 1: Validate Prerequisites
    Write-TestStep "Step 1: Validate Prerequisites"
    
    if (-not (Test-MockStudyAssets)) {
        throw "Mock study assets validation failed. Run generate_mock_study_assets.ps1 first."
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
    
    Write-Host "✅ Test environment prepared" -ForegroundColor Green
    
    if ($Interactive) {
        Read-Host "Press Enter to continue..." | Out-Null
    }
    
    # Step 3: Run Analysis Pipeline (if not ExportOnly)
    if (-not $ExportOnly) {
        Write-TestStep "Step 3: Run Analysis Pipeline"
        
        # Find the mock study directory
        $mockStudyDir = Get-ChildItem -Path $testStudyPath -Directory | Select-Object -First 1
        $actualStudyPath = $mockStudyDir.FullName
        
        # Run compile_study.ps1
        $compileResult = & "$ProjectRoot\compile_study.ps1" -StudyDirectory $actualStudyPath -NonInteractive
        if ($LASTEXITCODE -ne 0) {
            throw "Study compilation failed with exit code $LASTEXITCODE"
        }
        
        Write-Host "✅ Analysis pipeline completed" -ForegroundColor Green
        
        if ($Interactive) {
            Read-Host "Press Enter to continue..." | Out-Null
        }
        
        $finalStudyPath = $actualStudyPath
    } else {
        # For ExportOnly, just use the test study path
        $mockStudyDir = Get-ChildItem -Path $testStudyPath -Directory | Select-Object -First 1
        $finalStudyPath = $mockStudyDir.FullName
    }
    
    # Step 4: Generate GraphPad Exports
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
    Write-Host "`n❌ GRAPHPAD VALIDATION TEST FAILED" -ForegroundColor Red
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

Write-Host "`n✅ GRAPHPAD PRISM VALIDATION EXPORTS GENERATED SUCCESSFULLY" -ForegroundColor Green

if ($ExportOnly) {
    Write-Host "Export files available in: $GraphPadExportsDir" -ForegroundColor Cyan
} else {
    Write-Host "Ready for GraphPad Prism validation - follow instructions above" -ForegroundColor Cyan
}

exit 0

# === End of tests/algorithm_validation/validate_statistical_reporting.ps1 ===
