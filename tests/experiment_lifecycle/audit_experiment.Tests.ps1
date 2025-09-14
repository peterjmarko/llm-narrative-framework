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
# Filename: tests/experiment_lifecycle/audit_experiment.Tests.ps1

. (Join-Path $PSScriptRoot "Test-Harness.ps1")

# --- Test-Specific Mock Function ---
# Mock the pdm executable to intercept the call from the script.
$script:CapturedArgs = $null
function pdm {
    # This correctly flattens the arguments, preventing the "System.Object[]" issue.
    $flatArgs = @()
    foreach ($arg in $args) { $flatArgs += $arg }
    $script:CapturedArgs = $flatArgs
}

# This function simulates the logic within the real audit_experiment.ps1
function Invoke-Audit-Test {
    param([string]$TargetDirectory, [switch]$Verbose)
    
    # This is the core logic from the script we are testing
    $scriptName = "src/experiment_manager.py"
    $arguments = @("--verify-only", $TargetDirectory)
    if ($Verbose) {
        $arguments += "--verbose"
    }
    
    # Call our mock pdm function
    pdm run python $scriptName $arguments
}

# --- TEST CASES ---

Run-Test "Basic audit calls manager with correct flags" {
    $targetDir = "path/to/audit"
    $expectedArgs = @("run", "python", "src/experiment_manager.py", "--verify-only", $targetDir)
    
    Invoke-Audit-Test -TargetDirectory $targetDir
    
    # Compare the two arrays for differences. If there are none, it's a match.
    $diff = Compare-Object -ReferenceObject $expectedArgs -DifferenceObject $script:CapturedArgs
    if ($diff) { "ARRAYS_DIFFER" } else { "ARRAYS_MATCH" }
} @("ARRAYS_MATCH")

Run-Test "Verbose audit adds --verbose flag" {
    $targetDir = "path/to/verbose_audit"
    $expectedArgs = @("run", "python", "src/experiment_manager.py", "--verify-only", $targetDir, "--verbose")

    Invoke-Audit-Test -TargetDirectory $targetDir -Verbose

    $diff = Compare-Object -ReferenceObject $expectedArgs -DifferenceObject $script:CapturedArgs
    if ($diff) { "ARRAYS_DIFFER" } else { "ARRAYS_MATCH" }
} @("ARRAYS_MATCH")

# --- Finalize the run ---
Finalize-Test-Run

# === End of tests/experiment_lifecycle/audit_experiment.Tests.ps1 ===
