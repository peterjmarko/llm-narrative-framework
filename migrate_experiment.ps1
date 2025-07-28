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
# Filename: migrate_experiment.ps1

<#
.SYNOPSIS
    Copies a legacy experiment to a new, timestamped directory and upgrades it.

.DESCRIPTION
    This script performs a safe, non-destructive migration. It takes a target
    legacy experiment directory, copies it to a new timestamped folder within
    'output/migrated_experiments/', and then runs the migration process on the
    new copy. The original data is left untouched.

.PARAMETER TargetDirectory
    The path to the root of the old experiment directory that needs to be migrated.

.EXAMPLE
    # Copy and migrate "Legacy_Experiment_1"
    # This creates a folder like "output/migrated_experiments/Legacy_Experiment_1_migrated_20250712_103000"
    .\migrate_experiment.ps1 -TargetDirectory "output/legacy/Legacy_Experiment_1"
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the source legacy experiment directory to migrate.")]
    [string]$TargetDirectory
)

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
        # Check if the line is too long to be padded.
        if ($line.Length -gt ($Width - 8)) { # Use 8 to give a little buffer
            # If too long, print it plainly without attempting to center.
            Write-Host "### $($line) " -ForegroundColor $Color
        } else {
            # Otherwise, use the original centering logic.
            $paddingLength = $Width - $line.Length - 6 # 3 for '###', 3 for '###'
            $leftPad = [math]::Floor($paddingLength / 2)
            $rightPad = [math]::Ceiling($paddingLength / 2)
            $formattedLine = "###" + (" " * $leftPad) + $line + (" " * $rightPad) + "###"
            Write-Host $formattedLine -ForegroundColor $Color
        }
    }
    Write-Host $separator -ForegroundColor $Color
    Write-Host "" # Add a blank line after the header
}

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
    # Clean and validate the input path to prevent errors from hidden characters or typos.
    $TargetDirectory = $TargetDirectory.Trim()
    if (-not (Test-Path $TargetDirectory -PathType Container)) {
        throw "The specified TargetDirectory '$TargetDirectory' does not exist as a directory relative to the current location: '$(Get-Location)'"
    }
    
    # 0. Audit Target Experiment

    $TargetPath = Resolve-Path -Path $TargetDirectory -ErrorAction Stop
    $scriptName = "src/experiment_manager.py"
    # Corrected argument order: path must come before the flag for the parser.
    $pythonScriptArgs = $TargetPath, "--verify-only"

    # Execute by passing executable, prefix args, script name, and script args separately.
    # This robustly handles argument splatting in PowerShell.
    Write-Host "Auditing..." -ForegroundColor DarkGray
    & $executable $prefixArgs $scriptName $pythonScriptArgs

    $pythonExitCode = $LASTEXITCODE # Capture exit code from the audit command

    # This helper function standardizes the Y/N prompt.
    function Confirm-Proceed {
        param([string]$Prompt)
        while ($true) {
            $choice = Read-Host -Prompt $Prompt
            if ($choice.Trim().ToLower() -eq 'y') { return $true }
            if ($choice.Trim().ToLower() -eq 'n') { return $false }
        }
    }

    # Handle user interaction based on the audit result.
    switch ($pythonExitCode) {
        $AUDIT_ALL_VALID {
            # The audit report itself is the message. Give user option to force migration.
            $prompt = "`nExperiment is already complete and valid. Do you still want to force a migration? (Y/N): "
            if (-not (Confirm-Proceed -Prompt $prompt)) {
                Write-Host "`nNo action taken." -ForegroundColor Yellow
                exit 0
            }
        }
        $AUDIT_NEEDS_REPROCESS {
            Write-Host "`nReprocessing Recommended. This script will copy the data then perform a migration." -ForegroundColor Yellow
            Write-Host "For analysis updates *without* migration, use 'repair_experiment.ps1' instead." -ForegroundColor Yellow
            if (-not (Confirm-Proceed -Prompt "`nDo you wish to proceed? (Y/N): ")) {
                Write-Host "`nMigration aborted by user." -ForegroundColor Red; exit 1
            }
        }
        $AUDIT_NEEDS_REPAIR {
            Write-Host "`nCritical Repair Recommended. This script will copy the data then perform a migration." -ForegroundColor Red
            Write-Host "For automatic repair *without* migration, use 'repair_experiment.ps1' instead." -ForegroundColor Red
            if (-not (Confirm-Proceed -Prompt "`nDo you wish to proceed? (Y/N): ")) {
                Write-Host "`nMigration aborted by user." -ForegroundColor Red; exit 1
            }
        }
        $AUDIT_NEEDS_MIGRATION {
            Write-Host "`nMigration Required. This script will copy the data then perform a migration." -ForegroundColor Yellow
            if (-not (Confirm-Proceed -Prompt "`nDo you wish to proceed? (Y/N): ")) {
                Write-Host "`nMigration aborted by user." -ForegroundColor Red; exit 1
            }
        }
        default {
            Write-Header -Lines "Audit FAILED: Unknown or unexpected exit code: ${pythonExitCode}." -Color Red
            Write-Error "Halting migration due to unexpected audit result."
            exit 1
        }
    }
    # If script execution reaches this point, the user has confirmed they want to proceed.

    # 1. Resolve source and automatically determine destination
    $TargetBaseName = (Get-Item -Path $TargetPath).Name
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $NewFolderName = "${TargetBaseName}_migrated_${Timestamp}"
    $DestinationParent = "output/migrated_experiments"
    $DestinationPath = Join-Path -Path $DestinationParent -ChildPath $NewFolderName

    # Create the parent directory if it doesn't exist
    if (-not (Test-Path -Path $DestinationParent)) {
        New-Item -ItemType Directory -Path $DestinationParent -Force | Out-Null
    }

    # 2. Copy the experiment to the new location
    Write-Header -Lines "Step 1/2: Copying Experiment Data" -Color Cyan
    $relativeSource = (Resolve-Path $TargetPath -Relative).TrimStart(".\")
    # The destination path is already a relative string; display it before creation.
    Write-Host "Source:      $relativeSource"
    Write-Host "Destination: $DestinationPath"
    Copy-Item -Path $TargetPath -Destination $DestinationPath -Recurse -Force
    Write-Host "`nCopy complete."

    # 3. Run the migration process on the new copy
    Write-Header -Lines "Step 2/2: Transforming New Experiment Copy" -Color Cyan
    
    $scriptName = "src/experiment_manager.py"
    $pythonScriptArgs = $DestinationPath, "--migrate", "--quiet"

    & $executable $prefixArgs $scriptName $pythonScriptArgs

    # Check if the experiment_manager.py exited with a user-abort code.
    if ($LASTEXITCODE -eq $AUDIT_ABORTED_BY_USER) {
        Write-Header -Lines "Migration Process Aborted by User!" -Color Yellow
        exit 0 # Exit successfully, as it was a user-initiated graceful abort
    } elseif ($LASTEXITCODE -ne 0) {
        # Any other non-zero exit code is a true error
        throw "ERROR: Migration process failed with exit code ${LASTEXITCODE}."
    }

    # Run a final, conclusive audit on the newly migrated directory to verify success.
    $finalAuditArgs = $DestinationPath, "--verify-only", "--force-color"
    & $executable $prefixArgs $scriptName $finalAuditArgs

    if ($LASTEXITCODE -ne 0) {
        # This should not happen if the manager succeeded, but it's a critical safety check.
        Write-Header -Lines @("VALIDATION FAILED!", "Migration completed, but the final result is not valid.", "Please check the audit report above for details.") -Color Red
        exit 1
    }

    # The final audit report serves as the success message.
    $relativeDest = (Resolve-Path $DestinationPath -Relative).TrimStart(".\")
    Write-Host "`nMigration process complete. Migrated data is in: '$relativeDest'`n" -ForegroundColor Green

}
catch {
    Write-Header -Lines "MIGRATION FAILED" -Color Red
    # Handle both string errors from 'throw' and full exception objects.
    $errorMessage = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { $_ }
    Write-Host $errorMessage -ForegroundColor Red
    exit 1
}

# === End of migrate_experiment.ps1 ===
