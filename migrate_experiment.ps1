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
# Filename: migrate_experiment.ps1

<#
.SYNOPSIS
    Upgrades a legacy experiment directory by calling the central experiment manager in migrate mode.

.DESCRIPTION
    This script is a simple wrapper for the main 'experiment_manager.py' script.
    It passes the --migrate flag to the manager, which then orchestrates the entire
    data migration process to make old data compatible with the current pipeline.

.PARAMETER TargetDirectory
    The path to the root of the old experiment directory that needs to be migrated.

.EXAMPLE
    # To migrate the experiment data in the "6_Study_4" directory:
    .\migrate_experiment.ps1 -TargetDirectory "output/reports/6_Study_4"
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the old experiment directory.")]
    [string]$TargetDirectory
)

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

# --- Main Script Logic ---
try {
    # Resolve the path to ensure it's absolute and check for existence
    $ResolvedPath = Resolve-Path -Path $TargetDirectory -ErrorAction Stop

    Write-Host "`n######################################################" -ForegroundColor Green
    Write-Host "### Starting Data Migration for: '$($ResolvedPath)'" -ForegroundColor Green
    Write-Host "######################################################`n" -ForegroundColor Green

    # This script is now a simple wrapper for the experiment manager's migrate mode.
    $scriptName = "src/experiment_manager.py"
    $arguments = "--migrate", $ResolvedPath
    $finalArgs = $prefixArgs + $scriptName + $arguments

    Write-Host "Executing: $executable $($finalArgs -join ' ')"
    & $executable $finalArgs

    if ($LASTEXITCODE -ne 0) {
        throw "ERROR: Migration process failed with exit code ${LASTEXITCODE}."
    }

    Write-Host "`n######################################################" -ForegroundColor Green
    Write-Host "### Migration Finished Successfully! ###" -ForegroundColor Green
    Write-Host "######################################################`n" -ForegroundColor Green

}
catch {
    Write-Host "`n######################################################" -ForegroundColor Red
    Write-Host "### MIGRATION FAILED ###" -ForegroundColor Red
    Write-Host "######################################################" -ForegroundColor Red
    Write-Error $_.Exception.Message
    exit 1
}

# === End of migrate_experiment.ps1 ===