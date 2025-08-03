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

.PARAMETER TargetDirectory
    The path to the study directory containing multiple experiment folders.

.PARAMETER Verbose
    If specified, displays the full, detailed output from each individual 'repair_experiment.ps1' call.

.EXAMPLE
    # Run a repair on a study, which will first audit and then prompt for confirmation.
    .\repair_study.ps1 -TargetDirectory "output/studies/My_First_Study"
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the target directory containing one or more experiments.")]
    [string]$TargetDirectory
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

    if ($paddedMessage.Length -ge $contentWidth) {
        # If the message is too long, just return it without centering.
        return "$prefix$paddedMessage$suffix"
    }

    $paddingTotal = $contentWidth - $paddedMessage.Length
    $paddingLeft = [Math]::Floor($paddingTotal / 2)
    $paddingRight = $paddingTotal - $paddingLeft

    $content = (" " * $paddingLeft) + $paddedMessage + (" " * $paddingRight)
    
    return "$prefix$content$suffix"
}

# --- Logging Setup ---
$logFileName = "study_repair_log.txt"
if (-not (Test-Path -Path $TargetDirectory -PathType Container)) {
    throw "Study directory not found: $TargetDirectory"
}
$logFilePath = Join-Path $TargetDirectory $logFileName

# --- Auto-detect execution environment ---
$executable = "python"
$prefixArgs = @()
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    $executable = "pdm"
    $prefixArgs = "run", "python"
}

$ScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition

try {
    # Use -Force to overwrite the repair log, even if it's read-only.
    Start-Transcript -Path $logFilePath -Force | Out-Null
    
    Write-Host "" # Blank line before message
    Write-Host "The repair log will be saved to:" -ForegroundColor Gray
    $relativePath = Resolve-Path -Path $logFilePath -Relative
    Write-Host $relativePath -ForegroundColor Gray

    # --- Auto-detect execution environment ---
    $executable = "python"
    $prefixArgs = @()
    if (Get-Command pdm -ErrorAction SilentlyContinue) {
        $executable = "pdm"
        $prefixArgs = "run", "python"
    }

    # --- Define Audit Exit Codes from experiment_manager.py ---
    $AUDIT_ALL_VALID       = 0
    $AUDIT_NEEDS_REPROCESS = 1
    $AUDIT_NEEDS_REPAIR    = 2
    $AUDIT_NEEDS_MIGRATION = 3
    $AUDIT_NEEDS_AGGREGATION = 4

    Write-Host "`n--- Performing pre-repair audit of the entire study... ---" -ForegroundColor Cyan
    $experimentDirs = Get-ChildItem -Path $TargetDirectory -Directory | Where-Object { $_.Name -ne 'anova' }
    if ($experimentDirs.Count -eq 0) {
        Write-Host "No experiment directories found in '$TargetDirectory'." -ForegroundColor Yellow
        return
    }

    $experimentsToFix = [System.Collections.Generic.List[string]]::new()
    $experimentsToMigrate = [System.Collections.Generic.List[string]]::new()
    $allExperimentsValid = $true

    # This new loop performs a reliable, quiet audit on each experiment.
    foreach ($dir in $experimentDirs) {
        & $executable $prefixArgs src/experiment_manager.py --verify-only --quiet $dir.FullName
        $exitCode = $LASTEXITCODE

        if ($exitCode -eq $AUDIT_NEEDS_MIGRATION) {
            $experimentsToMigrate.Add($dir.Name)
            $allExperimentsValid = $false
        } elseif ($exitCode -ne $AUDIT_ALL_VALID) {
            $experimentsToFix.Add($dir.Name)
            $allExperimentsValid = $false
        }
    }

    # Now, run the full, visible audit so the user sees the report.
    $auditScriptPath = Join-Path $ScriptRoot "audit_study.ps1"
    & $auditScriptPath -TargetDirectory $TargetDirectory -NoLog

    # --- Main Logic branches based on the reliable audit results ---

    if ($experimentsToMigrate.Count -gt 0) {
        throw "Audit found experiments that require migration. Please run 'migrate_study.ps1' to handle these experiments before proceeding with a repair."
    }

    if ($allExperimentsValid) {
        # Correct path for a valid study
        Write-Host "`nStudy is already complete and valid." -ForegroundColor Yellow
        
        $prompt = @"

Do you still want to proceed with updating or aggregating all experiments?

(1) Full Update: Re-runs analysis on existing data for all experiments. (Safe)
(2) Aggregation Only: Re-creates top-level summary files for all experiments. (Fastest)
(N) No Action

Note: For safety reasons, a study-wide LLM-level repair is not available. 
      To force a repair on a single experiment, please run 
      'repair_experiment.ps1' directly on its directory.

Enter your choice (1, 2, or N)
"@
        $choice = Read-Host -Prompt $prompt
        $actionTaken = $false
        $repairScriptPath = Join-Path $ScriptRoot "repair_experiment.ps1"

        switch ($choice.Trim().ToLower()) {
            '1' {
                $i = 0
                foreach ($experimentDir in $experimentDirs) {
                    $i++
                    Write-Host "`n--- Forcing Update on experiment $i of $($experimentDirs.Count): $($experimentDir.Name) ---" -ForegroundColor Cyan
                    & $repairScriptPath -TargetDirectory $experimentDir.FullName -ForceUpdate
                    if ($LASTEXITCODE -ne 0) { throw "Forced update failed for experiment: $($experimentDir.Name)." }
                }
                $actionTaken = $true
            }
            '2' {
                 $i = 0
                foreach ($experimentDir in $experimentDirs) {
                    $i++
                    Write-Host "`n--- Forcing Aggregation on experiment $i of $($experimentDirs.Count): $($experimentDir.Name) ---" -ForegroundColor Cyan
                    & $repairScriptPath -TargetDirectory $experimentDir.FullName -ForceAggregate
                    if ($LASTEXITCODE -ne 0) { throw "Forced aggregation failed for experiment: $($experimentDir.Name)." }
                }
                $actionTaken = $true
            }
            'n' { Write-Host "`nNo action taken." -ForegroundColor Yellow; return }
            default { Write-Warning "`nInvalid choice. No action taken."; return }
        }

        if ($actionTaken) {
            Write-Host "`n--- Running post-action audit to verify all changes... ---" -ForegroundColor Cyan
            & $auditScriptPath -TargetDirectory $TargetDirectory -NoLog
            $headerLine = "#" * 80
            Write-Host "`n$headerLine" -ForegroundColor Green
            Write-Host (Format-Banner "Study Action Completed Successfully") -ForegroundColor Green
            Write-Host "$headerLine" -ForegroundColor Green
        }
        return
    }

    # Correct path for a study that needs repair
    Write-Host "`nThe following $($experimentsToFix.Count) experiment(s) will be repaired/updated:" -ForegroundColor Yellow
    $experimentsToFix | ForEach-Object { Write-Host " - $_" }

    $choice = Read-Host "`nDo you wish to proceed with the repair? (Y/N)"
    if ($choice.Trim().ToLower() -ne 'y') {
        Write-Host "`nRepair aborted by user." -ForegroundColor Yellow
        return
    }

    $repairScriptPath = Join-Path $ScriptRoot "repair_experiment.ps1"
    $i = 0
    foreach ($experimentName in $experimentsToFix) {
        $i++
        $experimentPath = Join-Path $TargetDirectory $experimentName
        Write-Host "`n--- Repairing experiment $i of $($experimentsToFix.Count): $experimentName ---" -ForegroundColor Cyan
        
        $repairArgs = @{ TargetDirectory = $experimentPath; NonInteractive = $true }
        if ($PSBoundParameters['Verbose']) { $repairArgs['Verbose'] = $true }
        & $repairScriptPath @repairArgs
        
        if ($LASTEXITCODE -ne 0) {
            throw "Repair failed for experiment: $experimentName. Halting study repair."
        }
    }

    Write-Host "`n--- Running post-repair audit to verify all changes... ---" -ForegroundColor Cyan
    & $auditScriptPath -TargetDirectory $TargetDirectory -NoLog
    
    $headerLine = "#" * 80
    Write-Host "`n$headerLine" -ForegroundColor Green
    Write-Host (Format-Banner "Study Repair Completed Successfully") -ForegroundColor Green
    Write-Host "$headerLine" -ForegroundColor Green

} catch {
    $headerLine = "#" * 80
    Write-Host "`n$headerLine" -ForegroundColor Red
    Write-Host (Format-Banner "STUDY REPAIR FAILED") -ForegroundColor Red
    Write-Host "$headerLine" -ForegroundColor Red
    Write-Host "ERROR: $($_.Exception.Message)`n" -ForegroundColor Red
    exit 1
} finally {
    # Stop the transcript silently to suppress the default message
    Stop-Transcript | Out-Null
    
    # Only print the custom message if a repair log was actually created.
    if (Test-Path -LiteralPath $logFilePath) {
        Write-Host "`nThe repair log has been saved to:" -ForegroundColor Gray
        $relativePath = Resolve-Path -Path $logFilePath -Relative
        Write-Host $relativePath -ForegroundColor Gray
        Write-Host "" # Add a blank line for spacing
    }
}

# === End of repair_study.ps1 ===