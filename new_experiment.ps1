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
    [Parameter(Mandatory=$false)]
    [string]$Notes,

    [Parameter(Mandatory=$false)]
    [Alias('config-path')]
    [string]$ConfigPath
)

function Get-ProjectRoot {
    $currentDir = Get-Location
    while ($currentDir -ne $null -and $currentDir.Path -ne "") {
        if (Test-Path (Join-Path $currentDir.Path "pyproject.toml")) { return $currentDir.Path }
        $currentDir = Split-Path -Parent -Path $currentDir.Path
    }
    throw "FATAL: Could not find project root (pyproject.toml)."
}

function Write-Header { param([string[]]$Lines, [string]$Color = "White"); $s = "#" * 80; Write-Host "`n$s" -F $Color; foreach ($l in $Lines) { $pL = [math]::Floor((80 - $l.Length - 6) / 2); $pR = [math]::Ceiling((80 - $l.Length - 6) / 2); Write-Host "###$(' ' * $pL)$l$(' ' * $pR)###" -F $Color }; Write-Host $s -F $Color; Write-Host "" }

$ProjectRoot = Get-ProjectRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Header -Lines "CREATING NEW EXPERIMENT FROM CONFIG.INI" -Color Cyan

$pythonScriptPath = Join-Path $ProjectRoot "src/experiment_manager.py"
$pythonArgs = @($pythonScriptPath)
if (-not [string]::IsNullOrEmpty($Notes)) { $pythonArgs += "--notes", $Notes }
if ($PSBoundParameters.ContainsKey('Verbose') -and $PSBoundParameters['Verbose']) { $pythonArgs += "--verbose" }
if ($Host.UI.SupportsVirtualTerminal) { $pythonArgs += "--force-color" }
if (-not [string]::IsNullOrEmpty($ConfigPath)) { $pythonArgs += "--config-path", $ConfigPath }

& pdm run python $pythonArgs
$pythonExitCode = $LASTEXITCODE

if ($pythonExitCode -ne 0) {
    Write-Host "`n!!! The experiment manager exited with an error. Check the output above. !!!" -ForegroundColor Red
    exit $pythonExitCode
}

try {
    # Read the output directory from config instead of hardcoding
    $basePath = Join-Path $ProjectRoot "output/new_experiments"  # Default fallback
    
    if (-not [string]::IsNullOrEmpty($ConfigPath) -and (Test-Path $ConfigPath)) {
        # Parse config to get the actual output directory
        $configContent = Get-Content $ConfigPath -Raw
        if ($configContent -match '(?m)^base_output_dir\s*=\s*(.+)$') {
            $baseOutputDir = $matches[1].Trim()
            if ($configContent -match '(?m)^new_experiments_subdir\s*=\s*(.+)$') {
                $newExperimentsSubdir = $matches[1].Trim()
                $basePath = Join-Path $ProjectRoot (Join-Path $baseOutputDir $newExperimentsSubdir)
            }
        }
    }
    
    $latestExperiment = Get-ChildItem -Path $basePath -Directory | Sort-Object CreationTime -Descending | Select-Object -First 1
    if ($null -ne $latestExperiment) {
        Write-Header -Lines "Verifying Final Experiment State" -Color Cyan
        $auditScriptPath = Join-Path $ProjectRoot "audit_experiment.ps1"
        
        # Use a hashtable for splatting to ensure named parameters are passed robustly.
        $auditSplat = @{
            ExperimentDirectory = $latestExperiment.FullName
        }
        if (-not [string]::IsNullOrEmpty($ConfigPath)) {
            $auditSplat['ConfigPath'] = $ConfigPath
        }
        & $auditScriptPath @auditSplat
    }
} catch {
    Write-Warning "Could not automatically verify the new experiment."
}

# === End of new_experiment.ps1 ===
