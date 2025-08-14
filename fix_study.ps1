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
# Filename: fix_study.ps1

<#
.SYNOPSIS
    Fixes, updates, or resumes all incomplete or outdated experiments within a study directory.

.DESCRIPTION
    This script provides a high-level workflow for bringing an entire study into a valid and
    up-to-date state. It first performs a comprehensive, read-only audit of every experiment
    within the specified study directory.

    Based on the audit, it identifies which experiments require any kind of fix (e.g., repair,
    update, resume). If any experiments are found to need migration, the script will halt with
    an error, recommending that 'migrate_study.ps1' be run first.

    If fixable issues are found, it will list the affected experiments, ask for a single user
    confirmation, and then sequentially call 'fix_experiment.ps1' non-interactively on each one.

.PARAMETER TargetDirectory
    The path to the study directory containing multiple experiment folders.

.PARAMETER Verbose
    If specified, displays the full, detailed output from each individual 'fix_experiment.ps1' call.

.EXAMPLE
    # Run a fix on a study, which will first audit and then prompt for confirmation.
    .\fix_study.ps1 -TargetDirectory "output/studies/My_First_Study"
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
$logFileName = "study_fix_log.txt"
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
    # Use -Force to overwrite the fix log, even if it's read-only.
    Start-Transcript -Path $logFilePath -Force | Out-Null
    
    Write-Host "" # Blank line before message
    Write-Host "The fix log will be saved to:" -ForegroundColor Gray
    $relativePath = Resolve-Path -Path $logFilePath -Relative
    Write-Host $relativePath -ForegroundColor Gray

    # --- Auto-detect execution environment ---
    $executable = "python"
    $prefixArgs = @()
    if (Get-Command pdm -ErrorAction SilentlyContinue) {
        $executable = "pdm"
        $prefixArgs = "run", "python"
    }

    # --- Define Audit Exit Codes from experiment_auditor.py ---
    $AUDIT_ALL_VALID       = 0
    $AUDIT_NEEDS_REPROCESS = 1
    $AUDIT_NEEDS_REPAIR    = 2
    $AUDIT_NEEDS_MIGRATION = 3
    $AUDIT_NEEDS_AGGREGATION = 4

    # --- Perform a single, visible audit to gather state and inform user ---
    $headerLine = "#" * 80
    $C_CYAN = "`e[96m"
    Write-Host "`n$($C_CYAN)$headerLine"
    Write-Host "$($C_CYAN)$(Format-Banner "RUNNING PRE-FIX AUDIT")"
    Write-Host "$($C_CYAN)$headerLine`n"

    $experimentDirs = Get-ChildItem -Path $TargetDirectory -Directory | Where-Object { $_.Name -ne 'anova' }
    if ($experimentDirs.Count -eq 0) {
        Write-Host "No experiment directories found in '$TargetDirectory'." -ForegroundColor Yellow
        return
    }

    # Print Real-time Audit Table Header
    $progressWidth = 10
    $experimentNameCap = 40
    Write-Host ("{0,-$progressWidth} {1,-$experimentNameCap} {2}" -f "Progress", "Experiment", "Result")
    Write-Host ("-" * $progressWidth + " " + "-" * $experimentNameCap + " " + "-" * 8)

    $experimentsToFix = [System.Collections.Generic.List[string]]::new()
    $experimentsToMigrate = [System.Collections.Generic.List[string]]::new()
    $allExperimentsValid = $true
    $auditorScriptPath = "src/experiment_auditor.py"
    $i = 0

    foreach ($dir in $experimentDirs) {
        $i++
        $progress = "$i/$($experimentDirs.Count)"
        $displayName = if ($dir.Name.Length -gt $experimentNameCap) { ($dir.Name.Substring(0, $experimentNameCap - 3) + "...") } else { $dir.Name }
        Write-Host ("{0,-$progressWidth} {1,-$experimentNameCap} " -f $progress, $displayName) -NoNewline

        & $executable $prefixArgs $auditorScriptPath $dir.FullName --quiet --force-color
        $exitCode = $LASTEXITCODE

        $statusText, $color = switch ($exitCode) {
            $AUDIT_ALL_VALID         { "[ OK ]", "Green"; break }
            $AUDIT_NEEDS_REPROCESS   { "[ WARN ]", "Yellow"; break }
            $AUDIT_NEEDS_REPAIR      { "[ FAIL ]", "Red"; break }
            $AUDIT_NEEDS_MIGRATION   { "[ FAIL ]", "Red"; break }
            $AUDIT_NEEDS_AGGREGATION { "[ WARN ]", "Yellow"; break }
            default                  { "[ ?? ]", "Red"; break }
        }
        Write-Host $statusText -ForegroundColor $color

        if ($exitCode -eq $AUDIT_NEEDS_MIGRATION) {
            $experimentsToMigrate.Add($dir.Name)
            $allExperimentsValid = $false
        } elseif ($exitCode -ne $AUDIT_ALL_VALID) {
            $experimentsToFix.Add($dir.Name)
            $allExperimentsValid = $false
        }
    }
    Write-Host "" # Newline after progress table

    # --- Main Logic branches based on the reliable audit results ---

    if ($experimentsToMigrate.Count -gt 0) {
        throw "Audit found experiments that require migration. Please run 'migrate_study.ps1' to handle these experiments before proceeding with a fix."
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
      'fix_experiment.ps1' directly on its directory.

Enter your choice (1, 2, or N)
"@
        $choice = Read-Host -Prompt $prompt
        $actionTaken = $false
        $fixScriptPath = Join-Path $ScriptRoot "fix_experiment.ps1"

        switch ($choice.Trim().ToLower()) {
            '1' {
                $i = 0
                foreach ($experimentDir in $experimentDirs) {
                    $i++
                    Write-Host "`n--- Forcing Update on experiment $i of $($experimentDirs.Count): $($experimentDir.Name) ---" -ForegroundColor Cyan
                    & $fixScriptPath -TargetDirectory $experimentDir.FullName -ForceUpdate
                    if ($LASTEXITCODE -ne 0) { throw "Forced update failed for experiment: $($experimentDir.Name)." }
                }
                $actionTaken = $true
            }
            '2' {
                 $i = 0
                foreach ($experimentDir in $experimentDirs) {
                    $i++
                    Write-Host "`n--- Forcing Aggregation on experiment $i of $($experimentDirs.Count): $($experimentDir.Name) ---" -ForegroundColor Cyan
                    & $fixScriptPath -TargetDirectory $experimentDir.FullName -ForceAggregate
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

    # Correct path for a study that needs fixing
    Write-Host "`nThe following $($experimentsToFix.Count) experiment(s) will be fixed/updated:" -ForegroundColor Yellow
    $experimentsToFix | ForEach-Object { Write-Host " - $_" }

    $choice = Read-Host "`nDo you wish to proceed with the fix? (Y/N)"
    if ($choice.Trim().ToLower() -ne 'y') {
        Write-Host "`nFix aborted by user." -ForegroundColor Yellow
        return
    }

    $fixScriptPath = Join-Path $ScriptRoot "fix_experiment.ps1"
    $i = 0
    foreach ($experimentName in $experimentsToFix) {
        $i++
        $experimentPath = Join-Path $TargetDirectory $experimentName
        Write-Host "`n--- Fixing experiment $i of $($experimentsToFix.Count): $experimentName ---" -ForegroundColor Cyan
        
        $fixArgs = @{ TargetDirectory = $experimentPath; NonInteractive = $true }
        if ($PSBoundParameters['Verbose']) { $fixArgs['Verbose'] = $true }
        & $fixScriptPath @fixArgs
        
        if ($LASTEXITCODE -ne 0) {
            throw "Fix failed for experiment: $experimentName. Halting study fix."
        }
    }

    Write-Host "`n--- Running post-fix audit to verify all changes... ---" -ForegroundColor Cyan
    & $auditScriptPath -TargetDirectory $TargetDirectory -NoLog
    
    $headerLine = "#" * 80
    Write-Host "`n$headerLine" -ForegroundColor Green
    Write-Host (Format-Banner "Study Fix Completed Successfully") -ForegroundColor Green
    Write-Host "$headerLine" -ForegroundColor Green

} catch {
    $headerLine = "#" * 80
    Write-Host "`n$headerLine" -ForegroundColor Red
    Write-Host (Format-Banner "STUDY FIX FAILED") -ForegroundColor Red
    Write-Host "$headerLine" -ForegroundColor Red
    Write-Host "ERROR: $($_.Exception.Message)`n" -ForegroundColor Red
    exit 1
} finally {
    # Stop the transcript silently to suppress the default message
    Stop-Transcript | Out-Null
    
    # Only print the custom message if a fix log was actually created.
    if (Test-Path -LiteralPath $logFilePath) {
        Write-Host "`nThe fix log has been saved to:" -ForegroundColor Gray
        $relativePath = Resolve-Path -Path $logFilePath -Relative
        Write-Host $relativePath -ForegroundColor Gray
        Write-Host "" # Add a blank line for spacing
    }
}

# === End of fix_study.ps1 ===
