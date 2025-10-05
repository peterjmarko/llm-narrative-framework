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
# Filename: tests/testing_harness/experiment_workflow/layer5/layer5_phase1_setup.ps1

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent
$TestEnvRoot = Join-Path $ProjectRoot "temp_test_environment"
$SandboxDir = Join-Path $TestEnvRoot "layer5_sandbox"
$StudyDir = Join-Path $SandboxDir "test_study"

try {
    # --- Cleanup from previous failed runs ---
    if (Test-Path $SandboxDir) {
        Write-Host "`nCleaning up previous Layer 5 sandbox..." -ForegroundColor Yellow
        Remove-Item -Path $SandboxDir -Recurse -Force
    }

    # --- Create the test environment ---
    New-Item -ItemType Directory -Path $TestEnvRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $StudyDir -Force | Out-Null

    Write-Host ""
    Write-Host "--- Layer 5 Integration Testing: Study Compilation ---" -ForegroundColor Magenta
    Write-Host "--- Phase 1: Automated Setup ---" -ForegroundColor Cyan
    Write-Host ""

    # --- Check for Layer 4 factorial study to copy ---
    $Layer4StudyDir = Join-Path $ProjectRoot "tests/assets/layer4_factorial_study"
    $Layer4SandboxDir = Join-Path $TestEnvRoot "layer4_sandbox/experiments"
    $Layer4ExperimentsFound = $false
    
    # First priority: Use permanent factorial study from previous Layer 4 runs
    if (Test-Path $Layer4StudyDir) {
        $Layer4Experiments = Get-ChildItem -Path $Layer4StudyDir -Directory -Filter "experiment_*" -ErrorAction SilentlyContinue
        if ($Layer4Experiments.Count -eq 4) {
            Write-Host "Found 4 experiments from Layer 4. Validating 2x2 factorial design..." -ForegroundColor Yellow
            
            # Validate factorial design by examining config files
            $mappingStrategies = @()
            $groupSizes = @()
            $validExperiments = $true
            
            foreach ($experiment in $Layer4Experiments) {
                # Check for experiment-level config first
                $configFile = Join-Path $experiment.FullName "config.ini.archived"
                
                # If not found at experiment level, check first replication directory
                if (-not (Test-Path $configFile)) {
                    $repDirs = Get-ChildItem -Path $experiment.FullName -Directory -Filter "run_*" | Select-Object -First 1
                    if ($repDirs) {
                        $configFile = Join-Path $repDirs.FullName "config.ini.archived"
                    }
                }
                
                if (Test-Path $configFile) {
                    $configContent = Get-Content $configFile
                    $mappingStrategyLine = $configContent | Where-Object { $_ -like "*mapping_strategy*" -and $_ -like "*=*" }
                    $groupSizeLine = $configContent | Where-Object { $_ -like "*group_size*" -and $_ -like "*=*" }
                    
                    $mappingStrategy = if ($mappingStrategyLine) { ($mappingStrategyLine -split "=")[1].Trim() } else { "" }
                    $groupSize = if ($groupSizeLine) { ($groupSizeLine -split "=")[1].Trim() } else { "" }
                    
                    Write-Host "  -> $($experiment.Name): mapping_strategy='$mappingStrategy', group_size='$groupSize'" -ForegroundColor Gray
                    
                    if ($mappingStrategy -and $groupSize) {
                        $mappingStrategies += $mappingStrategy.Trim()
                        $groupSizes += [int]$groupSize.Trim()
                    } else {
                        $validExperiments = $false
                        Write-Host "  -> Could not extract mapping_strategy and group_size from $($experiment.Name)" -ForegroundColor Red
                        break
                    }
                } else {
                    Write-Host "  -> Missing config file in $($experiment.Name)" -ForegroundColor Red
                    $validExperiments = $false
                    break
                }
                
                # Check that experiment is not already compiled into a study
                $studyResultsFile = Join-Path $experiment.FullName "STUDY_results.csv"
                $anovaDir = Join-Path $experiment.FullName "anova"
                if ((Test-Path $studyResultsFile) -or (Test-Path $anovaDir)) {
                    Write-Host "  -> Experiment $($experiment.Name) appears to be already compiled (found study-level artifacts)" -ForegroundColor Red
                    $validExperiments = $false
                    break
                }
            }
            
            if ($validExperiments) {
                # Validate 2x2 factorial design
                $uniqueMappingStrategies = $mappingStrategies | Sort-Object -Unique
                $uniqueGroupSizes = $groupSizes | Sort-Object -Unique
                
                if (($uniqueMappingStrategies.Count -eq 2) -and ($uniqueGroupSizes.Count -eq 2)) {
                    Write-Host "  -> Validated: 2x2 factorial design (mapping_strategy: $($uniqueMappingStrategies -join '/'), group_size: $($uniqueGroupSizes -join '/'))" -ForegroundColor Green
                    Write-Host "  -> All experiments are uncompiled and ready for study compilation" -ForegroundColor Green
                    
                    foreach ($experiment in $Layer4Experiments) {
                        $destDir = Join-Path $StudyDir $experiment.Name
                        Copy-Item -Path $experiment.FullName -Destination $destDir -Recurse -Force
                        Write-Host "  -> Copied: $($experiment.Name)" -ForegroundColor Cyan
                    }
                    
                    # Copy study metadata if it exists
                    $metadataFile = Join-Path $Layer4StudyDir "STUDY_metadata.json"
                    if (Test-Path $metadataFile) {
                        Copy-Item -Path $metadataFile -Destination (Join-Path $StudyDir "STUDY_metadata.json") -Force
                        Write-Host "  -> Copied: STUDY_metadata.json" -ForegroundColor Cyan
                    }
                    
                    $Layer4ExperimentsFound = $true
                } else {
                    Write-Host "  -> Invalid factorial design: Found $($uniqueMappingStrategies.Count) mapping strategies and $($uniqueGroupSizes.Count) group sizes" -ForegroundColor Red
                    Write-Host "  -> Expected 2x2 design with 2 mapping strategies and 2 group sizes. Using fallback data." -ForegroundColor Yellow
                }
            } else {
                Write-Host "  -> Experiments failed validation. Using fallback data." -ForegroundColor Yellow
            }
        } elseif ($Layer4Experiments.Count -gt 0) {
            Write-Host "Note: Found $($Layer4Experiments.Count) experiments from Layer 4, but expected 2x2 factorial (4). Using fallback data." -ForegroundColor Yellow
        }
    }
    
    # Second priority: Use current sandbox experiments (if Layer 4 just ran)
    if (-not $Layer4ExperimentsFound -and (Test-Path $Layer4SandboxDir)) {
        $Layer4Experiments = Get-ChildItem -Path $Layer4SandboxDir -Directory -Filter "experiment_*" -ErrorAction SilentlyContinue
        if ($Layer4Experiments.Count -gt 0) {
            Write-Host "Found $($Layer4Experiments.Count) experiment(s) from current Layer 4 sandbox. Copying to study directory..." -ForegroundColor Green
            
            foreach ($experiment in $Layer4Experiments) {
                $destDir = Join-Path $StudyDir $experiment.Name
                Copy-Item -Path $experiment.FullName -Destination $destDir -Recurse -Force
                Write-Host "  -> Copied: $($experiment.Name)" -ForegroundColor Cyan
            }
            $Layer4ExperimentsFound = $true
        }
    }

    if (-not $Layer4ExperimentsFound) {
        Write-Host "No Layer 4 experiments found. Creating mock study data for standalone testing..." -ForegroundColor Yellow
        
        # --- Create Mock Experiments as fallback ---
        # Create 4 mock experiments representing a 2x2 factorial design:
        # mapping_strategy: correct, random  
        # group_size (k): 4, 10
        # Note: Using 3 replications for faster testing (vs 30 in production)
        
        $mockExperiments = @(
            @{ Name = "experiment_20250101_120000"; MappingStrategy = "correct"; GroupSize = 4; MRR = 0.62; TopAcc = 0.45 }
            @{ Name = "experiment_20250101_130000"; MappingStrategy = "random"; GroupSize = 4; MRR = 0.28; TopAcc = 0.21 }
            @{ Name = "experiment_20250101_140000"; MappingStrategy = "correct"; GroupSize = 10; MRR = 0.58; TopAcc = 0.31 }
            @{ Name = "experiment_20250101_150000"; MappingStrategy = "random"; GroupSize = 10; MRR = 0.12; TopAcc = 0.08 }
        )

        foreach ($exp in $mockExperiments) {
            $expDir = Join-Path $StudyDir $exp.Name
            New-Item -ItemType Directory -Path $expDir -Force | Out-Null

            # Create mock EXPERIMENT_results.csv
            $csvHeader = "run_directory,replication,n_valid_responses,model,mapping_strategy,temperature,k,m,db,mean_mrr,mrr_p,mean_top_1_acc,top_1_acc_p,mean_top_3_acc,top_3_acc_p,mean_mrr_lift,mean_top_1_acc_lift,mean_top_3_acc_lift,mean_rank_of_correct_id,rank_of_correct_id_p,top1_pred_bias_std,true_false_score_diff,bias_slope,bias_intercept,bias_r_value,bias_p_value,bias_std_err"
            $csvContent = @($csvHeader)
            
            # Generate 3 replications per experiment (configurable for testing)
            $NumReplications = 3  # Use 3 for fast testing, 30 for production
            for ($rep = 1; $rep -le $NumReplications; $rep++) {
                $runDir = "run_20250101_${rep}${rep}${rep}${rep}${rep}${rep}_rep-$('{0:D3}' -f $rep)_gemini-flash-1_5_tmp-1_00_personalities_db_sbj-$('{0:D2}' -f $exp.GroupSize)_trl-003_rps-003_mps-$($exp.MappingStrategy)"
                $row = "$runDir,$rep,3,google/gemini-flash-1.5,$($exp.MappingStrategy),1.0,$($exp.GroupSize),3,personalities_db,$($exp.MRR),$((Get-Random -Min 1 -Max 100) / 1000.0),$($exp.TopAcc),$((Get-Random -Min 1 -Max 100) / 1000.0),0.65,0.025,1.2,1.8,2.1,2.5,0.15,0.08,0.02,-0.01,0.02,0.98,0.45,0.02"
                $csvContent += $row
            }
            
            $csvContent | Set-Content -Path (Join-Path $expDir "EXPERIMENT_results.csv") -Encoding UTF8

            # Create mock batch_run_log.csv
            $logContent = @(
                "Timestamp,Event,Details",
                "2025-01-01 12:00:00,BatchStart,Starting experiment batch",
                "2025-01-01 12:05:00,ReplicationComplete,Replication 1 completed successfully",
                "2025-01-01 12:10:00,ReplicationComplete,Replication 2 completed successfully", 
                "2025-01-01 12:15:00,ReplicationComplete,Replication 3 completed successfully",
                "2025-01-01 12:20:00,BatchSummary,Total replications: 3, Successful: 3, Failed: 0"
            )
            $logContent | Set-Content -Path (Join-Path $expDir "batch_run_log.csv") -Encoding UTF8

            # Create mock config.ini.archived (required by audit)
            $configContent = @(
                "[Study]",
                "num_replications = 3",
                "num_trials = 3", 
                "group_size = $($exp.GroupSize)",
                "mapping_strategy = $($exp.MappingStrategy)",
                "",
                "[LLM]",
                "model_name = google/gemini-flash-1.5",
                "temperature = 1.0"
            )
            $configContent | Set-Content -Path (Join-Path $expDir "config.ini.archived") -Encoding UTF8

            # Create mock EXPERIMENT_log.txt (required by audit)
            $expLogContent = @(
                "Experiment started: 2025-01-01 12:00:00",
                "Configuration loaded successfully",
                "Replications completed: 3/3",
                "Experiment finished: 2025-01-01 12:20:00",
                "Status: COMPLETED"
            )
            $expLogContent | Set-Content -Path (Join-Path $expDir "EXPERIMENT_log.txt") -Encoding UTF8

            # Create individual replication directories (audit expects these)
            for ($rep = 1; $rep -le $NumReplications; $rep++) {
                $repDir = Join-Path $expDir "run_20250101_${rep}${rep}${rep}${rep}${rep}${rep}_rep-$('{0:D3}' -f $rep)_gemini-flash-1_5_tmp-1_00_personalities_db_sbj-$('{0:D2}' -f $exp.GroupSize)_trl-003_rps-003_mps-$($exp.MappingStrategy)"
                New-Item -ItemType Directory -Path $repDir -Force | Out-Null
                
                # Create minimal replication files that audit expects
                "run_started,run_completed" | Set-Content -Path (Join-Path $repDir "REPLICATION_results.csv") -Encoding UTF8
                "Replication $rep completed successfully" | Set-Content -Path (Join-Path $repDir "replication_report_20250101-120000.txt") -Encoding UTF8
            }

            Write-Host "  -> Created mock experiment: $($exp.Name) ($($exp.MappingStrategy), k=$($exp.GroupSize))" -ForegroundColor Cyan
        }
    }

    Write-Host ""
    Write-Host "Integration test sandbox created successfully in '$((Resolve-Path $SandboxDir -Relative).TrimStart(".\"))'." -ForegroundColor Green

}
catch {
    Write-Host "`nERROR: Layer 5 setup script failed.`n$($_.Exception.Message)" -ForegroundColor Red
    # Re-throw the original exception to the master runner.
    throw
}

# === End of tests/testing_harness/experiment_workflow/layer5/layer5_phase1_setup.ps1 ===
