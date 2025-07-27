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
# Filename: new_experiment.ps1

<#
.SYNOPSIS
  Creates and runs a new experiment from scratch based on the global config.ini.

.DESCRIPTION
  This script is the primary entry point for CREATING a new experiment. It reads the
  main 'config.ini' file, then calls the Python backend to generate a new, timestamped
  experiment directory and execute the full set of replications as defined.

  This script does not take a target directory, as its sole purpose is to
  initiate new experimental runs. To repair or resume an existing experiment, use
  'repair_experiment.ps1'. To check an experiment's status, use 'audit_experiment.ps1'.

.PARAMETER Notes
    A string of notes to embed in the new experiment's reports and logs.

.PARAMETER Verbose
    A switch to enable detailed, real-time output from all underlying Python scripts.
    By default, output is a high-level summary.

.EXAMPLE
  # Run a new experiment using the settings from 'config.ini'.
  .\new_experiment.ps1

.EXAMPLE
  # Run a new experiment with notes and detailed logging.
  .\new_experiment.ps1 -Notes "First run with Llama 3 70B" -Verbose
#>

[CmdletBinding()]
param(
    # Optional notes for the run.
    [Parameter(Mandatory=$false)]
    [string]$Notes
)

# This is the main execution function.
function Invoke-NewExperiment {

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

    Write-Host # Add blank line for spacing

    # Ensure console output uses UTF-8.
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

    # Use '#' for banner consistency
    Write-Host ("#" * 80) -ForegroundColor Cyan
    Write-Host "###                 CREATING NEW EXPERIMENT FROM CONFIG.INI                  ###" -ForegroundColor Cyan
    Write-Host ("#" * 80) -ForegroundColor Cyan
    Write-Host

    # Construct the arguments for the Python script.
    # Note: No target directory is passed.
    $pythonArgs = @("src/experiment_manager.py")
    if (-not [string]::IsNullOrEmpty($Notes)) { $pythonArgs += "--notes", $Notes }

    # Translate the common -Verbose parameter to the internal --verbose for Python.
    if ($PSBoundParameters.ContainsKey('Verbose') -and $PSBoundParameters['Verbose']) {
        $pythonArgs += "--verbose"
    }

    # Add the --force-color flag if the calling environment supports it, for better logging.
    if ($Host.UI.SupportsVirtualTerminal) {
        $pythonArgs += "--force-color"
    }
    
    # Combine prefix arguments with the script and its arguments
    $finalArgs = $prefixArgs + $pythonArgs

    # Execute the command with its final argument list
    & $executable $finalArgs

    # Check the exit code from the Python script.
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n!!! The experiment manager exited with an error. Check the output above. !!!" -ForegroundColor Red
    }
}

# This invocation guard ensures the main logic is only triggered when the script is run directly.
if ($MyInvocation.InvocationName -ne '.') {
    Invoke-NewExperiment
}

# === End of new_experiment.ps1 ===
