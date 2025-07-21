#!/usr/bin/env powershell
# -*-- coding: utf-8 -*-
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
# Filename: update_study.ps1

<#
.SYNOPSIS
    Updates all out-of-date experiments within a study directory in a single batch operation.

.DESCRIPTION
    This script provides a high-level workflow for bringing an entire study up to date with the latest
    analysis logic. It first performs a comprehensive, read-only audit of every experiment within the
    specified study directory.

    Based on the audit, it identifies which experiments require an update. If any experiments have
    critical issues (e.g., needing repair or migration), the script will halt with an error, ensuring
    that updates are only performed on structurally sound data.

    If updates are needed, it will list the affected experiments, ask for a single user confirmation,
    and then sequentially call 'update_experiment.ps1' on each one.

.PARAMETER StudyDirectory
    The path to the study directory containing multiple experiment folders.

.PARAMETER Verbose
    If specified, displays the full, detailed output from each individual 'update_experiment.ps1' call.

.EXAMPLE
    # Run an update on a study, which will first audit and then prompt for confirmation.
    .\update_study.ps1 -StudyDirectory "output/studies/My_First_Study"
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the study directory to update.")]
    [string]$StudyDirectory
)

# --- Auto-detect execution environment ---
$executable = "python"
$prefixArgs = @()
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    $executable = "pdm"
    $prefixArgs = "run", "python"
}

$ScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition

try {
    Write-Host "--- Performing pre-update audit of the entire study... ---" -ForegroundColor Cyan
    $auditScriptPath = Join-Path $ScriptRoot "audit_study.ps1"
    
    # Run the audit script and capture its output
    $auditOutput = & $auditScriptPath -StudyDirectory $StudyDirectory -ErrorAction Stop

    # Explicitly write the captured output to the console so the user can see the summary
    $auditOutput | Write-Host

    $experimentsToUpdate = @()
    $needsManualFix = $false

    # Parse the summary table from the audit output
    $auditLines = $auditOutput | Out-String
    # Filter for lines that are part of the summary table and indicate an issue
    $summaryLines = $auditLines -split [System.Environment]::NewLine | Where-Object { $_ -match 'NEEDS UPDATE|NEEDS REPAIR|NEEDS MIGRATION' -and $_ -notmatch '^\s*Experiment' -and $_ -notmatch '^\s*-' }

    $nameColumnWidth = 45
    foreach ($line in $summaryLines) {
        if ($line.Length -ge $nameColumnWidth -and $line.Trim().Length -gt 0) {
            $experimentName = $line.Substring(0, $nameColumnWidth).Trim()
            if (-not [string]::IsNullOrWhiteSpace($experimentName)) {
                 if ($line -match "NEEDS UPDATE") {
                    $experimentsToUpdate += $experimentName
                } else {
                    $needsManualFix = $true
                }
            }
        }
    }

    if ($needsManualFix) {
        throw "Audit found experiments that need repair or migration. Please fix these critical issues before running a study-wide update."
    }

    if ($experimentsToUpdate.Count -eq 0) {
        Write-Host "`nAll experiments are already up to date. No action needed." -ForegroundColor Green
        exit 0
    }

    Write-Host "`nThe following $($experimentsToUpdate.Count) experiment(s) will be updated:" -ForegroundColor Yellow
    $experimentsToUpdate | ForEach-Object { Write-Host " - $_" }

    $choice = Read-Host "`nDo you wish to proceed with the update? (Y/N)"
    if ($choice.Trim().ToLower() -ne 'y') {
        Write-Host "Update aborted by user." -ForegroundColor Yellow
        exit 0
    }

    $updateScriptPath = Join-Path $ScriptRoot "update_experiment.ps1"
    $i = 0
    foreach ($experimentName in $experimentsToUpdate) {
        $i++
        $experimentPath = Join-Path $StudyDirectory $experimentName
        Write-Host "`n--- Updating experiment $i of $($experimentsToUpdate.Count): $experimentName ---" -ForegroundColor Cyan
        
        # --- CORRECTED SCRIPT CALL ---
        # Call the script directly with named parameters for maximum clarity and robustness.
        # This avoids splatting issues.
        if ($PSBoundParameters['Verbose']) {
            & $updateScriptPath -TargetDirectory $experimentPath -Verbose
        }
        else {
            & $updateScriptPath -TargetDirectory $experimentPath
        }
        
        if ($LASTEXITCODE -ne 0) {
            throw "Update failed for experiment: $experimentName. Halting study update."
        }
    }

    Write-Host "`n--- Running post-update audit to verify all changes... ---" -ForegroundColor Cyan
    & $auditScriptPath -StudyDirectory $StudyDirectory
    
    Write-Host "`nStudy update completed successfully." -ForegroundColor Green

} catch {
    Write-Error "An error occurred during the study update process: $($_.Exception.Message)"
    exit 1
}