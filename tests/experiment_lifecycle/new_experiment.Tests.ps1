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
# Filename: tests/experiment_lifecycle/new_experiment.Tests.ps1

. (Join-Path $PSScriptRoot "Test-Harness.ps1")

# --- Test-Specific Function Definitions ---

# Test-specific Invoke-Experiment function (mirrors the updated run_experiment.ps1's function content)
function Invoke-Experiment {
    [CmdletBinding()]
    param(
        [string]$TargetDirectory,
        [int]$StartRep,
        [int]$EndRep,
        [string]$Notes
    )

    $prefixArgs = "run", "python" # Assume PDM for testing consistency
    $pythonArgs = @("src/experiment_manager.py")
    if (-not [string]::IsNullOrEmpty($TargetDirectory)) { $pythonArgs += $TargetDirectory }
    if ($PSBoundParameters.ContainsKey('StartRep')) { $pythonArgs += "--start-rep", $StartRep }
    if ($PSBoundParameters.ContainsKey('EndRep')) { $pythonArgs += "--end-rep", $EndRep }
    if (-not [string]::IsNullOrEmpty($Notes)) { $pythonArgs += "--notes", $Notes }
    if ($PSBoundParameters.ContainsKey('Verbose') -and $PSBoundParameters['Verbose']) {
        $pythonArgs += "--verbose"
    }

    # Return the final arguments that would be passed to the external command.
    return $prefixArgs + $pythonArgs
}

# --- TEST CASES ---

# Test 1: should build default arguments when no parameters are provided
Run-Test "should build default arguments when no parameters are provided" {
    Invoke-Experiment
} @(
    "run", "python",
    "src/experiment_manager.py"
)

# Test 2: should include the --verbose flag when -Verbose is used
Run-Test "should include the --verbose flag when -Verbose is used" {
    Invoke-Experiment -Verbose
} @(
    "run", "python",
    "src/experiment_manager.py",
    "--verbose"
)

# Test 3: should include the target directory as the first argument
Run-Test "should include the target directory as the first argument" {
    Invoke-Experiment -TargetDirectory 'output/my_dir'
} @(
    "run", "python",
    "src/experiment_manager.py",
    "output/my_dir"
)

# Test 4: should include --start-rep and --end-rep flags
Run-Test "should include --start-rep and --end-rep flags" {
    Invoke-Experiment -StartRep 5 -EndRep 10
} @(
    "run", "python",
    "src/experiment_manager.py",
    "--start-rep", 5,
    "--end-rep", 10
)

# Test 5: should include the --notes flag with its value
Run-Test "should include the --notes flag with its value" {
    Invoke-Experiment -Notes "My test notes"
} @(
    "run", "python",
    "src/experiment_manager.py",
    "--notes", "My test notes"
)

# Test 6: should handle a combination of all parameters correctly
Run-Test "should handle a combination of all parameters correctly" {
    Invoke-Experiment -TargetDirectory 'output/combo' -StartRep 1 -EndRep 2 -Notes "Combo test" -Verbose
} @(
    "run", "python",
    "src/experiment_manager.py",
    "output/combo",
    "--start-rep", 1,
    "--end-rep", 2,
    "--notes", "Combo test",
    "--verbose"
)

# --- Finalize the run ---
Finalize-Test-Run

# === End of tests/experiment_lifecycle/new_experiment.Tests.ps1 ===
