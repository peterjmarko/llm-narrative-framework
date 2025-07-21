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
# Filename: update_experiment.ps1

<#
.SYNOPSIS
    Updates an experiment by regenerating all analysis reports and summary files.

.DESCRIPTION
    This script serves as a user-friendly wrapper for 'src/experiment_manager.py' with the '--reprocess' flag.
    It first runs a preliminary audit. If the audit finds issues that can be fixed by reprocessing,
    it proceeds automatically. If the audit finds the experiment is already complete and valid,
    it will prompt the user for confirmation before forcing a full update.

    This process involves two main steps:
    1. Regenerating the primary report ('replication_report.txt') for each individual run.
    2. Re-running the hierarchical aggregation to update all summary files ('REPLICATION_results.csv', 'EXPERIMENT_results.csv').

    This is the ideal tool for applying analysis updates or bug fixes without repeating expensive LLM API calls,
    as it ensures the entire data hierarchy is consistent.

.PARAMETER TargetDirectory
    (Required) The full path to the experiment directory that you want to update. This is a positional
    parameter, so you can provide the path directly after the script name.

.PARAMETER Notes
    (Optional) A string containing notes to embed in the run logs and reports. This is useful for
    documenting why the reprocessing was performed.

.PARAMETER Verbose
    (Optional) A switch parameter that enables detailed, real-time logging from the underlying Python
    scripts during the reprocessing phase.

.EXAMPLE
    # Reprocess the experiment located in 'output/reports/MyStudy/Experiment_1'
    .\update_experiment.ps1 -TargetDirectory "output/reports/MyStudy/Experiment_1"

.EXAMPLE
    # Reprocess the same experiment with verbose output and notes
    .\update_experiment.ps1 "output/reports/MyStudy/Experiment_1" -Notes "Applied fix to MRR calculation" -Verbose
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the experiment directory to update.")]
    [ValidateScript({
        if (-not (Test-Path $_ -PathType Container)) {
            throw "The specified TargetDirectory does not exist or is not a directory: $_"
        }
        return $true
    })]
    [string]$TargetDirectory,

    [Parameter(Mandatory = $false)]
    [string]$Notes
)

# --- Auto-detect execution environment ---
$executable = "python"
$prefixArgs = @()
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    $executable = "pdm"
    $prefixArgs = "run", "python"
}

try {
    Write-Host "--- Auditing experiment before update... ---" -ForegroundColor Cyan
    # Always force color for consistent output handling from Python script
    $auditArgs = @("src/experiment_manager.py", "--verify-only", $TargetDirectory, "--force-color")

    # Execute and capture the output to display it, but crucially check $LASTEXITCODE
    & $executable $prefixArgs $auditArgs
    $auditExitCode = $LASTEXITCODE

    switch ($auditExitCode) {
        0 { # AUDIT_ALL_VALID
            # If the experiment is already valid, ask the user if they want to force a reprocess.
            $promptMessage = "`nExperiment is already complete and valid. Do you want to force an update anyway? (Y/N)"
            $proceed = $false
            while ($true) {
                $choice = Read-Host -Prompt $promptMessage
                $cleanChoice = $choice.Trim().ToLower()
                if ($cleanChoice -eq 'y') {
                    $proceed = $true
                    break
                }
                if ($cleanChoice -eq 'n') {
                    break
                }
            }

            if (-not $proceed) {
                Write-Host "Update aborted by user." -ForegroundColor Yellow
                return # Exit the script successfully without doing anything.
            }
            # If 'y', proceed to the reprocess step.
            Write-Host "`nProceeding with forced update as requested..." -ForegroundColor Cyan
        }
        1 { # AUDIT_NEEDS_REPROCESS
            # The audit confirmed an update is needed. Let the user know we're proceeding.
            Write-Host "`nAn update is required to fix analysis files. Proceeding..." -ForegroundColor Cyan
        }
        2 { # AUDIT_NEEDS_REPAIR
            # The audit script already printed the reason and recommendation. Exit with a failure code.
            exit 1
        }
        3 { # AUDIT_NEEDS_MIGRATION
            # The audit script already printed the reason and recommendation. Exit with a failure code.
            exit 1
        }
        default {
            throw "Audit script failed unexpectedly with exit code $auditExitCode. Cannot proceed."
        }
    }

    Write-Host "`n--- Starting experiment reprocessing... ---" -ForegroundColor Cyan
    $procArgs = @("src/experiment_manager.py", "--reprocess", $TargetDirectory)
    # The --verbose flag from the wrapper is passed here, not to the audit.
    if ($Verbose.IsPresent) {
        $procArgs += "--verbose"
    }
    if ($Notes) { $procArgs += "--notes", $Notes }

    # Add --force-color for the reprocessing step as well
    $procArgs += "--force-color"

    & $executable $prefixArgs $procArgs
    if ($LASTEXITCODE -ne 0) { throw "Re-processing failed with exit code $LASTEXITCODE" }

    Write-Host "`n--- Running post-update audit to verify changes... ---" -ForegroundColor Cyan
    & $executable $prefixArgs $auditArgs
    if ($LASTEXITCODE -ne 0) {
        # The update should result in a valid state (exit code 0). If not, something is wrong.
        Write-Warning "Post-update audit failed. The experiment may still have unresolved issues."
    }

    Write-Host "`nExperiment update completed successfully for:" -ForegroundColor Green
    Write-Host $TargetDirectory -ForegroundColor Green
} catch {
    # The 'throw' statements in the switch block will be caught here.
    Write-Error "An error occurred during the update process: $($_.Exception.Message)"
    exit 1
}

# === End of update_experiment.ps1 ===
