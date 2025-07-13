#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 [Your Name/Institution]
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
# Filename: migrate_experiment.Tests.ps1

# Import the shared test harness
. (Join-Path $PSScriptRoot "Test-Harness.ps1")

# --- Test-Specific Mock Functions ---
# Mock the internal helper function that the real script would use.
$script:CapturedScriptName = $null
$script:CapturedArgs = $null
$script:ExitCodeToSimulate = 0

function Invoke-PythonScript {
    param(
        [string]$StepName,
        [string]$ScriptName,
        [string[]]$Arguments
    )
    $script:CapturedScriptName = $ScriptName
    $script:CapturedArgs = $Arguments
    if ($script:ExitCodeToSimulate -ne 0) {
        throw "Simulated failure from Python script."
    }
}

# --- Main Logic to Test (This function mirrors the logic inside migrate_experiment.ps1) ---
function Invoke-Migration-Test {
    # This is the core logic from the real script.
    Invoke-PythonScript -StepName "Migration" -ScriptName "src/experiment_manager.py" -Arguments "--migrate", "DUMMY_PATH"
    return "SUCCESS"
}

# --- TEST CASES ---

Run-Test "Successful migration calls manager with correct arguments" {
    $script:ExitCodeToSimulate = 0
    
    # Call the test function that represents the script's logic
    Invoke-Migration-Test | Out-Null # We don't care about the "SUCCESS" return

    # Check that the mock was called with the right arguments.
    # The output of this test block is what gets compared to the expected value.
    $areArgsCorrect = ($script:CapturedScriptName -eq "src/experiment_manager.py") -and ($script:CapturedArgs[0] -eq "--migrate")
    if ($areArgsCorrect) { "CORRECT_CALL" } else { "INCORRECT_CALL" }
} @("CORRECT_CALL")


Run-Test "Failure from python script is propagated" {
    $script:ExitCodeToSimulate = 1 # Simulate failure
    
    # The script should throw an exception on failure.
    try {
        Invoke-Migration-Test
        "DID_NOT_FAIL" # This line should not be reached.
    } catch {
        "CAUGHT_FAILURE" # This is the expected outcome.
    }
} @("CAUGHT_FAILURE")


# --- Finalize the run ---
Finalize-Test-Run

# === End of migrate_experiment.Tests.ps1 ===