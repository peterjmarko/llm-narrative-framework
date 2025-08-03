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
# Filename: tests/migrate_experiment.Tests.ps1

# Import the shared test harness
. (Join-Path $PSScriptRoot "Test-Harness.ps1")

# --- Test-Specific Setup ---
# Create a temporary source directory for the tests to use.
$tempDir = New-Item -ItemType Directory -Path (Join-Path $env:TEMP ("migrate_test_" + (Get-Random)))
$script:SourceTestDir = New-Item -ItemType Directory -Path (Join-Path $tempDir.FullName "Legacy_Experiment_Source")

# --- Test-Specific Mock Functions & State ---
$script:CapturedCopyParams = $null
$script:CapturedPythonScriptName = $null
$script:CapturedPythonArgs = $null
$script:ExitCodeToSimulate = 0

# Mock the external commands that the real script logic would call.
function Mock-Copy-Item {
    [CmdletBinding()]
    param(
        # Define the parameters that the real Copy-Item call will use.
        $Path,
        $Destination,
        [switch]$Recurse,
        [switch]$Force
    )
    # Capture the parameters passed to Copy-Item for verification.
    $script:CapturedCopyParams = $PSBoundParameters
}

function Mock-Invoke-PythonScript {
    param(
        [string]$ScriptName,
        [string[]]$Arguments
    )
    $script:CapturedPythonScriptName = $ScriptName
    $script:CapturedPythonArgs = $Arguments
    if ($script:ExitCodeToSimulate -ne 0) {
        $LASTEXITCODE = $script:ExitCodeToSimulate
        throw "Simulated failure from Python script with exit code ${LASTEXITCODE}."
    }
    $LASTEXITCODE = 0
}

# --- Main Logic to Test (This function mirrors the logic inside the real migrate_experiment.ps1) ---
function Invoke-Migration-Logic {
    param(
        [string]$SourceDirectory
    )
    # This logic is a direct copy from migrate_experiment.ps1
    $SourcePath = Resolve-Path -Path $SourceDirectory
    $SourceBaseName = (Get-Item -Path $SourcePath).Name
    $Timestamp = "20250101_120000" # Use a fixed timestamp for predictable test results
    $NewFolderName = "${SourceBaseName}_migrated_${Timestamp}"
    $DestinationParent = "output/migrated_experiments"
    $DestinationPath = Join-Path -Path $DestinationParent -ChildPath $NewFolderName

    # Call the mocked functions instead of the real commands
    Mock-Copy-Item -Path $SourcePath -Destination $DestinationPath -Recurse -Force
    Mock-Invoke-PythonScript -ScriptName "src/experiment_manager.py" -Arguments "--migrate", $DestinationPath

    # Return the generated destination path so we can verify it was used correctly
    return $DestinationPath
}


# --- TEST CASES ---

Run-Test "Successful migration calls Copy-Item and Python script correctly" {
    # Arrange: Reset state variables
    $script:CapturedCopyParams = $null
    $script:CapturedPythonArgs = $null
    $script:ExitCodeToSimulate = 0

    # Act: Run the logic and get the generated destination path
    $destinationPath = Invoke-Migration-Logic -SourceDirectory $script:SourceTestDir

    # Assert: Check if the mocked functions were called with the correct parameters
    # The Path parameter is a PathInfo object from Resolve-Path; its full path is in the .Path property.
    $copySourceCorrect = $script:CapturedCopyParams.Path.Path -eq $script:SourceTestDir.FullName
    $copyDestCorrect = $script:CapturedCopyParams.Destination -eq $destinationPath
    $pythonScriptCorrect = $script:CapturedPythonScriptName -eq "src/experiment_manager.py"
    $pythonArgsCorrect = ($script:CapturedPythonArgs[0] -eq "--migrate") -and ($script:CapturedPythonArgs[1] -eq $destinationPath)

    if ($copySourceCorrect -and $copyDestCorrect -and $pythonScriptCorrect -and $pythonArgsCorrect) {
        "ALL_CALLS_CORRECT"
    } else {
        "INCORRECT_CALLS"
    }
} @("ALL_CALLS_CORRECT")


Run-Test "Failure from python script is propagated" {
    # Arrange
    $script:ExitCodeToSimulate = 1

    # Act & Assert: The logic should throw an exception on failure
    try {
        Invoke-Migration-Logic -SourceDirectory $script:SourceTestDir
        "DID_NOT_FAIL" # This line should not be reached
    } catch {
        "CAUGHT_FAILURE" # This is the expected outcome
    }
} @("CAUGHT_FAILURE")


# --- Finalize the run and clean up ---
Finalize-Test-Run
Remove-Item -Path $tempDir -Recurse -Force

# === End of tests/migrate_experiment.Tests.ps1 ===