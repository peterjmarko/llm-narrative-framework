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
<#
.SYNOPSIS
    Repairs, updates, or resumes all incomplete or outdated experiments within a study directory.

.DESCRIPTION
    This script provides a high-level workflow for bringing an entire study into a valid and
    up-to-date state. It first performs a comprehensive, read-only audit of every experiment
    within the specified study directory.

    Based on the audit, it identifies which experiments require any kind of fix (e.g., repair,
    update, resume). If any experiments are found to need migration, the script will halt with
    an error, recommending that 'migrate_study.ps1' be run first.

    If fixable issues are found, it will list the affected experiments, ask for a single user
    confirmation, and then sequentially call 'repair_experiment.ps1' non-interactively on each one.

.PARAMETER StudyDirectory
    The path to the study directory containing multiple experiment folders.

.PARAMETER Verbose
    If specified, displays the full, detailed output from each individual 'repair_experiment.ps1' call.

.EXAMPLE
    # Run a repair on a study, which will first audit and then prompt for confirmation.
    .\repair_study.ps1 -StudyDirectory "output/studies/My_First_Study"
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the target study directory to repair.")]
    [string]$StudyDirectory
)

function Format-Banner {
    param(
        [string]$Message,
        [int]$TotalWidth = 80
    )
    $prefix = "###"
    $suffix = "###"
    $contentWidth = $TotalWidth - $prefix.Length - $suffix.Length
    $paddedMessage = " $Message "
    
    # Simple centering logic
    $paddingTotal = $contentWidth - $paddedMessage.Length
    if ($paddingTotal -lt 0) { $paddingTotal = 0 }
    $paddingLeft = [Math]::Floor($paddingTotal / 2)
    $paddingRight = $contentWidth - $paddedMessage.Length - $paddingLeft
    
    $content = (" " * $paddingLeft) + $paddedMessage + (" " * $paddingRight)
    
    return "$prefix$content$suffix"
}

# --- Auto-detect execution environment ---
$executable = "python"
$prefixArgs = @()
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    $executable = "pdm"
    $prefixArgs = "run", "python"
}

$ScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition

try {
    Write-Host "--- Performing pre-repair audit of the entire study... ---" -ForegroundColor Cyan
    $auditScriptPath = Join-Path $ScriptRoot "audit_study.ps1"
    
    # Run the audit script and capture its output
    $auditOutput = & $auditScriptPath -StudyDirectory $StudyDirectory -ErrorAction Stop

    # Explicitly write the captured output to the console so the user can see the summary
    $auditOutput | Write-Host

    $experimentsToFix = [System.Collections.Generic.List[string]]::new()
    $experimentsToMigrate = [System.Collections.Generic.List[string]]::new()

    # Parse the summary table from the audit output
    $auditLines = $auditOutput | Out-String
    
    # Find all lines that indicate a non-validated state
    $problemLines = $auditLines -split [System.Environment]::NewLine | Where-Object { $_ -match 'NEEDS' }

    # Robustly find the start of the "Status" column from the header line
    $headerLine = $auditLines -split [System.Environment]::NewLine | Where-Object { $_ -match "Experiment\s+Status" } | Select-Object -First 1
    $statusColumnIndex = if ($headerLine) { $headerLine.IndexOf("Status") } else { -1 }

    if ($statusColumnIndex -lt 0) {
        throw "Could not parse the header of the audit report. Cannot determine experiments to fix."
    }

    foreach ($line in $problemLines) {
        # The experiment name is the substring from the start of the line up to the status column.
        $experimentName = $line.Substring(0, $statusColumnIndex).Trim()

        if (-not [string]::IsNullOrWhiteSpace($experimentName)) {
             if ($line -match "NEEDS MIGRATION") {
                $experimentsToMigrate.Add($experimentName)
            } else { # Catches NEEDS REPAIR, NEEDS UPDATE, NEEDS FINALIZATION
                $experimentsToFix.Add($experimentName)
            }
        }
    }

    if ($experimentsToMigrate.Count -gt 0) {
        throw "Audit found experiments that require migration. Please run 'migrate_study.ps1' to handle these experiments before proceeding with a repair."
    }

    if ($experimentsToFix.Count -eq 0) {
        Write-Host "`nAll experiments are already valid and up to date. No action needed." -ForegroundColor Green
        exit 0
    }

    Write-Host "`nThe following $($experimentsToFix.Count) experiment(s) will be repaired/updated:" -ForegroundColor Yellow
    $experimentsToFix | ForEach-Object { Write-Host " - $_" }

    $choice = Read-Host "`nDo you wish to proceed with the repair process? (Y/N)"
    if ($choice.Trim().ToLower() -ne 'y') {
        Write-Host "Repair aborted by user." -ForegroundColor Yellow
        exit 0
    }

    $repairScriptPath = Join-Path $ScriptRoot "repair_experiment.ps1"
    $i = 0
    foreach ($experimentName in $experimentsToFix) {
        $i++
        $experimentPath = Join-Path $StudyDirectory $experimentName
        Write-Host "`n--- Repairing experiment $i of $($experimentsToFix.Count): $experimentName ---" -ForegroundColor Cyan
        
        # Call the repair script non-interactively. It will automatically perform the correct action.
        if ($PSBoundParameters['Verbose']) {
            & $repairScriptPath -TargetDirectory $experimentPath -NonInteractive -Verbose
        }
        else {
            & $repairScriptPath -TargetDirectory $experimentPath -NonInteractive
        }
        
        if ($LASTEXITCODE -ne 0) {
            throw "Repair failed for experiment: $experimentName. Halting study repair."
        }
    }

    Write-Host "`n--- Running post-repair audit to verify all changes... ---" -ForegroundColor Cyan
    & $auditScriptPath -StudyDirectory $StudyDirectory
    
    $headerLine = "#" * 80
    Write-Host "`n$headerLine" -ForegroundColor Green
    Write-Host (Format-Banner "Study Repair Completed Successfully") -ForegroundColor Green
    Write-Host "$headerLine" -ForegroundColor Green

} catch {
    $headerLine = "#" * 80
    Write-Host "`n$headerLine" -ForegroundColor Red
    Write-Host (Format-Banner "STUDY REPAIR FAILED") -ForegroundColor Red
    Write-Host "$headerLine" -ForegroundColor Red
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# === End of repair_study.ps1 ===