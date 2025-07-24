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
    Starts a new experiment or resumes/repairs an existing one.

.DESCRIPTION
    This is the main user entry point for running a full experimental batch. It calls
    the core 'experiment_manager.py' state machine, which intelligently handles the
    entire lifecycle: creating new replications, repairing failed runs, or resuming
    an interrupted process.

    By default, it shows a detailed configuration summary and prompts for confirmation
    before starting. You can override core parameters from 'config.ini' directly
    on the command line (e.g., -ModelName, -Temperature).

.PARAMETER TargetDirectory
    The target directory for the experiment. If an existing directory is specified,
    the script will attempt to resume or repair it. If not specified, a new,
    unique directory is created.

.PARAMETER Force
    A switch to bypass the confirmation prompt for automated runs.

.PARAMETER Notes
    A string of notes to embed in the experiment's reports and logs.

.PARAMETER StartRep
    The replication number to start from (e.g., 1).

.PARAMETER EndRep
    The replication number to end at (e.g., 30).

.PARAMETER ModelName
    Overrides the 'model_name' from config.ini.

.PARAMETER Temperature
    Overrides the 'temperature' from config.ini.

.PARAMETER MappingStrategy
    Overrides the 'mapping_strategy' from config.ini. Accepts 'correct' or 'random'.

.PARAMETER GroupSize
    Overrides the 'group_size' (k) from config.ini.

.PARAMETER Verbose
    A switch to enable detailed, real-time output from the underlying Python script.

.EXAMPLE
    # Start a new experiment using all defaults from config.ini.
    .\run_experiment.ps1

.EXAMPLE
    # Start a new experiment, overriding the model and disabling the confirmation prompt.
    .\run_experiment.ps1 -ModelName "google/gemini-flash-1.5" -Force

.EXAMPLE
    # Resume or repair an existing experiment.
    .\run_experiment.ps1 -TargetDirectory "output/new_experiments/experiment_20250721_175416"

.EXAMPLE
    # Resume an experiment, but only run replications 15 through 30.
    .\run_experiment.ps1 -TargetDirectory "output/new_experiments/experiment_20250721_175416" -StartRep 15 -EndRep 30
#>

[CmdletBinding()]
param(
    # The target directory for the experiment.
    [Parameter(Mandatory=$false)]
    [string]$TargetDirectory,

    # Optional starting replication number.
    [Parameter(Mandatory=$false)]
    [int]$StartRep,

    # Optional ending replication number.
    [Parameter(Mandatory=$false)]
    [int]$EndRep,

    # Optional notes for the run.
    [Parameter(Mandatory=$false)]
    [string]$Notes,

    # --- Command-line overrides for experiment parameters ---
    [Parameter(Mandatory=$false, HelpMessage="Override the model name from config.ini.")]
    [string]$ModelName,

    [Parameter(Mandatory=$false, HelpMessage="Override the temperature from config.ini.")]
    [double]$Temperature,

    [Parameter(Mandatory=$false, HelpMessage="Override the mapping strategy from config.ini.")]
    [ValidateSet("correct", "random")]
    [string]$MappingStrategy,

    [Parameter(Mandatory=$false, HelpMessage="Override the group size (k) from config.ini.")]
    [int]$GroupSize,

    # A switch to bypass the confirmation prompt for automated runs.
    [Parameter(Mandatory=$false)]
    [switch]$Force
)

# This invocation guard ensures the main execution logic is only triggered
# when the script is run directly (not dot-sourced).
if ($MyInvocation.InvocationName -ne '.') {
    
    # Use the built-in $PSScriptRoot variable. It's the most reliable way
    # to get the script's directory and avoids parsing errors.
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
        # Helper function to call the Python utility script for reading config.ini
        function Get-IniValue($Section, $Key) {
            $utilityScriptPath = Join-Path $PSScriptRoot "src/print_config_value.py"
            $cmdArgs = $prefixArgs + @($utilityScriptPath, $Section, $Key)
            $value = (& $executable $cmdArgs 2>$null).Trim()
            return $value
        }

        # Determine the intended action based on the target directory.
        $ActionDescription = ""
        if (-not $PSBoundParameters.ContainsKey('TargetDirectory')) {
            $ActionDescription = "Create a new experiment in an auto-generated directory."
        } elseif (Test-Path -Path $TargetDirectory -PathType Container) {
            $ActionDescription = "Resume or repair an EXISTING experiment."
        } else {
            $ActionDescription = "Create a new experiment in the specified directory."
        }

        Write-Host "`n--- Experiment Configuration Summary ---" -ForegroundColor Cyan
        
        # --- Action and Target ---
        Write-Host "Action:            $ActionDescription"
        Write-Host "Target Directory:  " -NoNewline; if ($TargetDirectory) { Write-Host $TargetDirectory } else { Write-Host "(auto-generated)" }
        Write-Host "Replications:      " -NoNewline; if ($PSBoundParameters.ContainsKey('StartRep') -or $PSBoundParameters.ContainsKey('EndRep')) { Write-Host "$StartRep to $EndRep" -ForegroundColor Yellow } else { $default = Get-IniValue "Study" "num_replications"; Write-Host "1 to $default (full experiment)" }
        
        # --- Core Scientific Parameters ---
        if ($PSBoundParameters.ContainsKey('MappingStrategy')) { Write-Host "Mapping Strategy:  $MappingStrategy (override)" -ForegroundColor Yellow } else { $default = Get-IniValue "Study" "mapping_strategy"; Write-Host "Mapping Strategy:  $default (from config.ini)" }
        if ($PSBoundParameters.ContainsKey('GroupSize')) { Write-Host "Group Size (k):    $GroupSize (override)" -ForegroundColor Yellow } else { $default = Get-IniValue "Study" "group_size"; Write-Host "Group Size (k):    $default (from config.ini)" }

        # --- LLM Parameters ---
        if ($PSBoundParameters.ContainsKey('ModelName')) { Write-Host "Model Name:        $ModelName (override)" -ForegroundColor Yellow } else { $default = Get-IniValue "LLM" "model_name"; Write-Host "Model Name:        $default (from config.ini)" }
        if ($PSBoundParameters.ContainsKey('Temperature')) { Write-Host "Temperature:       $Temperature (override)" -ForegroundColor Yellow } else { $default = Get-IniValue "LLM" "temperature"; Write-Host "Temperature:       $default (from config.ini)" }

        # --- Optional Notes ---
        if ($PSBoundParameters.ContainsKey('Notes')) { Write-Host "Notes:             $Notes" -ForegroundColor Yellow }

        Write-Host "------------------------------------" -ForegroundColor Cyan

        $choice = Read-Host "`nDo you wish to run the experiment with these settings? (Y/N)"
        if ($choice.Trim().ToLower() -ne 'y') {
            Write-Host "Experiment aborted by user." -ForegroundColor Yellow
            Write-Host "" # Add a blank line for separation after aborting
            return 
        }
    }

    Write-Host "`n--- Launching Experiment Manager ---" -ForegroundColor Cyan

    # Construct the Python arguments directly here.
    $pythonScriptPath = Join-Path $ScriptRoot "src/experiment_manager.py"
    $pythonArgs = @($pythonScriptPath)

    # These 'if' blocks will now work correctly because they are at the script's
    # top level, where $PSBoundParameters is correctly populated.
    if ($PSBoundParameters.ContainsKey('TargetDirectory')) { $pythonArgs += "--target_dir", $TargetDirectory }
    if ($PSBoundParameters.ContainsKey('StartRep')) { $pythonArgs += "--start-rep", $StartRep }
    if ($PSBoundParameters.ContainsKey('EndRep')) { $pythonArgs += "--end-rep", $EndRep }
    if ($PSBoundParameters.ContainsKey('Notes')) { $pythonArgs += "--notes", $Notes }
    
    # Add command-line overrides for experiment parameters if they were provided
    if ($PSBoundParameters.ContainsKey('ModelName')) { $pythonArgs += "--model_name", $ModelName }
    if ($PSBoundParameters.ContainsKey('Temperature')) { $pythonArgs += "--temperature", $Temperature }
    if ($PSBoundParameters.ContainsKey('MappingStrategy')) { $pythonArgs += "--mapping_strategy", $MappingStrategy }
    if ($PSBoundParameters.ContainsKey('GroupSize')) { $pythonArgs += "--group_size", $GroupSize }
    
    # Handle Verbose switch
    if ($PSBoundParameters.ContainsKey('Verbose') -and $PSBoundParameters['Verbose']) {
        $pythonArgs += "--verbose"
    }

    # Combine prefix arguments with the script and its arguments
    $finalArgs = $prefixArgs + $pythonArgs

    # Execute the command with its final argument list
    & $executable $finalArgs

    # Check the exit code from the Python script.
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        Write-Host "`n--- PowerShell launcher script finished. ---"
    } 
    elseif ($exitCode -eq 99) {
        # This is the special exit code for a user-initiated abort from the Python script.
        # The Python script has already printed the "aborted by user" message.
        Write-Host "`n--- PowerShell launcher script finished. ---"
    }
    else {
        # Any other non-zero exit code is a genuine error.
        Write-Host "`n!!! Experiment Manager exited with an error. Check the output above. !!!" -ForegroundColor Yellow
    }
    
    # Add a final blank line for clean separation from the next PS prompt.
    Write-Host ""
}

# === End of run_experiment.ps1 ===
