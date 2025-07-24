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
# Filename: audit_experiment.ps1

<#
.SYNOPSIS
    Provides a read-only, detailed completeness report for a specified experiment.

.DESCRIPTION
    This script calls the core 'experiment_manager.py' in a read-only diagnostic mode.
    It audits the specified experiment directory and prints a comprehensive report
    without making any changes. A detailed log is also saved as 'audit_log.txt'
    inside the audited directory.

    By default, it shows a summary and prompts for confirmation before running.

.PARAMETER TargetDirectory
    The path to the experiment directory to audit. This is a mandatory parameter.

.PARAMETER Force
    A switch to bypass the confirmation prompt for automated or scripted use.

.PARAMETER Verbose
    A switch to enable detailed, real-time output from the underlying Python script.

.EXAMPLE
    # Run a standard interactive audit on an experiment.
    .\audit_experiment.ps1 -TargetDirectory "output/reports/My_Experiment"

.EXAMPLE
    # Run a non-interactive audit for use in an automated script.
    .\audit_experiment.ps1 -TargetDirectory "output/reports/My_Experiment" -Force

.EXAMPLE
    # Run a detailed audit with verbose logging.
    .\audit_experiment.ps1 -TargetDirectory "output/reports/My_Experiment" -Verbose
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the experiment directory to audit.")]
    [string]$TargetDirectory,

    [Parameter(Mandatory = $false)]
    [switch]$Force
)

# --- Auto-detect execution environment ---
$executable = "python"
$prefixArgs = @()
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    $executable = "pdm"
    $prefixArgs = "run", "python"
}

# --- Helper function for post-processing the log file ---
function Format-LogFile {
    param([string]$Path)
    
    try {
        if (-not (Test-Path $Path)) { return }

        $lines = Get-Content -Path $Path
        $newLines = @()

        foreach ($line in $lines) {
            $newLine = $line
            if ($line.Trim().StartsWith("Start time:") -or $line.Trim().StartsWith("End time:")) {
                $parts = $line.Split(':')
                if ($parts.Length -ge 2) {
                    $prefix = $parts[0] + ":"
                    $timestampStr = ($parts[1..($parts.Length - 1)] -join ':').Trim()

                    if ($timestampStr -match "^\d{14}$") {
                        $dateTimeObj = [datetime]::ParseExact($timestampStr, 'yyyyMMddHHmmss', $null)
                        $formattedTimestamp = $dateTimeObj.ToString('yyyy-MM-dd HH:mm:ss')
                        $newLine = "$prefix $formattedTimestamp"
                    }
                }
            }
            $newLines += $newLine
        }
        
        Set-Content -Path $Path -Value $newLines -Encoding UTF8
    }
    catch {
        # If post-processing fails, do not crash the script. The original log is preserved.
    }
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
    # --- Display a summary and ask for confirmation (unless -Force is used) ---
    if (-not $Force.IsPresent) {
        Write-Host "`n--- Audit Configuration Summary ---" -ForegroundColor Cyan
        Write-Host "Action:            Audit an EXISTING experiment."
        Write-Host "Target Directory:  $TargetDirectory"
        Write-Host "---------------------------------" -ForegroundColor Cyan

        $choice = Read-Host "`nDo you wish to proceed with the audit? (Y/N)"
        if ($choice.Trim().ToLower() -ne 'y') {
            Write-Host "Audit aborted by user." -ForegroundColor Yellow
            Write-Host "" # Add a blank line for separation
            exit 0 # A clean exit since the user chose to abort.
        }
    }

    $ResolvedPath = Resolve-Path -Path $TargetDirectory -ErrorAction Stop

    $scriptName = "src/experiment_manager.py"
    # The path must be preceded by the --target_dir flag.
    $arguments = @("--verify-only", "--target_dir", $ResolvedPath)
    if ($PSBoundParameters.ContainsKey('Verbose') -and $PSBoundParameters['Verbose']) {
        $arguments += "--verbose"
    }

    # Force the python script to generate color for stream processing
    $arguments += "--force-color"
    $finalArgs = $prefixArgs + $scriptName + $arguments

    # Define the log file path
    $LogFilePath = Join-Path $ResolvedPath "audit_log.txt"
    Write-Host "`nAudit report will be saved to: $LogFilePath" -ForegroundColor DarkCyan

    # Clear any old log file
    if (Test-Path $LogFilePath) { Remove-Item $LogFilePath -Force }

    Write-Host "`n######################################################" -ForegroundColor Cyan
    Write-Host "### Running Experiment Audit                     ###" -ForegroundColor Cyan
    Write-Host "######################################################`n" -ForegroundColor Cyan

    Write-Host "Executing: $executable $($finalArgs -join ' ')"

    # Execute the command and redirect all output (stdout and stderr) to the log file.
    # This ensures $LASTEXITCODE accurately reflects the Python script's exit code.
    & $executable $finalArgs *>&1 | Out-File -FilePath $LogFilePath -Encoding UTF8

    # Get the exit code from the Python script
    $pythonExitCode = $LASTEXITCODE

    # Display the captured output from the log file to the console
    Get-Content -Path $LogFilePath | ForEach-Object { Write-Host $_ }

    # Interpret the audit result and provide appropriate final messaging
    switch ($pythonExitCode) {
        $AUDIT_ALL_VALID {
            Write-Host "`n######################################################" -ForegroundColor Green
            Write-Host "### Audit Finished: Experiment is VALIDATED.     ###" -ForegroundColor Green
            Write-Host "######################################################`n" -ForegroundColor Green
            exit 0
        }
        $AUDIT_NEEDS_REPROCESS {
            Write-Host "`n######################################################" -ForegroundColor Yellow
            Write-Host "### Audit Finished: Experiment needs UPDATE.     ###" -ForegroundColor Yellow
            Write-Host "### Recommendation: Run 'update_experiment.ps1' to ###" -ForegroundColor Yellow
            Write-Host "### reprocess analysis and summaries.            ###" -ForegroundColor Yellow
            Write-Host "######################################################`n" -ForegroundColor Yellow
            exit 0 # It's a non-fatal audit result, so exit 0 for the audit script itself
        }
        $AUDIT_NEEDS_REPAIR {
            Write-Host "`n######################################################" -ForegroundColor Red
            Write-Host "### Audit Finished: Experiment needs REPAIR.     ###" -ForegroundColor Red
            Write-Host "### Recommendation: Run 'run_experiment.ps1' to    ###" -ForegroundColor Red
            Write-Host "### automatically fix critical issues.           ###" -ForegroundColor Red
            Write-Host "######################################################`n" -ForegroundColor Red
            exit 0 # It's a non-fatal audit result, so exit 0 for the audit script itself
        }
        $AUDIT_NEEDS_MIGRATION {
            Write-Host "`n######################################################" -ForegroundColor Red
            Write-Host "### Audit Finished: Experiment needs MIGRATION.  ###" -ForegroundColor Red
            Write-Host "### Recommendation: Run 'migrate_experiment.ps1' to ###" -ForegroundColor Red
            Write-Host "### convert the legacy format.                   ###" -ForegroundColor Red
            Write-Host "######################################################`n" -ForegroundColor Red
            exit 0 # It's a non-fatal audit result, so exit 0 for the audit script itself
        }
        $AUDIT_ABORTED_BY_USER {
            Write-Host "`n######################################################" -ForegroundColor Yellow
            Write-Host "### Audit Process Aborted by User.               ###" -ForegroundColor Yellow
            Write-Host "######################################################`n" -ForegroundColor Yellow
            exit 0 # User aborted Python script, which is a graceful exit for the wrapper
        }
        default {
            # Any other non-zero exit code is a true error for the audit process
            Write-Host "`n######################################################" -ForegroundColor Red
            Write-Host "### AUDIT FAILED ###" -ForegroundColor Red
            Write-Host "######################################################`n" -ForegroundColor Red
            Write-Error "Unknown or unexpected exit code from experiment_manager.py: ${pythonExitCode}."
            Format-LogFile -Path $LogFilePath
            exit 1
        }
    }
    Format-LogFile -Path $LogFilePath

    # Add a final blank line for clean separation from the next PS prompt.
    Write-Host ""
}
catch {
    Write-Host "`n######################################################" -ForegroundColor Red
    Write-Host "### AUDIT FAILED ###" -ForegroundColor Red
    Write-Host "######################################################`n" -ForegroundColor Red
    Write-Error $_.Exception.Message
    Format-LogFile -Path $LogFilePath
    
    # Add a final blank line for clean separation from the next PS prompt.
    Write-Host ""
    exit 1
}

# === End of audit_experiment.ps1 ===
