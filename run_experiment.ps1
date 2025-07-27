#!/usr/bin/env pwsh
#-*- coding: utf-8 -*-
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
# Filename: run_experiment.ps1

<#
.SYNOPSIS
    Repairs or resumes an existing experiment by running missing replications.

.DESCRIPTION
    This script is the main entry point for REPAIRING or RESUMING an existing
    experiment. It serves as a user-friendly wrapper for the state-machine controller,
    `experiment_manager.py`, operating on a specified target directory.

    The controller will automatically detect and execute only the missing or
    incomplete parts of the experiment until all raw data is present.

    To create a new experiment from scratch, use 'new_experiment.ps1'.

.PARAMETER TargetDirectory
    The path to the existing experiment directory that needs to be repaired or resumed.

.PARAMETER Notes
    A string of notes to embed in the reports and logs of any newly generated replications.

.PARAMETER StartRep
    The replication number to start from (e.g., 15). Useful for resuming a specific portion of a large batch.

.PARAMETER EndRep
    The replication number to end at (e.g., 30).

.PARAMETER Verbose
    A switch to enable detailed, real-time output from all underlying Python scripts.

.EXAMPLE
    # Resume an interrupted experiment, completing all missing replications.
    .\run_experiment.ps1 -TargetDirectory "output/new_experiments/experiment_20250728_103000"

.EXAMPLE
    # Run only replications 15 through 20 in a specific experiment directory.
    .\run_experiment.ps1 -TargetDirectory "output/new_experiments/experiment_20250728_103000" -StartRep 15 -EndRep 20 -Verbose
#>

[CmdletBinding()]
param(
    # The target directory for the experiment. Can be an existing directory
    # or one to be created. This is the first positional parameter.
    [Parameter(Position=0, Mandatory=$false)]
    [string]$TargetDirectory,

    # Optional starting replication number.
    [Parameter(Mandatory=$false)]
    [int]$StartRep,

    # Optional ending replication number.
    [Parameter(Mandatory=$false)]
    [int]$EndRep,

    # Optional notes for the run.
    [Parameter(Mandatory=$false)]
    [string]$Notes
)

# This is the main execution function. It uses the script-level parameters defined above.
function Invoke-Experiment {
    
    # --- Auto-detect execution environment ---
    $executable = "python"
    $prefixArgs = @()
    if (Get-Command pdm -ErrorAction SilentlyContinue) {
        Write-Host "PDM detected. Using 'pdm run' to execute Python scripts." -ForegroundColor Cyan
        $executable = "pdm"
        $prefixArgs = "run", "python"
    }
    else {
        Write-Host "PDM not detected. Using standard 'python' command." -ForegroundColor Yellow
    }

    # Ensure console output uses UTF-8 to correctly display any special characters.
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

    Write-Host "--- Launching Python Batch Runner ---" -ForegroundColor Green

    # Construct the Python arguments directly here (logic formerly in ArgBuilder.ps1).
    $pythonArgs = @("src/experiment_manager.py")
    if (-not [string]::IsNullOrEmpty($TargetDirectory)) { $pythonArgs += $TargetDirectory }
    if ($StartRep) { $pythonArgs += "--start-rep", $StartRep }
    if ($EndRep) { $pythonArgs += "--end-rep", $EndRep }
    if (-not [string]::IsNullOrEmpty($Notes)) { $pythonArgs += "--notes", $Notes }
    
    # Translate the common -Verbose parameter to the internal --verbose for the Python script.
    # $PSBoundParameters contains common parameters when CmdletBinding is used.
    if ($PSBoundParameters.ContainsKey('Verbose') -and $PSBoundParameters['Verbose']) {
        $pythonArgs += "--verbose"
    }

    # Combine prefix arguments with the script and its arguments
    $finalArgs = $prefixArgs + $pythonArgs

    # Execute the command with its final argument list
    & $executable $finalArgs

    # Check the exit code from the Python script.
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n!!! The Python batch runner exited with an error. Check the output above. !!!" -ForegroundColor Yellow
    } else {
        Write-Host "`n--- PowerShell launcher script finished. ---"
    }
}

# This invocation guard ensures the main execution logic is only triggered
# when the script is run directly (not dot-sourced).
if ($MyInvocation.InvocationName -ne '.') {
    # Call the main function. It will have access to the script-level parameters.
    Invoke-Experiment
}

# === End of run_experiment.ps1 ===
