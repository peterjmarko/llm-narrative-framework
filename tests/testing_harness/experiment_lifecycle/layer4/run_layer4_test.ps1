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
# Filename: tests/testing_harness/experiment_lifecycle/layer4/run_layer4_test.ps1

param (
    [switch]$SkipCleanup,
    [switch]$Interactive
)

# --- Define ANSI Color Codes (matching Layer 3) ---
$C_RESET = "`e[0m"
$C_GRAY = "`e[90m"
$C_MAGENTA = "`e[95m"
$C_RED = "`e[91m"
$C_ORANGE = "`e[38;5;208m"
$C_YELLOW = "`e[93m"
$C_GREEN = "`e[92m"
$C_CYAN = "`e[96m"
$C_BLUE = "`e[94m"

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot

try {
    if ($Interactive) {
        Write-Host "`n--- Layer 4: Experiment Lifecycle Integration Testing ---" -ForegroundColor Magenta
        Write-Host "--- Interactive Mode: Guided Tour ---" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Welcome to the Layer 4 Interactive Test (Guided Tour)." -ForegroundColor Cyan
        Write-Host "This test demonstrates the experiment lifecycle using a 2x2 factorial design in a safe, isolated sandbox."
        Write-Host "It will create 4 experiments (mapping_strategy x group_size: correct/random x 4/10 subjects)."
        Write-Host "The test consists of three phases:"
        Write-Host "  1. Setup:      Creates a temporary sandbox with test data and configuration"
        Write-Host "  2. Execution:  Demonstrates the full 'new -> audit -> break -> fix' lifecycle with 4 failure scenarios"
        Write-Host "  3. Cleanup:    Archives the 4 experiments and removes the sandbox"
        Write-Host "Note: The test does not compile the 4 experiments into a complete study."
        Write-Host ""
        Read-Host -Prompt "${C_ORANGE}Press Enter to begin the Setup phase...${C_RESET}" | Out-Null
        
        Write-Host "--- Phase 1: Automated Setup ---" -ForegroundColor Cyan
        & "$ScriptDir\layer4_phase1_setup.ps1" -Interactive
        
        Write-Host "---" -ForegroundColor DarkGray
        Write-Host "Phase 1 (Setup) is complete. The test environment has been created." -ForegroundColor Cyan
        Write-Host "Next, we will begin Phase 2 (Execution), which will demonstrate the experiment lifecycle."
        Write-Host ""
        Write-Host "You will be prompted to continue before each major step."
        Write-Host ""
        [Console]::Write("${C_ORANGE}Press Enter to begin the Execution phase...${C_RESET} ")
        Read-Host | Out-Null
        
        & "$ScriptDir\layer4_phase2_run.ps1" -Interactive
    } else {
        # Phase 1: Setup
        & "$ScriptDir\layer4_phase1_setup.ps1"

        # Phase 2: Run the test workflow
        & "$ScriptDir\layer4_phase2_run.ps1"
    }
}
catch {
    Write-Host "`nFATAL: Layer 4 test run failed." -ForegroundColor Red
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    # Exit with a non-zero status code to fail CI/CD pipelines
    exit 1
}
finally {
    # Phase 3: Cleanup
    if (-not $SkipCleanup) {
        if ($Interactive) {
            & "$ScriptDir\layer4_phase3_cleanup.ps1" -Interactive
        } else {
            & "$ScriptDir\layer4_phase3_cleanup.ps1"
        }
    } else {
        Write-Host "`nCleanup skipped due to -SkipCleanup flag." -ForegroundColor Yellow
    }
    
    # Final messaging is handled by the cleanup script based on completion status
}

# === End of tests/testing_harness/experiment_lifecycle/layer4/run_layer4_test.ps1 ===
