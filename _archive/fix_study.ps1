#!/usr/bin/env pwsh
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 Peter J. Marko
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
    [Parameter(Mandatory = $false, HelpMessage = "Path to a specific config.ini file to use for this operation.")]
    [Alias('config-path')]
    [string]$ConfigPath,

    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the study directory containing one or more experiments.")]
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
if (-not (Test-Path -Path $StudyDirectory -PathType Container)) {
    throw "Study directory not found: $StudyDirectory"
}
$logFilePath = Join-Path $StudyDirectory $logFileName

# --- Auto-detect execution environment ---
$executable = "python"
$prefixArgs = @()
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    $executable = "pdm"
    $prefixArgs = "run", "python"
}

$ScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
$StudyAuditScriptPath = Join-Path $ScriptRoot "audit_study.ps1"

# --- Auto-detect execution environment (once, at the top) ---
$executable = "python"
$prefixArgs = @()
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    Write-Host "`nPDM detected. Using 'pdm run' to execute Python scripts." -ForegroundColor Cyan
    $executable = "pdm"
    $prefixArgs = "run", "python"
}
else {
    Write-Host "PDM not detected. Using standard 'python' command." -ForegroundColor Yellow
}

try {
    # Use -Force to overwrite the fix log, even if it's read-only.
    Start-Transcript -Path $logFilePath -Force | Out-Null
    
    Write-Host "" # Blank line before message
    Write-Host "The fix log will be saved to:" -ForegroundColor Gray
    $relativePath = Resolve-Path -Path $logFilePath -Relative
    Write-Host $relativePath -ForegroundColor Gray

    # --- Define Audit Exit Codes from experiment_auditor.py ---
    $AUDIT_ALL_VALID       = 0
    $AUDIT_NEEDS_MIGRATION = 3

    # --- Phase 1: Quietly audit to determine the true state ---
    Write-Host "`n--- Performing pre-fix audit of the entire study... ---" -ForegroundColor Cyan
    $experimentDirs = Get-ChildItem -Path $StudyDirectory -Directory | Where-Object { $_.Name -ne 'anova' }
    if ($experimentDirs.Count -eq 0) {
        Write-Host "No experiment directories found in '$StudyDirectory'." -ForegroundColor Yellow
        return
    }

    $experimentsToFix = [System.Collections.Generic.List[string]]::new()
    $experimentsToMigrate = [System.Collections.Generic.List[string]]::new()
    $allExperimentsValid = $true
    $auditorScriptPath = "src/experiment_auditor.py"

    foreach ($dir in $experimentDirs) {
        $auditorArgs = @($dir.FullName, "--quiet", "--force-color")
        if (-not [string]::IsNullOrEmpty($ConfigPath)) { $auditorArgs += "--config-path", $ConfigPath }
        
        & $executable $prefixArgs $auditorScriptPath @auditorArgs
        $exitCode = $LASTEXITCODE

        if ($exitCode -eq $AUDIT_NEEDS_MIGRATION) {
            $experimentsToMigrate.Add($dir.Name)
            $allExperimentsValid = $false
        } elseif ($exitCode -ne $AUDIT_ALL_VALID) {
            $experimentsToFix.Add($dir.Name)
            $allExperimentsValid = $false
        }
    }
    
    # --- Phase 2: Show the user the official audit report ---
    # We call the main audit script to give a consistent, rich report.
    # We call the main audit script to give a consistent, rich report.
    $auditStudySplat = @{
        StudyDirectory = $StudyDirectory
        NoLog          = $true
        NoHeader       = $true
    }
    if (-not [string]::IsNullOrEmpty($ConfigPath)) { $auditStudySplat['ConfigPath'] = $ConfigPath }
    & $StudyAuditScriptPath @auditStudySplat

    # --- Main Logic branches based on the reliable audit results ---

    if ($experimentsToMigrate.Count -gt 0) {
        $headerLine = "#" * 80
        $c_yellow = "`e[93m"
        Write-Host "`n$headerLine" -ForegroundColor Yellow
        Write-Host (Format-Banner "STUDY FIX HALTED") -ForegroundColor Yellow
        Write-Host "$headerLine" -ForegroundColor Yellow
        Write-Host "" # Blank line
        $message = "One or more experiments are not fixable in their current state. Please see the audit result and recommendation above."
        Write-Host $message -ForegroundColor Yellow
        Write-Host "" # Blank line
        exit 1
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
                    $fixUpdArgs = @{ ExperimentDirectory = $experimentDir.FullName; ForceUpdate = $true }
                    if (-not [string]::IsNullOrEmpty($ConfigPath)) { $fixUpdArgs['ConfigPath'] = $ConfigPath }
                    & $fixScriptPath @fixUpdArgs
                    if ($LASTEXITCODE -ne 0) { throw "Forced update failed for experiment: $($experimentDir.Name)." }
                }
                $actionTaken = $true
            }
            '2' {
                 $i = 0
                foreach ($experimentDir in $experimentDirs) {
                    $i++
                    Write-Host "`n--- Forcing Aggregation on experiment $i of $($experimentDirs.Count): $($experimentDir.Name) ---" -ForegroundColor Cyan
                    $fixAggArgs = @{ ExperimentDirectory = $experimentDir.FullName; ForceAggregate = $true }
                    if (-not [string]::IsNullOrEmpty($ConfigPath)) { $fixAggArgs['ConfigPath'] = $ConfigPath }
                    & $fixScriptPath @fixAggArgs
                    if ($LASTEXITCODE -ne 0) { throw "Forced aggregation failed for experiment: $($experimentDir.Name)." }
                }
                $actionTaken = $true
            }
            'n' { Write-Host "`nNo action taken." -ForegroundColor Yellow; return }
            default { Write-Warning "`nInvalid choice. No action taken."; return }
        }

        if ($actionTaken) {
            Write-Host "`n--- Running post-action audit to verify all changes... ---" -ForegroundColor Cyan
            $auditStudySplat = @{
                StudyDirectory = $StudyDirectory
                NoLog          = $true
                NoHeader       = $true
            }
            if (-not [string]::IsNullOrEmpty($ConfigPath)) { $auditStudySplat['ConfigPath'] = $ConfigPath }
            & $StudyAuditScriptPath @auditStudySplat
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
    $headerLine = "#" * 80
    $C_CYAN = "`e[96m"

    foreach ($experimentName in $experimentsToFix) {
        $i++
        $experimentPath = Join-Path $StudyDirectory $experimentName
        $bannerMessage = "Fixing Experiment $i of $($experimentsToFix.Count): $experimentName"
        Write-Host "`n$($C_CYAN)$headerLine"
        Write-Host "$($C_CYAN)$(Format-Banner $bannerMessage)"
        Write-Host "$($C_CYAN)$headerLine`n"
        
        $fixArgs = @{
            ExperimentDirectory = $experimentPath
            NonInteractive      = $true
            NoHeader            = $true
        }
        if ($PSBoundParameters['Verbose']) { $fixArgs['Verbose'] = $true }
        if (-not [string]::IsNullOrEmpty($ConfigPath)) { $fixArgs['ConfigPath'] = $ConfigPath }
        & $fixScriptPath @fixArgs
        
        if ($LASTEXITCODE -ne 0) {
            throw "Fix failed for experiment: $experimentName. Halting study fix."
        }
    }

    Write-Host "`n--- Running post-fix audit to verify all changes... ---" -ForegroundColor Cyan
    $auditStudySplat = @{
        StudyDirectory = $StudyDirectory
        NoLog          = $true
        NoHeader       = $true
    }
    if (-not [string]::IsNullOrEmpty($ConfigPath)) { $auditStudySplat['ConfigPath'] = $ConfigPath }
    & $StudyAuditScriptPath @auditStudySplat
    
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
