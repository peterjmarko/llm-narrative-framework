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
  main 'config.ini' file, calls the Python backend to generate a new, timestamped
  experiment directory, and executes the full set of replications.

  Upon successful completion, it automatically runs a final verification audit to
  provide immediate confirmation of the new experiment's status.

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
# --- Auto-detect execution environment ---
$executable = "python"
$prefixArgs = @()
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    Write-Host "`nPDM detected. Using 'pdm run' to execute Python scripts." -ForegroundColor Cyan
    $executable = "pdm"
    $prefixArgs = "run", "python"
}
else {
    Write-Host "PDM not detected. Using standard 'python' command." -ForegroundColor Yellow
}

# This is the main execution function.
function Invoke-NewExperiment {

    # --- Helper function to create standardized headers ---
    function Write-Header {
        param(
            [string[]]$Lines,
            [string]$Color = "White",
            [int]$Width = 80
        )
        $separator = "#" * $Width
        Write-Host "`n$separator" -ForegroundColor $Color
        foreach ($line in $Lines) {
            if ($line.Length -gt ($Width - 8)) {
                Write-Host "### $($line) " -ForegroundColor $Color
            } else {
                $paddingLength = $Width - $line.Length - 6
                $leftPad = [math]::Floor($paddingLength / 2)
                $rightPad = [math]::Ceiling($paddingLength / 2)
                $formattedLine = "###" + (" " * $leftPad) + $line + (" " * $rightPad) + "###"
                Write-Host $formattedLine -ForegroundColor $Color
            }
        }
        Write-Host $separator -ForegroundColor $Color
        Write-Host ""
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
    $pythonExitCode = $LASTEXITCODE

    # Check the exit code from the Python script.
    if ($pythonExitCode -ne 0) {
        Write-Host "`n!!! The experiment manager exited with an error. Check the output above. !!!" -ForegroundColor Red
        exit $pythonExitCode
    }

    # --- Verification Step ---
    # After a successful run, find the newly created directory and audit it.
    try {
        $basePath = "output\new_experiments"
        $latestExperiment = Get-ChildItem -Path $basePath -Directory | Sort-Object CreationTime -Descending | Select-Object -First 1
        
        if ($null -ne $latestExperiment) {
            Write-Header -Lines "Verifying Final Experiment State" -Color Cyan
            $finalAuditArgs = @("src/experiment_auditor.py", $latestExperiment.FullName, "--force-color", "--non-interactive")
            & $executable $prefixArgs $finalAuditArgs
        }
    } catch {
        Write-Warning "Could not automatically verify the new experiment. Please run audit_experiment.ps1 manually."
    }
}

# This invocation guard ensures the main logic is only triggered when the script is run directly.
if ($MyInvocation.InvocationName -ne '.') {
    Invoke-NewExperiment
}

# === End of new_experiment.ps1 ===
