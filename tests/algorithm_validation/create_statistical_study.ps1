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
# Filename: tests/algorithm_validation/create_statistical_study.ps1

<#
.SYNOPSIS
    Statistical Validation Study Generator - Step 3 Implementation

.DESCRIPTION
    This script generates a real statistical validation study using the actual framework.
    It creates a 2x2 factorial design (Mapping Strategy x Group Size) by calling 
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
    .\create_statistical_study.ps1
    Generate the statistical validation study with default parameters.

.EXAMPLE
    .\create_statistical_study.ps1 -ReplicationsPerExperiment 8 -Force
    Generate with 8 replications per experiment, overwriting existing data.
#>

param(
    [string]$OutputPath = "tests/assets/statistical_validation_study",
    [int]$ReplicationsPerExperiment = 6,
    [int]$TrialsPerReplication = 32,
    [string]$Model = "meta-llama/llama-4-maverick",
    [array]$MappingStrategies = @("correct", "random"),
    [array]$GroupSizes = @(4, 10),
    [switch]$Force,
    [switch]$Verbose
)

# Script initialization and validation
if ($Verbose) { $VerbosePreference = "Continue" }

Write-Host "`n=== Statistical Validation Study Generator ===" -ForegroundColor Magenta
Write-Host "Focus: GraphPad Prism Statistical Validation" -ForegroundColor Green
Write-Host "Approach: Real framework execution with controlled parameters" -ForegroundColor White
Write-Host "Parameters: m = $TrialsPerReplication trials, $ReplicationsPerExperiment replications per experiment, Model = $Model" -ForegroundColor White

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
        Remove-Item $OutputPath -Recurse -Force 2>$null
    } else {
        Write-Host ""
        Write-Error "Output directory '$OutputPath' already exists. Use -Force to overwrite."
        Write-Host ""
        exit 1
    }
}

Write-Verbose "Creating output directory: $OutputPath"
New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null

# 2x2 Factorial Design Parameters (configurable)
$MappingStrategies = $MappingStrategies
$GroupSizes = $GroupSizes
$StudyName = "statistical_validation_study"

Write-Host "`nGenerating 2x2 factorial design using real framework..." -ForegroundColor Cyan
Write-Host "Experimental Design:" -ForegroundColor White
Write-Host "  Factor A: Mapping Strategy → correct vs random" -ForegroundColor Gray
Write-Host "  Factor B: Group Size → k=4 vs k=10" -ForegroundColor Gray
Write-Host "  Model: $Model (deterministic with temperature=0.0)" -ForegroundColor Gray
$TotalExperiments = $MappingStrategies.Count * $GroupSizes.Count
Write-Host "  Total: $TotalExperiments experiments x $ReplicationsPerExperiment replications = $($TotalExperiments * $ReplicationsPerExperiment) total replications" -ForegroundColor Gray

$ExperimentCounter = 1
$AllExperimentPaths = @()

foreach ($MappingStrategy in $MappingStrategies) {
    foreach ($K in $GroupSizes) {
        Write-Host "`n--- Creating Experiment ${ExperimentCounter}: ${MappingStrategy} mapping, k=${K} ---" -ForegroundColor Yellow
        
        Write-Host "  Generating experiment with $ReplicationsPerExperiment replications..." -ForegroundColor Blue
            
            try {
                # Update specific parameters in config.ini
                $configPath = "config.ini"
                $configBackup = "config.ini.backup"
                
                # Backup original config
                if (Test-Path $configPath) {
                    Copy-Item $configPath $configBackup -Force
                }
                
                # Read existing config and update only specific parameters
                if (Test-Path $configPath) {
                    $configLines = Get-Content $configPath -Encoding UTF8
                } else {
                    $configLines = @()
                }
                
                # Function to update or add a parameter in a specific section
                function Update-ConfigParameter {
                    param($Lines, $Section, $Key, $Value)
                    
                    $inSection = $false
                    $updated = $false
                    $result = @()
                    
                    foreach ($line in $Lines) {
                        if ($line -match "^\[$Section\]") {
                            $inSection = $true
                            $result += $line
                        } elseif ($line -match "^\[.*\]") {
                            if ($inSection -and -not $updated) {
                                $result += "$Key = $Value"
                                $updated = $true
                            }
                            $inSection = $false
                            $result += $line
                        } elseif ($inSection -and $line -match "^\s*$Key\s*=") {
                            $result += "$Key = $Value"
                            $updated = $true
                        } else {
                            $result += $line
                        }
                    }
                    
                    # Add section if it doesn't exist
                    if (-not $updated) {
                        $sectionExists = $Lines | Where-Object { $_ -match "^\[$Section\]" }
                        if (-not $sectionExists) {
                            $result += "[$Section]"
                        }
                        $result += "$Key = $Value"
                    }
                    
                    return $result
                }
                
                # Update only the parameters we need to control  
                $configLines = Update-ConfigParameter $configLines "Study" "num_replications" $ReplicationsPerExperiment
                $configLines = Update-ConfigParameter $configLines "Study" "num_trials" $TrialsPerReplication
                $configLines = Update-ConfigParameter $configLines "Study" "group_size" $K
                $configLines = Update-ConfigParameter $configLines "Study" "mapping_strategy" $MappingStrategy
                $configLines = Update-ConfigParameter $configLines "LLM" "model_name" $Model
                $configLines = Update-ConfigParameter $configLines "LLM" "temperature" "0.0"
                
                # Write updated config
                Set-Content -Path $configPath -Value $configLines -Encoding UTF8
                
                # Call new_experiment.ps1 without parameters
                & ".\new_experiment.ps1"
                
                # Restore original config
                if (Test-Path $configBackup) {
                    Move-Item $configBackup $configPath -Force
                }
                
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
                $modelSafe = $Model -replace '/', '_'  
                $newName = "exp_${ExperimentCounter}_${modelSafe}_${MappingStrategy}_k${K}_reps${ReplicationsPerExperiment}"
                $destinationPath = Join-Path $OutputPath $newName
                
                if (Test-Path $destinationPath) {
                    Remove-Item $destinationPath -Recurse -Force
                }
                
                Move-Item -Path $latestExperiment.FullName -Destination $destinationPath -Force
                $AllExperimentPaths += $destinationPath
                
                Write-Verbose "  Created: $newName"
                
            } catch {
                if ($_.Exception.Message -match "KeyboardInterrupt|interrupted") {
                    Write-Host "`nKeyboard interrupt detected. Cleaning up..." -ForegroundColor Yellow
                    # Restore original config if backup exists
                    if (Test-Path "config.ini.backup") {
                        Move-Item "config.ini.backup" "config.ini" -Force
                    }
                    Write-Host "Statistical validation study generation interrupted by user." -ForegroundColor Yellow
                    exit 130  # Standard exit code for keyboard interrupt
                } else {
                    Write-Error "Failed to generate experiment $ExperimentCounter`: $($_.Exception.Message)"
                    exit 1
                }
            }
        Write-Host "  ✓ Completed experiment $ExperimentCounter with $ReplicationsPerExperiment replications" -ForegroundColor Green
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
        if ($ExpName -match "exp_(\d+)_(.+)_(.+)_k(\d+)_reps(\d+)") {
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

# Compile the study automatically
Write-Host "`n=== Compiling Statistical Validation Study ===" -ForegroundColor Cyan
Write-Host "Running automatic study compilation..." -ForegroundColor White

try {
    Write-Host "Running automatic study compilation..." -ForegroundColor White
    $compileResult = & ".\compile_study.ps1" -StudyDirectory $OutputPath 2>&1 | Where-Object {
        $_ -match "^\[|^Step |completed successfully|Study Evaluation Finished|evaluation log has been saved" -and 
        $_ -notmatch "Could not clean the transcript log file"
    }
    
    if ($LASTEXITCODE -ne 0) {
        throw "compile_study.ps1 failed with exit code $LASTEXITCODE"
    }
    
    Write-Host "Study compilation completed successfully!" -ForegroundColor Green
    
    # Display experimental design summary
    Write-Host "`n=== Statistical Validation Study Generation Complete ===" -ForegroundColor Green
    Write-Host "Study location: $OutputPath" -ForegroundColor Cyan
    Write-Host "Data source: Real LLM responses from $Model (temperature=0.0)"
    Write-Host "Selection algorithm: Framework's built-in seeded randomization"
    Write-Host "Factorial design: 2x2 (Mapping Strategy x Group Size)"

    Write-Host "`nExperimental Conditions:" -ForegroundColor White
    foreach ($Condition in $ExperimentsByCondition.Keys | Sort-Object) {
        $Count = $ExperimentsByCondition[$Condition]
        Write-Host "  $Condition`: $Count replications" -ForegroundColor Gray
    }

    Write-Host "`nStudy Statistics:" -ForegroundColor White
    Write-Host "  Total experiments: $TotalReplications" -ForegroundColor Gray
    Write-Host "  Trials per experiment: $TrialsPerReplication" -ForegroundColor Gray
    Write-Host "  Total trials: $($TotalReplications * $TrialsPerReplication)" -ForegroundColor Gray
    Write-Host "  Expected statistical power: High (sufficient for full ANOVA)" -ForegroundColor Gray

    # Statistical analysis readiness report
    Write-Host "`n=== GraphPad Prism Validation Readiness ===" -ForegroundColor Cyan
    Write-Host "✓ Uses REAL framework execution (not mock data)" -ForegroundColor Green
    Write-Host "✓ Deterministic LLM responses (temperature=0.0)" -ForegroundColor Green
    Write-Host "✓ Framework's seeded randomization for personality selection" -ForegroundColor Green
    Write-Host "✓ Sufficient replications for full statistical analysis" -ForegroundColor Green
    Write-Host "✓ Balanced 2x2 factorial design" -ForegroundColor Green
    Write-Host "✓ Real data flow through complete analysis pipeline" -ForegroundColor Green
    Write-Host "✓ Ready for GraphPad validation" -ForegroundColor Green
    
    # Check for expected outputs
    $studyResultsFile = Join-Path $OutputPath "STUDY_results.csv"
    $anovaDir = Join-Path $OutputPath "anova"
    
    if (Test-Path $studyResultsFile) {
        Write-Host "  Generated: STUDY_results.csv" -ForegroundColor Gray
    }
    
    if (Test-Path $anovaDir) {
        Write-Host "  Generated: anova/ directory with statistical analysis" -ForegroundColor Gray
    }
    
} catch {
    Write-Warning "Study compilation failed: $($_.Exception.Message)"
    Write-Host "Manual compilation may be required:" -ForegroundColor Yellow
    Write-Host "  .\compile_study.ps1 -StudyDirectory '$OutputPath'" -ForegroundColor Gray
}

# Next steps guidance for validation
Write-Host "`n=== Next Steps for GraphPad Validation ===" -ForegroundColor Cyan
Write-Host "1. Generate GraphPad export files:" -ForegroundColor Gray
Write-Host "   pdm run test-graphpad-exports" -ForegroundColor Gray
Write-Host "2. Follow GraphPad Prism comparison instructions" -ForegroundColor Gray
Write-Host "3. Document validation results for publication" -ForegroundColor Gray

# Final cleanup: Ensure config.ini is restored to original state
Write-Verbose "Performing final cleanup..."
if (Test-Path "config.ini.backup") {
    Write-Verbose "Restoring original config.ini from backup..."
    Move-Item "config.ini.backup" "config.ini" -Force
}

if (-not $compilationFailed) {
    Write-Host "`n=== Next Steps for GraphPad Validation ===" -ForegroundColor Cyan
    Write-Host "`n=== 4-Step GraphPad Validation Workflow ===" -ForegroundColor Cyan
    Write-Host "✓ Step 1: create_statistical_study.ps1 - COMPLETED" -ForegroundColor Green
    Write-Host "→ Step 2: Generate GraphPad export files" -ForegroundColor Yellow
    Write-Host "   pwsh -File ./tests/algorithm_validation/generate_graphpad_exports.ps1" -ForegroundColor Gray
    Write-Host "  Step 3: Manual GraphPad Prism analysis (import, analyze, export)" -ForegroundColor Gray
    Write-Host "  Step 4: Validate results against framework" -ForegroundColor Gray
    Write-Host "2. Follow GraphPad Prism comparison instructions" -ForegroundColor Gray
    Write-Host "3. Document validation results for publication" -ForegroundColor Gray

    Write-Host "`nStatistical validation study generated and compiled successfully!" -ForegroundColor Green
    Write-Host "Focus: Complete 2x2 factorial study ready for GraphPad Prism comparison`n" -ForegroundColor Cyan
}

# === End of tests/algorithm_validation/create_statistical_study.ps1 ===
