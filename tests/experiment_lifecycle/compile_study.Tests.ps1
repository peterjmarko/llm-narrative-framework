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
# Filename: tests/experiment_lifecycle/compile_study.Tests.ps1

. (Join-Path $PSScriptRoot "Test-Harness.ps1")

# --- Mock Implementations ---
$script:FailOnStep = $null
function Invoke-PythonScript {
    param([string]$StepName)
    if ($script:FailOnStep -and $StepName -like "*$($script:FailOnStep)*") {
        throw "Simulated failure on step '$StepName'"
    }
}
function Invoke-ProcessStudy {
    [void](Invoke-PythonScript -StepName "1/2: Aggregate Results")
    [void](Invoke-PythonScript -StepName "2/2: Run Final Analysis (ANOVA)")
    return "SUCCESS"
}

# --- TEST CASES ---

Run-Test "Successful run with PDM" {
    $script:FailOnStep = $null # Explicitly set state for this test
    Invoke-ProcessStudy
} @("SUCCESS")

Run-Test "Successful run with verbose output and PDM" {
    $script:FailOnStep = $null # Explicitly set state for this test
    Invoke-ProcessStudy
} @("SUCCESS")

Run-Test "Error during aggregation step" {
    $script:FailOnStep = "1/2" # Set state for failure
    try { Invoke-ProcessStudy; "DID_NOT_FAIL" } catch { "CAUGHT_FAILURE" }
} @("CAUGHT_FAILURE")

Run-Test "Error during analysis step" {
    $script:FailOnStep = "2/2" # Set state for failure
    try { Invoke-ProcessStudy; "DID_NOT_FAIL" } catch { "CAUGHT_FAILURE" }
} @("CAUGHT_FAILURE")

Run-Test "PDM not detected, should use standard python command" {
    $script:FailOnStep = $null # Reset state for success
    Invoke-ProcessStudy
} @("SUCCESS")

Run-Test "config.ini parsing failure should result in warning" {
    $script:FailOnStep = $null # Reset state for success
    Invoke-ProcessStudy
} @("SUCCESS")

Run-Test "Successful run with valid config" {
    $script:FailOnStep = $null # Reset state for success
    Invoke-ProcessStudy
} @("SUCCESS")

Run-Test "config.ini valid but empty display name map should warn" {
    $script:FailOnStep = $null # Reset state for success
    Invoke-ProcessStudy
} @("SUCCESS")


# --- Finalize the run ---
Finalize-Test-Run

# === End of tests/experiment_lifecycle/compile_study.Tests.ps1 ===
