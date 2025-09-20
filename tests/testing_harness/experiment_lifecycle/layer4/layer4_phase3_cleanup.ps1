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
    Write-Host "The experiment lifecycle test has completed successfully!" -ForegroundColor Green
    Write-Host "This final phase will clean up the test environment while preserving the experiment for inspection."
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

Write-Host "Note: Test experiment preserved in production directory 'output/new_experiments'."
Write-Host "      This allows inspection of the full experiment lifecycle results."

if ($Interactive) {
    Write-Host "`nGuided cleanup complete!" -ForegroundColor Green
    Write-Host "Thank you for taking the Layer 4 Interactive Tour. You've seen how the framework:"
    Write-Host "  • Creates experiments reliably"
    Write-Host "  • Diagnoses issues automatically"  
    Write-Host "  • Repairs corruption intelligently"
    Write-Host "  • Maintains data integrity throughout"
    Write-Host ""
} else {
    Write-Host "`nCleanup complete." -ForegroundColor Green
}
Write-Host ""
}
catch {
    Write-Host "`nERROR: Layer 4 cleanup script failed.`n$($_.Exception.Message)" -ForegroundColor Red
    # Re-throw the original exception to the master runner.
    throw
}

# === End of tests/testing_harness/experiment_lifecycle/layer4/layer4_phase3_cleanup.ps1 ===
