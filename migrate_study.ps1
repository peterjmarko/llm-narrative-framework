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
    Migrates all legacy or corrupted experiments within a study directory in a single batch.

.DESCRIPTION
    This script provides a safe, high-level workflow for upgrading legacy or corrupted
    experiments within a study. It first performs a comprehensive, read-only audit of every
    experiment in the specified study directory.

    Based on the audit, it identifies which experiments require migration. If any experiments
    have other issues (e.g., needing repair or update), the script will halt with an error,
    recommending that 'repair_study.ps1' be run first to ensure the study is in a stable
    state before performing migrations.

    If migrations are needed, it will list the affected experiments, ask for a single user
    confirmation, and then sequentially call 'migrate_experiment.ps1' non-interactively on
    each one. Each migration creates a safe, upgraded copy, leaving the original data untouched.

.PARAMETER StudyDirectory
    The path to the study directory containing multiple experiment folders.

.PARAMETER Verbose
    If specified, displays the full, detailed output from each individual 'migrate_experiment.ps1' call.

.EXAMPLE
    # Run a migration on a study, which will first audit and then prompt for confirmation.
    .\migrate_study.ps1 -StudyDirectory "output/studies/My_Legacy_Study"
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the target study directory to migrate.")]
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
    
    $paddingTotal = $contentWidth - $paddedMessage.Length
    if ($paddingTotal -lt 0) { $paddingTotal = 0 }
    $paddingLeft = [Math]::Floor($paddingTotal / 2)
    $paddingRight = $contentWidth - $paddedMessage.Length - $paddingLeft
    
    $content = (" " * $paddingLeft) + $paddedMessage + (" " * $paddingRight)
    
    return "$prefix$content$suffix"
}

$ScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition

try {
    Write-Host "--- Performing pre-migration audit of the entire study... ---" -ForegroundColor Cyan
    $auditScriptPath = Join-Path $ScriptRoot "audit_study.ps1"
    
    # Run the audit script and capture its output
    $auditOutput = & $auditScriptPath -StudyDirectory $StudyDirectory -ErrorAction Stop

    # Explicitly write the captured output to the console so the user can see the summary
    $auditOutput | Write-Host

    $experimentsToMigrate = [System.Collections.Generic.List[string]]::new()
    $needsRepair = $false

    # Parse the summary table from the audit output
    $auditLines = $auditOutput | Out-String
    
    # Find all lines that indicate a non-validated state
    $problemLines = $auditLines -split [System.Environment]::NewLine | Where-Object { $_ -match 'NEEDS' }

    # Robustly find the start of the "Status" column from the header line
    $headerLine = $auditLines -split [System.Environment]::NewLine | Where-Object { $_ -match "Experiment\s+Status" } | Select-Object -First 1
    $statusColumnIndex = if ($headerLine) { $headerLine.IndexOf("Status") } else { -1 }

    if ($statusColumnIndex -lt 0) {
        throw "Could not parse the header of the audit report. Cannot determine experiments to migrate."
    }

    foreach ($line in $problemLines) {
        # The experiment name is the substring from the start of the line up to the status column.
        $experimentName = $line.Substring(0, $statusColumnIndex).Trim()

        if (-not [string]::IsNullOrWhiteSpace($experimentName)) {
             if ($line -match "NEEDS MIGRATION") {
                $experimentsToMigrate.Add($experimentName)
            } else { # Catches NEEDS REPAIR, NEEDS UPDATE, NEEDS FINALIZATION
                $needsRepair = $true
            }
        }
    }

    if ($needsRepair) {
        throw "Audit found experiments that require repair or update. Please run 'repair_study.ps1' first to ensure the study is in a stable state before migrating."
    }

    if ($experimentsToMigrate.Count -eq 0) {
        Write-Host "`nNo experiments require migration. No action needed." -ForegroundColor Green
        exit 0
    }

    Write-Host "`nThe following $($experimentsToMigrate.Count) experiment(s) will be migrated:" -ForegroundColor Yellow
    $experimentsToMigrate | ForEach-Object { Write-Host " - $_" }

    $choice = Read-Host "`nDo you wish to proceed with the migration process? (Y/N)"
    if ($choice.Trim().ToLower() -ne 'y') {
        Write-Host "Migration aborted by user." -ForegroundColor Yellow
        exit 0
    }

    $migrateScriptPath = Join-Path $ScriptRoot "migrate_experiment.ps1"
    $i = 0
    foreach ($experimentName in $experimentsToMigrate) {
        $i++
        $experimentPath = Join-Path $StudyDirectory $experimentName
        Write-Host "`n--- Migrating experiment $i of $($experimentsToMigrate.Count): $experimentName ---" -ForegroundColor Cyan
        
        # Call the migration script non-interactively.
        if ($PSBoundParameters['Verbose']) {
            & $migrateScriptPath -TargetDirectory $experimentPath -NonInteractive -Verbose
        }
        else {
            & $migrateScriptPath -TargetDirectory $experimentPath -NonInteractive
        }
        
        if ($LASTEXITCODE -ne 0) {
            throw "Migration failed for experiment: $experimentName. Halting study migration."
        }
    }

    Write-Host "`n--- Migration process complete. ---" -ForegroundColor Green
    Write-Host "Note: Migrated experiments are created in the 'output/migrated_experiments/' directory." -ForegroundColor Yellow
    Write-Host "The original study directory is unchanged. You may need to run another audit on the" -ForegroundColor Yellow
    Write-Host "newly created migrated experiments." -ForegroundColor Yellow
    
    $headerLine = "#" * 80
    Write-Host "`n$headerLine" -ForegroundColor Green
    Write-Host (Format-Banner "Study Migration Completed Successfully") -ForegroundColor Green
    Write-Host "$headerLine" -ForegroundColor Green

} catch {
    $headerLine = "#" * 80
    Write-Host "`n$headerLine" -ForegroundColor Red
    Write-Host (Format-Banner "STUDY MIGRATION FAILED") -ForegroundColor Red
    Write-Host "$headerLine" -ForegroundColor Red
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# === End of migrate_study.ps1 ===