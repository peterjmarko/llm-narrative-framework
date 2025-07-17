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

# --- Define Audit Exit Codes from experiment_manager.py ---
# These are mapped from the Python script for clarity and robustness.
$AUDIT_ALL_VALID       = 0 # Experiment is complete and valid.
$AUDIT_NEEDS_REPROCESS = 1 # Experiment needs reprocessing (e.g., analysis issues).
$AUDIT_NEEDS_REPAIR    = 2 # Experiment needs repair (e.g., missing responses, critical files).
$AUDIT_NEEDS_MIGRATION = 3 # Experiment is legacy or malformed, requires full migration.
$AUDIT_ABORTED_BY_USER = 99 # Specific exit code when user aborts via prompt in experiment_manager.py

# --- Main Script Logic ---
try {
    # 0. Audit Source Experiment
    Write-Host "`n======================================================" -ForegroundColor Cyan
    Write-Host "### Auditing Source Experiment                   ###" -ForegroundColor Cyan
    Write-Host "======================================================`n" -ForegroundColor Cyan

    $SourcePath = Resolve-Path -Path $SourceDirectory -ErrorAction Stop
    $scriptName = "src/experiment_manager.py"
    $auditArgs = "--verify-only", $SourcePath
    $finalAuditArgs = $prefixArgs + $scriptName + $auditArgs

    Write-Host "Auditing: $executable $($finalAuditArgs -join ' ')"
    & $executable $finalAuditArgs

    $pythonExitCode = $LASTEXITCODE # Capture exit code from the audit command

    # Determine message and color based on audit result
    $summaryMessage = ""
    $summaryColor = "Green"
    $shouldExitImmediately = $false

    switch ($pythonExitCode) {
        $AUDIT_ALL_VALID {
            $summaryMessage = "Experiment is in mint condition. No action is required by this script."
            $summaryColor = "Green"
            $shouldExitImmediately = $true
        }
        $AUDIT_NEEDS_REPROCESS {
            $summaryMessage = "Reprocessing Recommended. This script will perform a full migration, which involves first copying the data and then transforming the new copy."
            $summaryDetails = "For analysis updates *without* migration, use 'update_experiment.ps1' instead."
            $summaryColor = "Yellow"
        }
        $AUDIT_NEEDS_REPAIR {
            $summaryMessage = "Critical Repair Recommended. This script will attempt to fix issues via a full migration, which involves first copying the data and then transforming the new copy."
            $summaryDetails = "For automatic repair *without* migration, use 'run_experiment.ps1' instead."
            $summaryColor = "Red"
        }
        $AUDIT_NEEDS_MIGRATION {
            $summaryMessage = "Migration Required. This script will proceed with a full migration, which involves first copying the data and then transforming the new copy."
            $summaryColor = "Yellow"
        }
        default {
            Write-Host "`n######################################################" -ForegroundColor Red
            Write-Host "### Audit FAILED: Unknown or unexpected exit code: ${pythonExitCode}. ###" -ForegroundColor Red
            Write-Host "######################################################`n" -ForegroundColor Red
            Write-Error "Halting migration due to unexpected audit result."
            exit 1
        }
    }

    # Print the audit summary banner
    Write-Host "`n######################################################" -ForegroundColor $summaryColor
    Write-Host "### Audit Summary:                                 ###" -ForegroundColor $summaryColor
    Write-Host "### (See detailed report above)                    ###" -ForegroundColor $summaryColor
    Write-Host "######################################################`n" -ForegroundColor $summaryColor
    
    # Print the action message below the banner for better flow
    Write-Host "$summaryMessage" -ForegroundColor $summaryColor
    if ($summaryDetails) {
        Write-Host "$summaryDetails" -ForegroundColor $summaryColor
    }

    # Prompt for user review and then confirmation if needed
    if ($shouldExitImmediately) {
        Write-Host "`n$(Read-Host "Press Enter to review the audit report, then continue to exit...")`n"
        exit 0
    } else {
        $confirm = Read-Host "`nDo you wish to proceed with the full migration? (Y/N)"
        if ($confirm -ne 'Y' -and $confirm -ne 'y') {
            Write-Host "`nMigration aborted by user." -ForegroundColor Red
            exit 1
        }
    }

    # 1. Resolve source and automatically determine destination
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
    Write-Host "`n======================================================" -ForegroundColor Cyan
    Write-Host "### Step 1/2: Copying Experiment Data ###" -ForegroundColor Cyan
    Write-Host "======================================================`n" -ForegroundColor Cyan
    Write-Host "Source:      $SourcePath"
    Write-Host "Destination: $DestinationPath"
    Copy-Item -Path $SourcePath -Destination $DestinationPath -Recurse -Force
    Write-Host "`nCopy complete."

    # 3. Run the migration process on the new copy
    Write-Host "`n======================================================" -ForegroundColor Cyan
    Write-Host "### Step 2/2: Transforming New Experiment Copy ###" -ForegroundColor Cyan
    Write-Host "======================================================`n" -ForegroundColor Cyan
    
    $scriptName = "src/experiment_manager.py"
    $arguments = "--migrate", $DestinationPath
    $finalArgs = $prefixArgs + $scriptName + $arguments

    Write-Host "Executing: $executable $($finalArgs -join ' ')"
    & $executable $finalArgs

    # Check if the experiment_manager.py exited with a user-abort code.
    if ($LASTEXITCODE -eq $AUDIT_ABORTED_BY_USER) {
        Write-Host "`n######################################################" -ForegroundColor Yellow
        Write-Host "### Migration Process Aborted by User! ###" -ForegroundColor Yellow
        Write-Host "######################################################`n" -ForegroundColor Yellow
        exit 0 # Exit successfully, as it was a user-initiated graceful abort
    } elseif ($LASTEXITCODE -ne 0) {
        # Any other non-zero exit code is a true error
        throw "ERROR: Migration process failed with exit code ${LASTEXITCODE}."
    }

    # --- Final Validation Audit ---
    Write-Host "`n--- Running Post-Migration Audit to Verify Changes... ---" -ForegroundColor Cyan
    $postAuditArgs = "--verify-only", $DestinationPath, "--force-color"
    $finalPostAuditArgs = $prefixArgs + $scriptName + $postAuditArgs
    & $executable $finalPostAuditArgs

    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Post-migration audit failed. The experiment may still have unresolved issues."
    }

    Write-Host "`n######################################################" -ForegroundColor Green
    Write-Host "### Migration Finished Successfully!             ###" -ForegroundColor Green
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