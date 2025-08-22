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
# Filename: migrate_study.ps1

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

.PARAMETER TargetDirectory
    The path to the study directory containing multiple experiment folders.

.PARAMETER Verbose
    If specified, displays the full, detailed output from each individual 'migrate_experiment.ps1' call.

.EXAMPLE
    # Run a migration on a study, which will first audit and then prompt for confirmation.
    .\migrate_study.ps1 -TargetDirectory "output/studies/My_Legacy_Study"
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory = $false, HelpMessage = "Path to a specific config.ini file to use for this operation.")]
    [Alias('config-path')]
    [string]$ConfigPath,

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

$ScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition

# --- Logging Setup ---
$logFileName = "study_migration_log.txt"
if (-not (Test-Path -Path $TargetDirectory -PathType Container)) {
    throw "Study directory not found: $TargetDirectory"
}
$logFilePath = Join-Path $TargetDirectory $logFileName

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
    # Use -Force to overwrite the log file, even if it's read-only.
    Start-Transcript -Path $logFilePath -Force | Out-Null
    
    Write-Host "" # Blank line before message
    Write-Host "The migration log will be saved to:" -ForegroundColor Gray
    $relativePath = Resolve-Path -Path $logFilePath -Relative
    Write-Host $relativePath -ForegroundColor Gray

    # --- Define Audit Exit Codes from experiment_auditor.py ---
    $AUDIT_ALL_VALID       = 0
    $AUDIT_NEEDS_MIGRATION = 3

    Write-Host "`n--- Performing pre-migration audit of the entire study... ---" -ForegroundColor Cyan
    $experimentDirs = Get-ChildItem -Path $TargetDirectory -Directory | Where-Object { $_.Name -ne 'anova' }
    if ($experimentDirs.Count -eq 0) {
        Write-Host "No experiment directories found in '$TargetDirectory'." -ForegroundColor Yellow
        return
    }

    $experimentsToMigrate = [System.Collections.Generic.List[string]]::new()
    $needsRepair = $false
    $auditorScriptPath = "src/experiment_auditor.py"

    # This loop performs a reliable, quiet audit on each experiment.
    foreach ($dir in $experimentDirs) {
        $auditorArgs = @($dir.FullName, "--quiet")
        if (-not [string]::IsNullOrEmpty($ConfigPath)) { $auditorArgs += "--config-path", $ConfigPath }
        
        & $executable $prefixArgs $auditorScriptPath @auditorArgs
        $exitCode = $LASTEXITCODE

        if ($exitCode -eq $AUDIT_NEEDS_MIGRATION) {
            $experimentsToMigrate.Add($dir.Name)
        } elseif ($exitCode -ne $AUDIT_ALL_VALID) {
            $needsRepair = $true
        }
    }

    # Now, run the full, visible audit so the user sees the report.
    $auditScriptPath = Join-Path $ScriptRoot "audit_study.ps1"
    $auditStudyArgs = @{ TargetDirectory = $TargetDirectory; NoLog = $true; NoHeader = $true }
    if (-not [string]::IsNullOrEmpty($ConfigPath)) { $auditStudyArgs['ConfigPath'] = $ConfigPath }
    & $auditScriptPath @auditStudyArgs

    # --- Main Logic branches based on the reliable audit results ---
    if ($needsRepair) {
        $headerLine = "#" * 80
        Write-Host "`n$headerLine" -ForegroundColor Yellow
        Write-Host (Format-Banner "STUDY MIGRATION HALTED") -ForegroundColor Yellow
        Write-Host "$headerLine" -ForegroundColor Yellow
        Write-Host "" # Blank line
        $message = "The study contains issues that must be resolved first. Please see the audit result and recommendation above."
        Write-Host $message -ForegroundColor Yellow
        Write-Host "" # Blank line
        exit 1
    }

    if ($experimentsToMigrate.Count -eq 0) {
        Write-Host "`nAll experiments are valid. No migration is required." -ForegroundColor Yellow
        
        $prompt = @"

You can force a migration on all experiments in the study. This will create
a clean, upgraded copy of the entire study in the 'output/migrated_studies/'
directory, leaving the originals untouched.

(1) Force Migration for all experiments
(N) No Action

Enter your choice (1 or N)
"@
        $choice = Read-Host -Prompt $prompt
        
        if ($choice.Trim().ToLower() -eq '1') {
            # Create a new, timestamped directory for the entire migrated study.
            $studyBaseName = (Get-Item -Path $TargetDirectory).Name
            $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
            $newStudyFolderName = "${studyBaseName}_migrated_${timestamp}"
            $migratedStudyParent = "output/migrated_studies"
            $migratedStudyPath = Join-Path -Path $migratedStudyParent -ChildPath $newStudyFolderName
            
            Write-Host "`nCreating new study directory at: $migratedStudyPath" -ForegroundColor Cyan
            New-Item -ItemType Directory -Path $migratedStudyPath -Force | Out-Null

            $migrateScriptPath = Join-Path $ScriptRoot "migrate_experiment.ps1"
            $i = 0
            $headerLine = "#" * 80
            $C_CYAN = "`e[96m"

            foreach ($experimentDir in $experimentDirs) {
                $i++
                $bannerMessage = "Forcing Migration on Experiment $i of $($experimentDirs.Count): $($experimentDir.Name)"
                Write-Host "`n$($C_CYAN)$headerLine"
                Write-Host "$($C_CYAN)$(Format-Banner $bannerMessage)"
                Write-Host "$($C_CYAN)$headerLine`n"
                
                # Pass the new study directory as the destination for the worker script.
                $migrateArgs = @{
                    TargetDirectory   = $experimentDir.FullName
                    DestinationParent = $migratedStudyPath
                    NonInteractive    = $true
                    NoHeader          = $true
                }
                if ($PSBoundParameters['Verbose']) { $migrateArgs['Verbose'] = $true }
                if (-not [string]::IsNullOrEmpty($ConfigPath)) { $migrateArgs['ConfigPath'] = $ConfigPath }
                & $migrateScriptPath @migrateArgs
                
                if ($LASTEXITCODE -ne 0) {
                    throw "Forced migration failed for experiment: $($experimentDir.Name)."
                }
            }
            Write-Host "`n--- Forced migration process complete. ---" -ForegroundColor Green
            Write-Host "Migrated study created at: $migratedStudyPath" -ForegroundColor Green
        } else {
            Write-Host "`nNo action taken." -ForegroundColor Yellow
        }
        return
    }

    Write-Host "`nThe following $($experimentsToMigrate.Count) experiment(s) will be migrated:" -ForegroundColor Yellow
    $experimentsToMigrate | ForEach-Object { Write-Host " - $_" }

    $choice = Read-Host "`nDo you wish to proceed with the migration? (Y/N)"
    if ($choice.Trim().ToLower() -ne 'y') {
        Write-Host "`nMigration aborted by user." -ForegroundColor Yellow
        return
    }

    $migrateScriptPath = Join-Path $ScriptRoot "migrate_experiment.ps1"
    $i = 0
    $headerLine = "#" * 80
    $C_CYAN = "`e[96m"

    foreach ($experimentName in $experimentsToMigrate) {
        $i++
        $experimentPath = Join-Path $TargetDirectory $experimentName
        $bannerMessage = "Migrating Experiment $i of $($experimentsToMigrate.Count): $experimentName"
        Write-Host "`n$($C_CYAN)$headerLine"
        Write-Host "$($C_CYAN)$(Format-Banner $bannerMessage)"
        Write-Host "$($C_CYAN)$headerLine`n"
        
        # Add NonInteractive = $true to suppress the redundant confirmation prompt
        # in the worker script.
        $migrateArgs = @{
            TargetDirectory = $experimentPath
            NonInteractive  = $true
            NoHeader        = $true
        }
        if ($PSBoundParameters['Verbose']) { $migrateArgs['Verbose'] = $true }
        if (-not [string]::IsNullOrEmpty($ConfigPath)) { $migrateArgs['ConfigPath'] = $ConfigPath }
        & $migrateScriptPath @migrateArgs
        
        if ($LASTEXITCODE -ne 0) {
            throw "Migration failed for experiment: $experimentName. Halting study migration."
        }
    }

    Write-Host "`n--- Migration process complete. ---" -ForegroundColor Green
    Write-Host "Note: Migrated experiments are created in the 'output/migrated_experiments/' directory." -ForegroundColor Yellow
    
    $headerLine = "#" * 80
    Write-Host "`n$headerLine" -ForegroundColor Green
    Write-Host (Format-Banner "Study Migration Completed Successfully") -ForegroundColor Green
    Write-Host "$headerLine`n" -ForegroundColor Green
} catch {
    $headerLine = "#" * 80
    Write-Host "`n$headerLine" -ForegroundColor Red
    Write-Host (Format-Banner "STUDY MIGRATION FAILED") -ForegroundColor Red
    Write-Host "$headerLine" -ForegroundColor Red
    Write-Host "ERROR: $($_.Exception.Message)`n" -ForegroundColor Red
    exit 1
} finally {
    # Stop the transcript silently to suppress the default message
    Stop-Transcript | Out-Null
    
    # Only print the custom message if a log file was actually created.
    if (Test-Path -LiteralPath $logFilePath) {
        Write-Host "`nThe migration log has been saved to:" -ForegroundColor Gray
        $relativePath = Resolve-Path -Path $logFilePath -Relative
        Write-Host $relativePath -ForegroundColor Gray
        Write-Host "" # Add a blank line for spacing
    }
}

# === End of migrate_study.ps1 ===
