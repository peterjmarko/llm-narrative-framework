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
# Filename: run_experiment.ps1

<#
.SYNOPSIS
    Runs a complete experimental batch by orchestrating the Python backend.

.DESCRIPTION
    This script is the main user entry point for running a full experimental batch.
    It serves as a user-friendly wrapper for the state-machine controller,
    `experiment_manager.py`.

    The controller will automatically run, repair, or reprocess an experiment
    until it is complete. This script provides a simple interface for starting
    that process, translating PowerShell parameters (like -Verbose) into the
    appropriate arguments for the Python backend.

.PARAMETER TargetDirectory
    The target directory for the experiment. Can be an existing directory or one to
    be created. If not provided, a unique directory is created based on config.ini settings.

.PARAMETER Notes
    A string of notes to embed in the experiment's reports and logs.

.PARAMETER StartRep
    The replication number to start from (e.g., 1).

.PARAMETER EndRep
    The replication number to end at (e.g., 30).

.PARAMETER Verbose
    A switch to enable detailed, real-time output from all underlying Python scripts.
    By default, output is a high-level summary.

.EXAMPLE
    # Run a full batch defined in config.ini.
    .\run_experiment.ps1

.EXAMPLE
    # Run a batch, organizing results into a specific directory with notes.
    .\run_experiment.ps1 -TargetDirectory "output/reports/My_Llama3_Study" -Notes "First run with random mapping"

.EXAMPLE
    # Run only replications 5 through 10 with detailed logging for debugging.
    .\run_experiment.ps1 -StartRep 5 -EndRep 10 -Verbose
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
