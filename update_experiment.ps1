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
# Filename: update_experiment.ps1

<#
.SYNOPSIS
    Updates an existing experiment by regenerating all analysis reports and summary files.

.DESCRIPTION
    This script calls the core 'experiment_manager.py' with the '--reprocess' flag.
    It's the ideal tool for applying analysis updates or bug fixes without re-running
    expensive LLM API calls.

    By default, it shows a summary and prompts for confirmation before running. It will
    warn you if you are forcing an update on an already valid experiment.

.PARAMETER TargetDirectory
    (Required) The path to the experiment directory to update.

.PARAMETER Force
    A switch to bypass the confirmation prompt for automated or scripted use.

.PARAMETER Notes
    (Optional) A string of notes to embed in the reports, useful for documenting why
    the update was performed.

.PARAMETER Verbose
    (Optional) A switch to enable detailed, real-time logging from the underlying Python script.

.EXAMPLE
    # Interactively update an experiment
    .\update_experiment.ps1 -TargetDirectory "output/new_experiments/experiment_20250721_175416"

.EXAMPLE
    # Force a non-interactive update with notes for an automated script
    .\update_experiment.ps1 -TargetDirectory "output/new_experiments/experiment_20250721_175416" -Notes "Applied new bias metric" -Force
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, HelpMessage = "Path to the experiment directory to update.")]
    [ValidateScript({
        if (-not (Test-Path $_ -PathType Container)) {
            throw "The specified TargetDirectory does not exist or is not a directory: $_"
        }
        return $true
    })]
    [string]$TargetDirectory,

    [Parameter(Mandatory = $false)]
    [string]$Notes,

    [Parameter(Mandatory = $false)]
    [switch]$Force
)

# This invocation guard ensures the main execution logic is only triggered
# when the script is run directly (not dot-sourced).
if ($MyInvocation.InvocationName -ne '.') {

    # Use the built-in $PSScriptRoot variable.
    $ScriptRoot = $PSScriptRoot

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

    # --- Display a summary and ask for confirmation (unless -Force is used) ---
    if (-not $Force.IsPresent) {
        Write-Host "`n--- Update Configuration Summary ---" -ForegroundColor Cyan
        Write-Host "Action:            Update an EXISTING experiment (regenerate reports)."
        Write-Host "Target Directory:  $TargetDirectory"
        if ($Notes) { Write-Host "Notes:             $Notes" -ForegroundColor Yellow }
        Write-Host "------------------------------------" -ForegroundColor Cyan

        $choice = Read-Host "`nDo you wish to proceed with the update? (Y/N)"
        if ($choice.Trim().ToLower() -ne 'y') {
            Write-Host "Update aborted by user." -ForegroundColor Yellow
            Write-Host "" # Add a blank line for separation
            exit 0
        }
    }
    
    Write-Host "`n--- Launching Experiment Manager (Update Mode) ---" -ForegroundColor Cyan

    $pythonScriptPath = Join-Path $ScriptRoot "src/experiment_manager.py"
    $pythonArgs = @($pythonScriptPath)

    # Core arguments for this script
    $pythonArgs += "--reprocess"
    $pythonArgs += "--target_dir", $TargetDirectory
    
    # Optional arguments
    if ($PSBoundParameters.ContainsKey('Notes')) { $pythonArgs += "--notes", $Notes }
    if ($PSBoundParameters.ContainsKey('Verbose') -and $PSBoundParameters['Verbose']) {
        $pythonArgs += "--verbose"
    }

    $finalArgs = $prefixArgs + $pythonArgs

    try {
        & $executable $finalArgs
        $exitCode = $LASTEXITCODE

        if ($exitCode -eq 0) {
            Write-Host "`nExperiment update completed successfully for:" -ForegroundColor Green
            Write-Host $TargetDirectory -ForegroundColor Green
        } 
        elseif ($exitCode -eq 99) {
            # This is the special exit code for a user-initiated abort from the Python script.
            # The Python script has already printed the "aborted by user" message,
            # so we just exit gracefully here.
        }
        else {
            # Any other non-zero exit code is a genuine error.
            throw "Experiment Manager exited with an error."
        }

    } catch {
        Write-Host "`n!!! $($_.Exception.Message) Check the output above. !!!" -ForegroundColor Yellow
    }

    # Add a final blank line for clean separation from the next PS prompt.
    Write-Host ""
}

# === End of update_experiment.ps1 ===
