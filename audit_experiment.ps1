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
    Provides a read-only, detailed completeness report for an existing experiment.

.DESCRIPTION
    This script is the primary diagnostic tool for CHECKING the status of any
    experiment. It calls the `experiment_auditor.py` backend to perform a
    comprehensive, read-only audit and prints a detailed report, including a
    final recommendation for the next appropriate action (e.g., 'repair_experiment.ps1'
    or 'migrate_experiment.ps1').

    It never makes any changes to the data. The full, detailed output is also
    saved to an 'experiment_audit_log.txt' file inside the target directory.

.PARAMETER TargetDirectory
    The path to the experiment directory to audit. This is a mandatory parameter.

.PARAMETER Verbose
    Enables verbose output from the verification process.

.EXAMPLE
    # Run a standard audit on an experiment.
    .\audit_experiment.ps1 -TargetDirectory "output/reports/My_Experiment"

.EXAMPLE
    # Run a detailed audit.
    .\audit_experiment.ps1 "output/reports/My_Experiment" -Verbose
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the experiment directory to audit.")]
    [string]$TargetDirectory
)

# --- Auto-detect execution environment ---
$executable = "python"
$prefixArgs = @()
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    $executable = "pdm"
    $prefixArgs = "run", "python"
}

# --- Main Script Logic ---
$scriptExitCode = 0
$LogFilePath = $null # Initialize to null

try {
    # Clean and validate the input path to prevent errors from hidden characters or typos.
    $TargetDirectory = $TargetDirectory.Trim()
    if (-not (Test-Path $TargetDirectory -PathType Container)) {
        throw "The specified TargetDirectory '$TargetDirectory' does not exist as a directory relative to the current location: '$(Get-Location)'"
    }
    $ResolvedPath = Resolve-Path -Path $TargetDirectory -ErrorAction Stop

    $scriptName = "src/experiment_auditor.py"
    # Build the argument list for the python script itself.
    $pythonScriptArgs = @($ResolvedPath)
    if ($PSBoundParameters['Verbose']) {
        $pythonScriptArgs += "--verbose"
    }
    # Force the python script to generate color for stream processing
    $pythonScriptArgs += "--force-color"

    # Define the log file name and path
    $logFileName = "experiment_audit_log.txt"
    $LogFilePath = Join-Path $ResolvedPath $logFileName
    
    Write-Host "" # Add blank line for spacing
    Write-Host "The audit log will be saved to:"
    $relativeLogPathForDisplay = Join-Path $TargetDirectory $logFileName
    Write-Host $relativeLogPathForDisplay
    
    # Remove the old log file if it exists to ensure a clean run
    if (Test-Path $LogFilePath) { Remove-Item $LogFilePath -Force }

    # Execute the python script, stream its output to both the console and the log file,
    # and capture the exit code. This is the correct method for this script.
    & $executable $prefixArgs $scriptName $pythonScriptArgs *>&1 | Tee-Object -FilePath $LogFilePath
    $pythonExitCode = $LASTEXITCODE

    # The Python script handles all UI. This wrapper just passes the exit code through.
    $scriptExitCode = $pythonExitCode
}
catch {
    Write-Host "`n######################################################" -ForegroundColor Red
    Write-Host "### AUDIT FAILED ###" -ForegroundColor Red
    Write-Host "######################################################`n" -ForegroundColor Red
    Write-Error $_.Exception.Message
    $scriptExitCode = 1
}
finally {
    if ($LogFilePath -and (Test-Path -LiteralPath $LogFilePath)) {
        # Post-process the log file to remove ANSI escape codes.
        try {
            $logContent = Get-Content -Path $LogFilePath -Raw
            # Regex to match and replace ANSI color codes. `e is the escape character.
            $cleanedContent = $logContent -replace "`e\[[0-9;]*m", ''
            Set-Content -Path $LogFilePath -Value $cleanedContent.Trim() -Force
        }
        catch {
            # If cleanup fails, do not crash the script. The original log is preserved.
            Write-Warning "Could not clean ANSI codes from the log file: $($_.Exception.Message)"
        }

        Write-Host "`nThe audit log has been saved to:" -ForegroundColor Gray
        $relativePath = Resolve-Path -Path $LogFilePath -Relative
        Write-Host $relativePath -ForegroundColor Gray
        Write-Host "" # Add a blank line for spacing
    }
}

exit $scriptExitCode

# === End of audit_experiment.ps1 ===
