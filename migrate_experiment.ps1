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
    Upgrades a legacy or severely corrupted experiment via a safe, non-destructive copy.

.DESCRIPTION
    This is a powerful safety utility for handling legacy data or any experiment
    diagnosed with multiple, complex errors. It performs a non-destructive
    migration by first creating a clean, timestamped copy of the target experiment,
    then running the full upgrade and validation process on that copy.

    The original data is always left untouched.

.PARAMETER TargetDirectory
    The path to the experiment directory that will be targeted for migration.
    This original directory will be copied, not modified.

.EXAMPLE
    # Copy and migrate "Legacy_Experiment_1"
    # This creates a folder like "output/migrated_experiments/Legacy_Experiment_1_migrated_20250712_103000"
    .\migrate_experiment.ps1 -TargetDirectory "output/legacy/Legacy_Experiment_1"
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the experiment directory to migrate.")]
    [string]$TargetDirectory,

    [Parameter(Mandatory = $false, HelpMessage = "Specifies a custom parent directory for the migrated experiment.")]
    [string]$DestinationParent,

    [Parameter(Mandatory = $false, HelpMessage = "Run in non-interactive mode, suppressing user prompts for confirmation.")]
    [switch]$NonInteractive
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
$AUDIT_NEEDS_AGGREGATION = 4 # Replications valid, but experiment-level summary is missing.
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

    # In non-interactive mode, we skip all user prompts and proceed directly.
    if (-not $NonInteractive.IsPresent) {
        $pythonExitCode = $LASTEXITCODE # Capture exit code from the audit command

        # This helper function standardizes the Y/N prompt.
        function Confirm-Proceed {
            param([string]$Message)
            # The prompt format is now defined in one place. Read-Host adds the final ':'.
            $promptText = "$Message (Y/N)"
            while ($true) {
                $choice = Read-Host -Prompt $promptText
                if ($choice.Trim().ToLower() -eq 'y') { return $true }
                if ($choice.Trim().ToLower() -eq 'n') { return $false }
            }
        }

        # Handle user interaction based on the audit result.
        switch ($pythonExitCode) {
            $AUDIT_ALL_VALID {
                # The audit report itself is the message. Give user option to force migration.
                Write-Host "`nExperiment is already complete and valid." -ForegroundColor Yellow
                Write-Host "" # Add a blank line for spacing
                $message = "Do you still want to proceed with migration?"
                if (-not (Confirm-Proceed -Message $message)) {
                    Write-Host "`nNo action taken.`n" -ForegroundColor Yellow
                    return
                }
            }
            $AUDIT_NEEDS_REPROCESS {
                Write-Host "`nExperiment needs updating. We recommend that you exit at the next prompt ('N') and run 'repair_experiment.ps1' instead to update the original data.`nMigration will first copy the experiment then upgrade this copy."
                if (-not (Confirm-Proceed -Message "`nDo you still want to proceed with migration?")) {
                    Write-Host "`nMigration aborted by user.`n" -ForegroundColor Yellow; return
                }
            }
            $AUDIT_NEEDS_REPAIR {
                Write-Host "`nExperiment needs repair. We recommend that you exit at the next prompt ('N') and run 'repair_experiment.ps1' instead to repair your original data.`nMigration will first copy the experiment then upgrade this copy."
                if (-not (Confirm-Proceed -Message "`nDo you still want to proceed with migration?")) {
                    Write-Host "`nMigration aborted by user.`n" -ForegroundColor Yellow; return
                }
            }
            $AUDIT_NEEDS_AGGREGATION {
                Write-Host "`nExperiment only needs finalization. We recommend that you exit at the next prompt ('N') and run 'repair_experiment.ps1' instead to finalize the original data.`nMigration will first copy the experiment then upgrade this copy."
                if (-not (Confirm-Proceed -Message "`nDo you still want to proceed with migration?")) {
                    Write-Host "`nMigration aborted by user.`n" -ForegroundColor Yellow; return
                }
            }
            $AUDIT_NEEDS_MIGRATION {
                Write-Host "`nMigration Required. This script will copy your original data then perform a full upgrade to complete the migration." -ForegroundColor Yellow
                if (-not (Confirm-Proceed -Message "`nDo you wish to proceed?")) {
                    Write-Host "`nMigration aborted by user.`n" -ForegroundColor Yellow; return
                }
            }
            default {
                Write-Header -Lines "Audit FAILED: Unknown or unexpected exit code: ${pythonExitCode}." -Color Red
                Write-Error "Halting migration due to unexpected audit result."
                return
            }
        }
    }
    # If script execution reaches this point, the user has confirmed they want to proceed.

    # 1. Resolve source and automatically determine destination
    $TargetBaseName = (Get-Item -Path $TargetPath).Name
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $NewFolderName = "${TargetBaseName}_migrated_${Timestamp}"
    
    # Use the provided destination parent if available, otherwise default to the standard one.
    if (-not $PSBoundParameters.ContainsKey('DestinationParent')) {
        $DestinationParent = "output/migrated_experiments"
    }
    
    $DestinationPath = Join-Path -Path $DestinationParent -ChildPath $NewFolderName

    # Create the parent directory if it doesn't exist
    if (-not (Test-Path -Path $DestinationParent)) {
        New-Item -ItemType Directory -Path $DestinationParent -Force | Out-Null
    }

    # --- Logging Setup ---
    # The migration log is created in the NEW destination directory.
    $logFileName = "experiment_migration_log.txt"
    $logFilePath = Join-Path $DestinationPath $logFileName
    Start-Transcript -Path $logFilePath -Force | Out-Null
    
    Write-Host "" # Blank line before message
    Write-Host "The migration log will be saved at:" -ForegroundColor Gray
    # Since the destination path doesn't exist yet, we construct the relative path manually.
    $relativeLogPath = (Join-Path $DestinationParent $NewFolderName $logFileName).Replace("\", "/")
    Write-Host $relativeLogPath -ForegroundColor Gray

    # 2. Copy the experiment to the new location
    Write-Header -Lines "Step 1/2: Copying Experiment Data" -Color Cyan
    $relativeSource = (Resolve-Path $TargetPath -Relative).TrimStart(".\")
    # The destination path is already a relative string; display it before creation.
    Write-Host "Source:      $relativeSource"
    Write-Host "Destination: $DestinationPath"
    # Ensure the destination directory exists before copying contents into it.
    New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null
    # Append '\*' to the source path to copy its contents, not the folder itself.
    Copy-Item -Path (Join-Path $TargetPath "*") -Destination $DestinationPath -Recurse -Force
    Write-Host "`nCopy complete."

    # 3. Run the migration process on the new copy
    Write-Header -Lines "Step 2/2: Upgrading New Experiment Copy" -Color Cyan
    
    $scriptName = "src/experiment_manager.py"
    $pythonScriptArgs = $DestinationPath, "--migrate", "--quiet"

    & $executable $prefixArgs $scriptName $pythonScriptArgs

    # Check if the experiment_manager.py exited with a user-abort code.
    if ($LASTEXITCODE -eq $AUDIT_ABORTED_BY_USER) {
        Write-Header -Lines "Migration Process Aborted by User!" -Color Yellow
        return # Exit successfully, allowing the 'finally' block to run.
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
        return
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
finally {
    # Only try to stop the transcript and print the message if a migration log
    # was actually created, which implies a transcript was started.
    if ($logFilePath -and (Test-Path -LiteralPath $logFilePath)) {
        Stop-Transcript | Out-Null
        
        Write-Host "`nThe migration log has been saved at:" -ForegroundColor Gray
        $relativePath = Resolve-Path -Path $logFilePath -Relative
        Write-Host $relativePath -ForegroundColor Gray
        Write-Host "" # Add a blank line for spacing
    }
}


# === End of migrate_experiment.ps1 ===
