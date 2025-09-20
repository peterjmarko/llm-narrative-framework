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
# Filename: tests/testing_harness/experiment_lifecycle/layer4/layer4_phase2_run.ps1

param(
    [switch]$Interactive
)

# --- Define ANSI Color Codes ---
$C_RESET = "`e[0m"
$C_GRAY = "`e[90m"
$C_MAGENTA = "`e[95m"
$C_RED = "`e[91m"
$C_ORANGE = "`e[38;5;208m"
$C_YELLOW = "`e[93m"
$C_GREEN = "`e[92m"
$C_CYAN = "`e[96m"
$C_BLUE = "`e[94m"

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer4_sandbox"
$TestConfigPath = Join-Path $SandboxDir "config.ini"

function Write-TestHeader { param($Message, $Color = 'Blue') Write-Host "--- $($Message) ---" -ForegroundColor $Color }
function Format-Banner {
    param([string]$Message, [string]$Color = $C_CYAN)
    $line = '#' * 80; $bookend = "###"; $contentWidth = $line.Length - ($bookend.Length * 2)
    $paddingNeeded = $contentWidth - $Message.Length - 2; $leftPad = [Math]::Floor($paddingNeeded / 2); $rightPad = [Math]::Ceiling($paddingNeeded / 2)
    $centeredMsg = "$bookend $(' ' * $leftPad)$Message$(' ' * $rightPad) $bookend"
    Write-Host "`n$Color$line"; Write-Host "$Color$centeredMsg"; Write-Host "$Color$line$C_RESET`n"
}

Write-Host ""
Write-Host "--- Layer 4: Experiment Lifecycle Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Phase 2: Run Test Workflow ---" -ForegroundColor Cyan

try {
    # --- STEP 1: Creating a new experiment ---
    $stepHeader = ">>> Step 1/6: Create New Experiment <<<"
    Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray
    Write-Host $stepHeader -ForegroundColor Blue
    Write-Host "Creates 4 experiments using a 2x2 factorial design (mapping_strategy x group_size)." -ForegroundColor Blue
    
    if ($Interactive) {
        Write-Host "`n${C_BLUE}Step Summary: This step demonstrates creating multiple experiments for a factorial study design. It will generate 4 complete experiments (2x2 factorial: correct/random mapping × 4/10 group size), each with 1 replication containing 2 trials.${C_RESET}"
        Write-Host "`n${C_GRAY}  BASE DIRECTORY: $($SandboxDir.Replace('\', '/'))${C_RESET}"
        Write-Host ""
        Write-Host "${C_RESET}  INPUTS:"
        Write-Host "    - config.ini (test configuration)"
        Write-Host "    - data/personalities_db.txt (10 test subjects)"
        Write-Host ""
        Write-Host "  OUTPUT:"
        Write-Host "    - output/new_experiments/experiment_[timestamp]/ (complete experiment directory)"
        
        Read-Host -Prompt "`n${C_ORANGE}Press Enter to execute this step (Ctrl+C to exit)...${C_RESET}" | Out-Null
        Write-Host ""
    }

    # Create 2x2 factorial design: mapping_strategy (correct, random) x group_size (4, 10)
    $factorialDesign = @(
        @{ mapping_strategy = "correct"; group_size = 4 }
        @{ mapping_strategy = "random"; group_size = 4 }
        @{ mapping_strategy = "correct"; group_size = 10 }
        @{ mapping_strategy = "random"; group_size = 10 }
    )
    
    $createdExperiments = @()
    $basePath = Join-Path $SandboxDir "experiments"
    
    foreach ($condition in $factorialDesign) {
        Write-Host "  Creating experiment: mapping_strategy=$($condition.mapping_strategy), group_size=$($condition.group_size)" -ForegroundColor Cyan
        
        # Create temporary config for this condition
        $tempConfig = $TestConfigPath -replace "\.ini$", "_temp.ini"
        $configContent = Get-Content $TestConfigPath -Raw
        $configContent = $configContent -replace "mapping_strategy = \w+", "mapping_strategy = $($condition.mapping_strategy)"
        $configContent = $configContent -replace "group_size = \d+", "group_size = $($condition.group_size)"
        $configContent | Set-Content -Path $tempConfig -Encoding UTF8
        
        & "$ProjectRoot\new_experiment.ps1" -ConfigPath $tempConfig
        if ($LASTEXITCODE -ne 0) { 
            Remove-Item -Path $tempConfig -Force -ErrorAction SilentlyContinue
            throw "new_experiment.ps1 failed for condition: $($condition | ConvertTo-Json -Compress)" 
        }
        
        # Find the newly created experiment
        $latestExperiment = Get-ChildItem -Path $basePath -Directory | Sort-Object CreationTime -Descending | Select-Object -First 1
        if ($latestExperiment) {
            $createdExperiments += $latestExperiment.FullName
            Write-Host "    -> Created: $($latestExperiment.Name)" -ForegroundColor Green
        }
        
        Remove-Item -Path $tempConfig -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1  # Ensure timestamp differences between experiments
    }
    
    if ($createdExperiments.Count -ne 4) {
        throw "Expected 4 experiments to be created, but got $($createdExperiments.Count)"
    }
    
    # Use the first experiment for the break/fix cycle demonstration
    $NewExperimentPath = $createdExperiments[0]
    
    if (-not (Test-Path $NewExperimentPath -PathType Container)) { throw "Experiment directory not found: $NewExperimentPath" }
    $RelativePath = (Resolve-Path $NewExperimentPath -Relative).TrimStart(".\")
    Write-Host "  -> New experiment created at: $RelativePath" -ForegroundColor Green
    Write-Host ""

    Write-Host "`n${C_GREEN}SUCCESS: Experiment created successfully at '$RelativePath'.${C_RESET}"
    
    if ($Interactive) {
        Write-Host "`n${C_ORANGE}Step complete. Inspect the output, then press Enter to continue..."
        Read-Host | Out-Null
    }

    # --- STEP 2: Auditing the new experiment ---
    $stepHeader = ">>> Step 2/6: Audit New Experiment <<<"
    Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray
    Write-Host $stepHeader -ForegroundColor Blue
    Write-Host "Verifies the experiment is complete and valid using audit_experiment.ps1." -ForegroundColor Blue
    
    if ($Interactive) {
        Write-Host "`n${C_BLUE}Step Summary: This step demonstrates the framework's diagnostic capabilities. The audit script performs a comprehensive health check, validating that all required files are present and correctly formatted. A properly created experiment should show status 'VALIDATED'.${C_RESET}"
        Write-Host "`n${C_GRAY}  EXPERIMENT DIRECTORY: $RelativePath${C_RESET}"
        Write-Host ""
        Write-Host "${C_RESET}  EXPECTED RESULT:"
        Write-Host "    - Overall Status: VALIDATED"
        Write-Host "    - All replications: COMPLETE"
        Write-Host "    - Exit Code: 0 (success)"
        
        Read-Host -Prompt "`n${C_ORANGE}Press Enter to execute this step (Ctrl+C to exit)...${C_RESET}" | Out-Null
        Write-Host ""
    }

    # Starting Step 2 execution
    & "$ProjectRoot\audit_experiment.ps1" -ExperimentDirectory $NewExperimentPath -ConfigPath $TestConfigPath
    if ($LASTEXITCODE -ne 0) { throw "Initial audit failed. Experiment should be VALIDATED." }

    Write-Host "`n${C_GREEN}SUCCESS: Audit completed. Experiment shows as VALIDATED.${C_RESET}"
    
    if ($Interactive) {
        Write-Host "`nStep complete. Inspect the audit results above." -ForegroundColor Yellow
        Read-Host -Prompt "Press Enter to continue..." | Out-Null
    }

    # --- STEP 3: Deliberately breaking the experiment ---
    $stepHeader = ">>> Step 3/6: Simulate Failure <<<"
    Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray
    Write-Host $stepHeader -ForegroundColor Blue
    Write-Host "Deliberately corrupts the experiment to simulate a common failure scenario." -ForegroundColor Blue
    
    if ($Interactive) {
        Write-Host "`n${C_BLUE}Step Summary: This step simulates 4 different real-world failure scenarios across all experiments. Each failure type represents a common issue that can occur during experiment execution. The framework should detect and repair all of them automatically.${C_RESET}"
        Write-Host "`n${C_GRAY}  FAILURE SCENARIOS:${C_RESET}"
        Write-Host "    1. API Failure: Missing LLM response (network interruption)"
        Write-Host "    2. Processing Failure: Corrupted analysis file (I/O error)"
        Write-Host "    3. Data Failure: Missing trial directory (storage failure)" 
        Write-Host "    4. Config Failure: Broken metadata (invalid state)"
        Write-Host ""
        Write-Host "${C_RESET}  Each experiment will demonstrate a different failure mode."
        
        Read-Host -Prompt "`n${C_ORANGE}Press Enter to corrupt all 4 experiments (Ctrl+C to exit)...${C_RESET}" | Out-Null
        Write-Host ""
    }

    # Starting Step 3 execution - Create different error conditions for each experiment
    $errorConditions = @(
        @{ Type = "Missing LLM Response"; Description = "API-level failure (network interruption)" }
        @{ Type = "Corrupted Analysis"; Description = "Processing failure (I/O error)" }  
        @{ Type = "Missing Trial Data"; Description = "Data-level failure (storage failure)" }
        @{ Type = "Broken Configuration"; Description = "Configuration failure (invalid state)" }
    )
    
    for ($i = 0; $i -lt $createdExperiments.Count; $i++) {
        $experimentPath = $createdExperiments[$i]
        $experimentName = Split-Path $experimentPath -Leaf
        $errorCondition = $errorConditions[$i]
        
        # Create banner for each experiment
        $bannerText = "EXPERIMENT $($i+1)/4: $($errorCondition.Type)"
        $bannerLine = "=" * 60
        Write-Host "`n$bannerLine" -ForegroundColor DarkCyan
        Write-Host $bannerText -ForegroundColor Cyan
        Write-Host "$($errorCondition.Description)" -ForegroundColor Gray
        Write-Host $bannerLine -ForegroundColor DarkCyan
        
        Write-Host "  Target: $experimentName" -ForegroundColor Yellow
        Write-Host "    Error type: $($errorCondition.Type) - $($errorCondition.Description)" -ForegroundColor Gray
        
        if ($Interactive -and $i -eq 0) {
            # Detailed walkthrough for first experiment only
            Write-Host "`n${C_BLUE}DETAILED WALKTHROUGH (Experiment 1 only):${C_RESET}"
            Write-Host "This experiment will lose an LLM response file, simulating what happens"
            Write-Host "when an API call is interrupted by network issues or rate limits."
            Write-Host "The audit will detect the missing file and fix_experiment.ps1 will"
            Write-Host "automatically re-run only the failed API call."
            Read-Host -Prompt "`n${C_ORANGE}Press Enter to corrupt this experiment...${C_RESET}" | Out-Null
        } elseif ($Interactive) {
            # Brief prompt for remaining experiments
            Read-Host -Prompt "${C_ORANGE}Press Enter to corrupt experiment $($i+1)...${C_RESET}" | Out-Null
        }
        
        switch ($i) {
            0 { # Missing LLM Response File
                $responseFile = Get-ChildItem -Path $experimentPath -Filter "llm_response_*.txt" -Recurse | Select-Object -First 1
                if ($responseFile) {
                    Remove-Item -Path $responseFile.FullName -Force
                    Write-Host "    -> Deleted: $($responseFile.Name)" -ForegroundColor Red
                }
            }
            1 { # Corrupted Analysis File  
                $resultsFile = Get-ChildItem -Path $experimentPath -Filter "EXPERIMENT_results.csv" -Recurse | Select-Object -First 1
                if ($resultsFile) {
                    "corrupted,data,invalid" | Set-Content -Path $resultsFile.FullName -Force
                    Write-Host "    -> Corrupted: EXPERIMENT_results.csv" -ForegroundColor Red
                }
            }
            2 { # Missing Trial Data
                $trialDir = Get-ChildItem -Path $experimentPath -Directory -Filter "run_*" | Get-ChildItem -Directory -Filter "trial_*" | Select-Object -First 1
                if ($trialDir) {
                    Remove-Item -Path $trialDir.FullName -Recurse -Force
                    Write-Host "    -> Deleted: $($trialDir.Name) directory" -ForegroundColor Red
                }
            }
            3 { # Broken Configuration State
                $configFile = Join-Path $experimentPath "experiment_metadata.json"
                if (Test-Path $configFile) {
                    '{"invalid": "config", "broken": true}' | Set-Content -Path $configFile -Force
                    Write-Host "    -> Corrupted: experiment_metadata.json" -ForegroundColor Red
                }
            }
        }
    }
    
    Write-Host ""
    Write-Host "`n${C_YELLOW}All 4 experiments corrupted with different error conditions.${C_RESET}"
    
    if ($Interactive) {
        Write-Host "`nStep complete. The experiment now has missing data." -ForegroundColor Yellow
        Read-Host -Prompt "Press Enter to continue..." | Out-Null
    }

    # --- STEP 4: Auditing the broken experiment ---
    $stepHeader = ">>> Step 4/6: Audit Broken Experiment <<<"
    Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray
    Write-Host $stepHeader -ForegroundColor Blue
    Write-Host "Verifies the audit system can detect the missing data and recommend repair." -ForegroundColor Blue
    
    if ($Interactive) {
        Write-Host "`n${C_BLUE}Step Summary: This step demonstrates the framework's ability to detect corruption. The audit should identify the missing response file and recommend using 'fix_experiment.ps1' to repair the data. The exit code should be 2 (needs repair).${C_RESET}"
        Write-Host "`n${C_GRAY}  EXPERIMENT DIRECTORY: $RelativePath${C_RESET}"
        Write-Host ""
        Write-Host "${C_RESET}  EXPECTED RESULT:"
        Write-Host "    - Overall Status: NEEDS REPAIR"
        Write-Host "    - Missing: LLM response files"
        Write-Host "    - Exit Code: 2 (repair needed)"
        
        Read-Host -Prompt "`n${C_ORANGE}Press Enter to execute this step (Ctrl+C to exit)...${C_RESET}" | Out-Null
        Write-Host ""
    }

    # Starting Step 4 execution - Audit all corrupted experiments
    for ($i = 0; $i -lt $createdExperiments.Count; $i++) {
        $experimentPath = $createdExperiments[$i]
        $experimentName = Split-Path $experimentPath -Leaf
        $errorCondition = $errorConditions[$i]
        
        Write-Host "  Auditing experiment $($i+1): $experimentName" -ForegroundColor Cyan
        Write-Host "    Expected error: $($errorCondition.Type)" -ForegroundColor Gray
        
        & "$ProjectRoot\audit_experiment.ps1" -ExperimentDirectory $experimentPath -ConfigPath $TestConfigPath
        if ($LASTEXITCODE -ne 2) { 
            throw "Audit of experiment $($i+1) did not correctly identify it as needing REPAIR (Exit Code 2)." 
        }
        Write-Host "    -> Correctly identified as needing repair" -ForegroundColor Green
        Write-Host ""
    }

    Write-Host "`n${C_GREEN}SUCCESS: All audits detected their respective corruptions and recommended repair.${C_RESET}"
    
    if ($Interactive) {
        Write-Host "`nStep complete. The audit correctly identified the missing data." -ForegroundColor Gray
        Read-Host -Prompt "Press Enter to continue..." | Out-Null
    }

    # --- STEP 5: Fixing the experiment ---
    $stepHeader = ">>> Step 5/6: Repair Experiment <<<"
    Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray
    Write-Host $stepHeader -ForegroundColor Blue
    Write-Host "Automatically repairs the experiment using fix_experiment.ps1." -ForegroundColor Blue
    
    if ($Interactive) {
        Write-Host "`n${C_BLUE}Step Summary: This step demonstrates the framework's self-healing capabilities. The fix script will automatically detect what's missing and re-run only the necessary API calls to restore the experiment to a complete state. No manual intervention is required.${C_RESET}"
        Write-Host "`n${C_GRAY}  REPAIR STRATEGY: Intelligent re-run of missing components${C_RESET}"
        Write-Host ""
        Write-Host "${C_RESET}  ACTIONS:"
        Write-Host "    - Detect missing LLM response files"
        Write-Host "    - Re-run only the failed API calls"
        Write-Host "    - Rebuild analysis and summary files"
        Write-Host "    - Verify experiment integrity"
        
        Read-Host -Prompt "`n${C_ORANGE}Press Enter to execute this step (Ctrl+C to exit)...${C_RESET}" | Out-Null
        Write-Host ""
    }

    # Starting Step 5 execution - Repair all corrupted experiments
    for ($i = 0; $i -lt $createdExperiments.Count; $i++) {
        $experimentPath = $createdExperiments[$i]
        $experimentName = Split-Path $experimentPath -Leaf
        $errorCondition = $errorConditions[$i]
        
        Write-Host "  Repairing experiment $($i+1): $experimentName" -ForegroundColor Cyan
        Write-Host "    Fixing: $($errorCondition.Type)" -ForegroundColor Gray
        
        if ($Interactive -and $i -eq 0) {
            Write-Host "`n${C_BLUE}DETAILED REPAIR (Experiment 1):${C_RESET}"
            Write-Host "The repair will identify what's missing and re-run only the failed API call."
            Read-Host -Prompt "${C_ORANGE}Press Enter to repair this experiment...${C_RESET}" | Out-Null
        } elseif ($Interactive) {
            Read-Host -Prompt "${C_ORANGE}Press Enter to repair experiment $($i+1)...${C_RESET}" | Out-Null
        }
        
        & "$ProjectRoot\fix_experiment.ps1" -ExperimentDirectory $experimentPath -ConfigPath $TestConfigPath -NonInteractive
        if ($LASTEXITCODE -ne 0) { 
            throw "fix_experiment.ps1 failed to repair experiment $($i+1)." 
        }
        Write-Host "    -> Repair completed successfully" -ForegroundColor Green
        Write-Host ""
    }

    Write-Host "`n${C_GREEN}SUCCESS: All 4 experiments repaired successfully.${C_RESET}"
    
    if ($Interactive) {
        Write-Host "`nStep complete. The experiment has been automatically repaired." -ForegroundColor Gray
        Read-Host -Prompt "Press Enter to continue..." | Out-Null
    }

    # --- STEP 6: Final verification ---
    $stepHeader = ">>> Step 6/6: Final Verification <<<"
    Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray
    Write-Host $stepHeader -ForegroundColor Blue
    Write-Host "Performs final audit to confirm the experiment is fully restored." -ForegroundColor Blue
    
    if ($Interactive) {
        Write-Host "`n${C_BLUE}Step Summary: This final step verifies that the repair was successful. The audit should now show the experiment as 'VALIDATED' again, proving that the framework can automatically recover from common failure scenarios.${C_RESET}"
        Write-Host "`n${C_GRAY}  VERIFICATION TARGET: Complete experiment integrity${C_RESET}"
        Write-Host ""
        Write-Host "${C_RESET}  EXPECTED RESULT:"
        Write-Host "    - Overall Status: VALIDATED"
        Write-Host "    - All files restored and valid"
        Write-Host "    - Exit Code: 0 (success)"
        
        Read-Host -Prompt "`n${C_ORANGE}Press Enter to execute this step (Ctrl+C to exit)...${C_RESET}" | Out-Null
        Write-Host ""
    }

    # Starting Step 6 execution
    & "$ProjectRoot\audit_experiment.ps1" -ExperimentDirectory $NewExperimentPath -ConfigPath $TestConfigPath
    if ($LASTEXITCODE -ne 0) { throw "Final verification audit failed. Experiment should be VALIDATED." }
    
    if ($Interactive) {
        Write-Host "`n🎉 SUCCESS! The complete experiment lifecycle test passed!" -ForegroundColor Green
        Write-Host "`nWhat we demonstrated:" -ForegroundColor White
        Write-Host "  ✓ Created a new experiment from config" -ForegroundColor Green
        Write-Host "  ✓ Verified it was complete and valid" -ForegroundColor Green  
        Write-Host "  ✓ Simulated a common failure (missing API response)" -ForegroundColor Green
        Write-Host "  ✓ Automatically detected the issue" -ForegroundColor Green
        Write-Host "  ✓ Repaired the experiment by re-running only what was needed" -ForegroundColor Green
        Write-Host "  ✓ Verified the repair was successful" -ForegroundColor Green
        Write-Host "`nYou can inspect the experiment at: $RelativePath" -ForegroundColor Gray
        Read-Host -Prompt "Press Enter to continue to cleanup..." | Out-Null
    } else {
        Write-Host "`nSUCCESS: The full 'new -> audit -> break -> fix' lifecycle completed successfully." -ForegroundColor Green
    }
}
catch {
    Write-Host "`nERROR: Layer 4 test workflow failed.`n$($_.Exception.Message)" -ForegroundColor Red
    # Re-throw the original exception to the master runner.
    throw
}

# === End of tests/testing_harness/experiment_lifecycle/layer4/layer4_phase2_run.ps1 ===
