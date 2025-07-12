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
# Filename: migrate_old_experiment.ps1

<#
.SYNOPSIS
    Upgrades a legacy experiment directory to be compatible with the current analysis pipeline.

.DESCRIPTION
    This script orchestrates a full, four-step data migration process. It ensures
    that old experimental data can be analyzed using the latest tools. The steps are:
    1.  Patch Configs: Runs 'patch_old_experiment.py' to create missing config archives.
    2.  Rebuild Reports: Runs 'rebuild_reports.py' to update all reports to the modern format.
    3.  Clean Artifacts: Deletes obsolete summary files and temporary data.
    4.  Final Reprocess: Runs 'experiment_manager.py --reprocess' to generate new, clean summary files.

.PARAMETER TargetDirectory
    The path to the root of the old experiment directory that needs to be migrated.

.EXAMPLE
    # To migrate the experiment data in the "6_Study_4" directory:
    .\migrate_old_experiment.ps1 -TargetDirectory "output/reports/6_Study_4"
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

# --- Function to execute a Python script using the detected executor, and check for errors ---
function Invoke-PythonScript {
    param (
        [string]$StepName,
        [string]$ScriptName,
        [string[]]$Arguments
    )
    
    # Combine prefix arguments with the script and its arguments
    $finalArgs = $prefixArgs + $ScriptName + $Arguments

    # Use -join to correctly format the command for logging
    Write-Host "[${StepName}] Executing: $executable $($finalArgs -join ' ')"
    
    # Execute the command with its final argument list
    & $executable $finalArgs
    
    # Check the exit code of the last command
    if ($LASTEXITCODE -ne 0) {
        throw "ERROR: Step '${StepName}' failed with exit code ${LASTEXITCODE}. Aborting migration."
    }
    
    Write-Host "Step '${StepName}' completed successfully."
    Write-Host ""
}

# --- Main Script Logic ---
try {
    # Resolve the path to ensure it's absolute and check for existence
    $ResolvedPath = Resolve-Path -Path $TargetDirectory -ErrorAction Stop
    
    Write-Host "`n######################################################" -ForegroundColor Green
    Write-Host "### Starting Data Migration for: '$($ResolvedPath)'" -ForegroundColor Green
    Write-Host "######################################################`n" -ForegroundColor Green

    # --- Step 1: Run patch_old_experiment.py ---
    Invoke-PythonScript -StepName "1/4: Patch Configs" -ScriptName "src/patch_old_experiment.py" -Arguments $ResolvedPath

    # --- Step 2: Run rebuild_reports.py ---
    Invoke-PythonScript -StepName "2/4: Rebuild Reports" -ScriptName "src/rebuild_reports.py" -Arguments $ResolvedPath

    # --- Step 3: Clean out old artifacts ---
    Write-Host "[3/4: Clean Artifacts] Cleaning up old and temporary files..."
    
    # Delete top-level summary files
    $filesToDelete = @("final_summary_results.csv", "batch_run_log.csv")
    foreach ($file in $filesToDelete) {
        $filePath = Join-Path -Path $ResolvedPath -ChildPath $file
        if (Test-Path $filePath) {
            Write-Host " - Deleting old '$file'"
            Remove-Item -Path $filePath -Force
        }
    }
    
    # Delete temporary artifacts from all run_* subdirectories
    Write-Host " - Deleting '*.corrupted' reports and old 'analysis_inputs' directories..."
    Get-ChildItem -Path $ResolvedPath -Filter "run_*" -Directory | ForEach-Object {
        # Delete corrupted report backups
        Get-ChildItem -Path $_.FullName -Filter "*.txt.corrupted" | Remove-Item -Force
        
        # Delete old analysis_inputs directory
        $analysisInputsPath = Join-Path -Path $_.FullName -ChildPath "analysis_inputs"
        if (Test-Path $analysisInputsPath) {
            Remove-Item -Path $analysisInputsPath -Recurse -Force
        }
    }
    Write-Host "Step '3/4: Clean Artifacts' completed successfully."
    Write-Host ""

    # --- Step 4: Run experiment_manager.py --reprocess ---
    Invoke-PythonScript -StepName "4/4: Final Reprocess" -ScriptName "src/experiment_manager.py" -Arguments "--reprocess", $ResolvedPath
    
    Write-Host "######################################################" -ForegroundColor Green
    Write-Host "### Migration Finished Successfully! ###" -ForegroundColor Green
    Write-Host "######################################################`n" -ForegroundColor Green

}
catch {
    Write-Host "`n######################################################" -ForegroundColor Red
    Write-Host "### MIGRATION FAILED ###" -ForegroundColor Red
    Write-Host "######################################################" -ForegroundColor Red
    Write-Error $_.Exception.Message
    # Exit with a non-zero status code to indicate failure to other automation tools
    exit 1
}

# === End of migrate_old_experiment.ps1 ===
