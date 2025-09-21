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
# Filename: tests/testing_harness/experiment_lifecycle/layer4/layer4_phase3_cleanup.ps1

param(
    [switch]$Interactive
)

# --- Define ANSI Color Codes ---
$C_RESET = "`e[0m"
$C_ORANGE = "`e[38;5;208m"
$C_GREEN = "`e[92m"
$C_CYAN = "`e[96m"
$C_MAGENTA = "`e[95m"

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer4_sandbox"
$NewExperimentsDir = Join-Path $ProjectRoot "output/new_experiments"

Write-Host ""
if ($Interactive) {
    Write-Host "--- Layer 4: Experiment Lifecycle Integration Testing ---" -ForegroundColor Magenta
    Write-Host "--- Phase 3: Guided Cleanup ---" -ForegroundColor Cyan
    Write-Host ""
    
    # Check if any experiments were created (indicates test completion vs interruption)
    $experimentsCreated = Test-Path (Join-Path $SandboxDir "experiments") -PathType Container
    if ($experimentsCreated -and (Get-ChildItem -Path (Join-Path $SandboxDir "experiments") -Directory -ErrorAction SilentlyContinue).Count -gt 0) {
        Write-Host "The experiment lifecycle test has completed successfully!" -ForegroundColor Green
        Write-Host "This final phase will clean up the test environment while preserving the experiment for inspection."
    } else {
        Write-Host "Test was interrupted. Cleaning up partial test environment..." -ForegroundColor Yellow
        Write-Host "This cleanup will remove any partial artifacts that were created."
    }
    Write-Host ""
    Read-Host -Prompt "${C_ORANGE}Press Enter to begin cleanup...${C_RESET}" | Out-Null
} else {
    Write-Host "--- Layer 4 Integration Testing: Experiment Creation ---" -ForegroundColor Magenta
    Write-Host "--- Phase 3: Automated Cleanup ---" -ForegroundColor Cyan
    Write-Host ""
}

try {
    if (Test-Path $SandboxDir) {
    Write-Host "Removing Layer 4 sandbox directory..."
    Remove-Item -Path $SandboxDir -Recurse -Force
    Write-Host "  -> Done."
} else {
    Write-Host "Layer 4 sandbox directory not found. Nothing to remove."
}

Write-Host "Note: Test experiment removed with sandbox cleanup."
Write-Host "      All test artifacts are contained in temp_test_environment."

# Copy created experiments to permanent test assets as a complete study for Layer 5 use
$experimentsDir = Join-Path $SandboxDir "experiments"
$testAssetsStudyDir = Join-Path $ProjectRoot "tests/assets/layer4_factorial_study"

if (Test-Path $experimentsDir) {
    $experiments = Get-ChildItem -Path $experimentsDir -Directory -Filter "experiment_*"
    if ($experiments.Count -eq 4) {
        # Create/clean the test study directory
        if (Test-Path $testAssetsStudyDir) {
            Remove-Item -Path $testAssetsStudyDir -Recurse -Force
        }
        New-Item -ItemType Directory -Path $testAssetsStudyDir -Force | Out-Null
        
        # Copy all 4 experiments to create a complete factorial study
        foreach ($experiment in $experiments) {
            $destPath = Join-Path $testAssetsStudyDir $experiment.Name
            Copy-Item -Path $experiment.FullName -Destination $destPath -Recurse -Force
            Write-Host "  -> Archived experiment: $($experiment.Name)" -ForegroundColor Cyan
        }
        
        # Create a study metadata file to document the factorial design
        $studyMetadata = @{
            study_type = "2x2_factorial_design"
            factors = @{
                mapping_strategy = @("correct", "random")
                group_size = @(4, 10)
            }
            experiment_count = 4
            created_by = "Layer4_test_harness"
            created_date = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        }
        $studyMetadata | ConvertTo-Json -Depth 3 | Set-Content -Path (Join-Path $testAssetsStudyDir "STUDY_metadata.json") -Encoding UTF8
        
        Write-Host "Created complete 2x2 factorial study with $($experiments.Count) experiments for Layer 5 integration." -ForegroundColor Green
    } elseif ($experiments.Count -gt 0) {
        Write-Host "Warning: Expected 4 experiments for factorial study, but found $($experiments.Count). Study not created." -ForegroundColor Yellow
    }
}

if ($Interactive) {
    # Check if any experiments were created (indicates test completion)
    $experimentsCreated = Test-Path (Join-Path $SandboxDir "experiments") -PathType Container
    if ($experimentsCreated -and (Get-ChildItem -Path (Join-Path $SandboxDir "experiments") -Directory -ErrorAction SilentlyContinue).Count -gt 0) {
        Write-Host "`nGuided cleanup complete!" -ForegroundColor Green
        Write-Host "Thank you for taking the Layer 4 Interactive Tour. You've seen how the framework:"
        Write-Host "  • Creates experiments reliably"
        Write-Host "  • Diagnoses issues automatically"  
        Write-Host "  • Repairs corruption intelligently"
        Write-Host "  • Maintains data integrity throughout"
        Write-Host "`nLayer 4 test completed successfully.`n" -ForegroundColor Green
    } else {
        Write-Host "`nCleanup complete. Test environment removed.`n" -ForegroundColor Green
    }
} else {
    Write-Host "`nCleanup complete.`n" -ForegroundColor Green
}
Write-Host ""
}
catch {
    Write-Host "`nERROR: Layer 4 cleanup script failed.`n$($_.Exception.Message)" -ForegroundColor Red
    # Re-throw the original exception to the master runner.
    throw
}

# === End of tests/testing_harness/experiment_lifecycle/layer4/layer4_phase3_cleanup.ps1 ===
