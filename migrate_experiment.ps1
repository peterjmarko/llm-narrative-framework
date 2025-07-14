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
    Copies a legacy experiment to a new, timestamped directory and upgrades it.

.DESCRIPTION
    This script performs a safe, non-destructive migration. It takes a source
    legacy experiment directory, copies it to a new timestamped folder within
    'output/migrated_experiments/', and then runs the migration process on the
    new copy. The original data is left untouched.

.PARAMETER SourceDirectory
    The path to the root of the old experiment directory that needs to be migrated.

.EXAMPLE
    # Copy and migrate "Legacy_Experiment_1"
    # This creates a folder like "output/migrated_experiments/Legacy_Experiment_1_migrated_20250712_103000"
    .\migrate_experiment.ps1 -SourceDirectory "output/legacy/Legacy_Experiment_1"
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the source legacy experiment directory to migrate.")]
    [string]$SourceDirectory
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
    # 1. Resolve source and automatically determine destination
    $SourcePath = Resolve-Path -Path $SourceDirectory -ErrorAction Stop
    $SourceBaseName = (Get-Item -Path $SourcePath).Name
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $NewFolderName = "${SourceBaseName}_migrated_${Timestamp}"
    $DestinationParent = "output/migrated_experiments"
    $DestinationPath = Join-Path -Path $DestinationParent -ChildPath $NewFolderName

    # Create the parent directory if it doesn't exist
    if (-not (Test-Path -Path $DestinationParent)) {
        New-Item -ItemType Directory -Path $DestinationParent -Force | Out-Null
    }

    # 2. Copy the experiment to the new location
    Write-Host "`n######################################################" -ForegroundColor Green
    Write-Host "### Step 1/2: Copying Experiment Data" -ForegroundColor Green
    Write-Host "######################################################`n"
    Write-Host "Source:      $SourcePath"
    Write-Host "Destination: $DestinationPath"
    Copy-Item -Path $SourcePath -Destination $DestinationPath -Recurse -Force
    Write-Host "`nCopy complete."

    # 3. Run the migration process on the new copy
    Write-Host "`n######################################################" -ForegroundColor Green
    Write-Host "### Step 2/2: Migrating New Experiment Copy" -ForegroundColor Green
    Write-Host "######################################################`n"
    
    $scriptName = "src/experiment_manager.py"
    $arguments = "--migrate", $DestinationPath
    $finalArgs = $prefixArgs + $scriptName + $arguments

    Write-Host "Executing: $executable $($finalArgs -join ' ')"
    & $executable $finalArgs

    if ($LASTEXITCODE -ne 0) {
        throw "ERROR: Migration process failed with exit code ${LASTEXITCODE}."
    }

    Write-Host "`n######################################################" -ForegroundColor Green
    Write-Host "### Migration Finished Successfully! ###" -ForegroundColor Green
    Write-Host "### Migrated data is in: '$($DestinationPath)'" -ForegroundColor Green
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