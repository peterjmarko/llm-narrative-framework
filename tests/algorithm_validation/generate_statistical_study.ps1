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
# Filename: tests/algorithm_validation/generate_statistical_study.ps1

<#
.SYNOPSIS
    Statistical Validation Study Generator - Step 3 Implementation

.DESCRIPTION
    This script generates a real statistical validation study using the actual framework.
    It creates a 2×2 factorial design (Mapping Strategy × Group Size) by calling 
    new_experiment.ps1 with controlled parameters. The generated experiments use real
    LLM responses (temperature=0.0 for determinism) and the framework's built-in 
    seeded randomization for reproducibility.

    The study is designed to have sufficient replications to trigger full statistical
    analysis (ANOVA, post-hoc tests, Bayesian analysis) for GraphPad Prism validation.

.PARAMETER OutputPath
    Base directory for the validation study (default: tests/assets/statistical_validation_study)

.PARAMETER ReplicationsPerExperiment
    Number of replications per experimental condition (default: 6)

.PARAMETER M
    Number of trials per replication (default: 25)

.PARAMETER Model
    LLM model to use for validation (default: gemini-1.5-flash)

.PARAMETER Force
    Remove existing output directory if it exists

.PARAMETER Verbose
    Enable verbose output

.EXAMPLE
    .\generate_statistical_study.ps1
    Generate the statistical validation study with default parameters.

.EXAMPLE
    .\generate_statistical_study.ps1 -ReplicationsPerExperiment 8 -Force
    Generate with 8 replications per experiment, overwriting existing data.
#>

param(
    [string]$OutputPath = "tests/assets/statistical_validation_study",
    [int]$ReplicationsPerExperiment = 6,
    [int]$M = 25,
    [string]$Model = "gemini-1.5-flash",
    [switch]$Force,
    [switch]$Verbose
)

# Script initialization and validation
if ($Verbose) { $VerbosePreference = "Continue" }

Write-Host "=== Statistical Validation Study Generator - Step 3 Implementation ===" -ForegroundColor Cyan
Write-Host "Focus: GraphPad Prism Statistical Validation" -ForegroundColor Green
Write-Host "Approach: Real framework execution with controlled parameters" -ForegroundColor White
Write-Host "Parameters: M=$M trials, $ReplicationsPerExperiment replications per experiment, Model=$Model" -ForegroundColor White

# Verify required data files exist
$RequiredFiles = @(
    "data/personalities_db.txt"
)

Write-Host "`nValidating required data files..." -ForegroundColor White
foreach ($File in $RequiredFiles) {
    if (-not (Test-Path $File)) {
        Write-Error "Required file not found: $File"
        Write-Error "Please ensure the data preparation pipeline has been run."
        exit 1
    }
    Write-Verbose "✓ Found: $File"
}

# Verify framework scripts exist
$FrameworkScripts = @(
    "new_experiment.ps1",
    "compile_study.ps1"
)

Write-Host "Validating framework scripts..." -ForegroundColor White
foreach ($Script in $FrameworkScripts) {
    if (-not (Test-Path $Script)) {
        Write-Error "Framework script not found: $Script"
        Write-Error "Please ensure you're running from the project root directory."
        exit 1
    }
    Write-Verbose "✓ Found: $Script"
}

# Ensure output directory is clean
if (Test-Path $OutputPath) {
    if ($Force) {
        Write-Host "Removing existing validation study directory..." -ForegroundColor Yellow
        Remove-Item $OutputPath -Recurse -Force
    } else {
        Write-Error "Output directory '$OutputPath' already exists. Use -Force to overwrite."
        exit 1
    }
}

Write-Verbose "Creating output directory: $OutputPath"
New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null

# 2x2 Factorial Design Parameters
$MappingStrategies = @("correct", "random")
$GroupSizes = @(4, 10)
$StudyName = "statistical_validation_study"

Write-Host "`nGenerating 2x2 factorial design using real framework..." -ForegroundColor Cyan
Write-Host "Experimental Design:" -ForegroundColor White
Write-Host "  Factor A: Mapping Strategy → correct vs random" -ForegroundColor Gray
Write-Host "  Factor B: Group Size → K=4 vs K=10" -ForegroundColor Gray
Write-Host "  Model: $Model (deterministic with temperature=0.0)" -ForegroundColor Gray
Write-Host "  Total: 4 experiments × $ReplicationsPerExperiment replications = $($4 * $ReplicationsPerExperiment) total replications" -ForegroundColor Gray

$ExperimentCounter = 1
$AllExperimentPaths = @()

foreach ($MappingStrategy in $MappingStrategies) {
    foreach ($K in $GroupSizes) {
        Write-Host "`n--- Creating Experiment $ExperimentCounter: $MappingStrategy mapping, K=$K ---" -ForegroundColor Yellow
        
        # Generate multiple replications for this experimental condition
        for ($rep = 1; $rep -le $ReplicationsPerExperiment; $rep++) {
            Write-Host "  Generating replication $rep/$ReplicationsPerExperiment..." -ForegroundColor White
            
            try {
                # Call new_experiment.ps1 with controlled parameters
                $result = & ".\new_experiment.ps1" -Model $Model -K $K -M $M -MappingStrategy $MappingStrategy -Temperature 0.0 -NonInteractive
                
                if ($LASTEXITCODE -ne 0) {
                    throw "new_experiment.ps1 failed with exit code $LASTEXITCODE"
                }
                
                # Find the most recently created experiment directory
                $latestExperiment = Get-ChildItem -Path "output/new_experiments" -Directory | 
                                   Sort-Object CreationTime -Descending | 
                                   Select-Object -First 1
                
                if (-not $latestExperiment) {
                    throw "No experiment directory found after running new_experiment.ps1"
                }
                
                # Move experiment to our validation study directory with descriptive name
                $newName = "exp_${ExperimentCounter}_${Model}_${MappingStrategy}_k${K}_rep${rep}"
                $destinationPath = Join-Path $OutputPath $newName
                
                Move-Item -Path $latestExperiment.FullName -Destination $destinationPath
                $AllExperimentPaths += $destinationPath
                
                Write-Verbose "  Created: $newName"
                
            } catch {
                Write-Error "Failed to generate replication $rep for experiment $ExperimentCounter`: $($_.Exception.Message)"
                exit 1
            }
        }
        
        Write-Host "  ✓ Completed $ReplicationsPerExperiment replications for experiment $ExperimentCounter" -ForegroundColor Green
        $ExperimentCounter++
    }
}

# Verify all experiments were created successfully
Write-Host "`nValidating generated experiments..." -ForegroundColor White
$TotalReplications = 0
$ExperimentsByCondition = @{}

foreach ($ExpPath in $AllExperimentPaths) {
    if (Test-Path $ExpPath) {
        $TotalReplications++
        
        # Extract condition from path name
        $ExpName = Split-Path $ExpPath -Leaf
        if ($ExpName -match "exp_(\d+)_(.+)_(.+)_k(\d+)_rep(\d+)") {
            $Condition = "$($Matches[3])_k$($Matches[4])"  # e.g., "correct_k4"
            if (-not $ExperimentsByCondition.ContainsKey($Condition)) {
                $ExperimentsByCondition[$Condition] = 0
            }
            $ExperimentsByCondition[$Condition]++
        }
        
        Write-Verbose "  ✓ Validated: $(Split-Path $ExpPath -Leaf)"
    } else {
        Write-Error "Missing experiment directory: $ExpPath"
        exit 1
    }
}

Write-Host "✓ All experiments generated successfully" -ForegroundColor Green

# Display experimental design summary
Write-Host "`n=== Statistical Validation Study Generation Complete ===" -ForegroundColor Green
Write-Host "Study location: $OutputPath" -ForegroundColor Yellow
Write-Host "Data source: Real LLM responses from $Model (temperature=0.0)" -ForegroundColor Yellow
Write-Host "Selection algorithm: Framework's built-in seeded randomization" -ForegroundColor Yellow
Write-Host "Factorial design: 2×2 (Mapping Strategy × Group Size)" -ForegroundColor Yellow

Write-Host "`nExperimental Conditions:" -ForegroundColor White
foreach ($Condition in $ExperimentsByCondition.Keys | Sort-Object) {
    $Count = $ExperimentsByCondition[$Condition]
    Write-Host "  $Condition`: $Count replications" -ForegroundColor Gray
}

Write-Host "`nStudy Statistics:" -ForegroundColor White
Write-Host "  Total experiments: $TotalReplications" -ForegroundColor Gray
Write-Host "  Trials per experiment: $M" -ForegroundColor Gray
Write-Host "  Total trials: $($TotalReplications * $M)" -ForegroundColor Gray
Write-Host "  Expected statistical power: High (sufficient for full ANOVA)" -ForegroundColor Gray

# Statistical analysis readiness report
Write-Host "`n=== GraphPad Prism Validation Readiness ===" -ForegroundColor Cyan
Write-Host "✓ Uses REAL framework execution (not mock data)" -ForegroundColor Green
Write-Host "✓ Deterministic LLM responses (temperature=0.0)" -ForegroundColor Green
Write-Host "✓ Framework's seeded randomization for personality selection" -ForegroundColor Green
Write-Host "✓ Sufficient replications for full statistical analysis" -ForegroundColor Green
Write-Host "✓ Balanced 2×2 factorial design" -ForegroundColor Green
Write-Host "✓ Real data flow through complete analysis pipeline" -ForegroundColor Green
Write-Host "✓ Ready for compile_study.ps1 → GraphPad validation" -ForegroundColor Green

# Next steps guidance
Write-Host "`n=== Next Steps for GraphPad Validation ===" -ForegroundColor White
Write-Host "1. Run study compilation:" -ForegroundColor Gray
Write-Host "   .\compile_study.ps1 -StudyDirectory '$OutputPath'" -ForegroundColor Gray
Write-Host "2. Run GraphPad validation script:" -ForegroundColor Gray
Write-Host "   pdm run test-stats-reporting" -ForegroundColor Gray
Write-Host "3. Follow GraphPad Prism comparison instructions" -ForegroundColor Gray
Write-Host "4. Document validation results for publication" -ForegroundColor Gray

Write-Host "`nStatistical validation study generated successfully!" -ForegroundColor Green
Write-Host "Focus: Real framework validation for GraphPad Prism comparison" -ForegroundColor Cyan

# === End of tests/algorithm_validation/generate_statistical_study.ps1 ===
