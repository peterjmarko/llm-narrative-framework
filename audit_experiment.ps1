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
    experiment. It performs a comprehensive, read-only audit and prints a
    detailed report, including a final recommendation for the next appropriate
    action (e.g., 'repair_experiment.ps1' or 'migrate_experiment.ps1').

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

# --- Main Script Logic ---
$scriptExitCode = 0
try {
    # Clean and validate the input path to prevent errors from hidden characters or typos.
    $TargetDirectory = $TargetDirectory.Trim()
    if (-not (Test-Path $TargetDirectory -PathType Container)) {
        throw "The specified TargetDirectory '$TargetDirectory' does not exist as a directory relative to the current location: '$(Get-Location)'"
    }
    $ResolvedPath = Resolve-Path -Path $TargetDirectory -ErrorAction Stop

    $scriptName = "src/experiment_manager.py"
    # Build the argument list for the python script itself.
    $pythonScriptArgs = @($ResolvedPath, "--verify-only")
    if ($Verbose) {
        $pythonScriptArgs += "--verbose"
    }
    # Force the python script to generate color for stream processing
    $pythonScriptArgs += "--force-color"

    # Define the log file name
    $logFileName = "experiment_audit_log.txt"
    # Create the full, absolute path for file operations
    $LogFilePath = Join-Path $ResolvedPath $logFileName
    
    Write-Host "" # Add blank line for spacing
    Write-Host "The audit log will be saved to:"
    # Manually construct the relative path for display, since the file doesn't exist yet.
    # This uses the user-provided TargetDirectory, which is often already relative.
    $relativeLogPathForDisplay = Join-Path $TargetDirectory $logFileName
    Write-Host $relativeLogPathForDisplay
    
    if (Test-Path $LogFilePath) { Remove-Item $LogFilePath -Force }

    # Execute the python script, stream its output to both the console and the log file,
    # and capture the exit code.
    & $executable $prefixArgs $scriptName $pythonScriptArgs *>&1 | Tee-Object -FilePath $LogFilePath
    $pythonExitCode = $LASTEXITCODE

    Format-LogFile -Path $LogFilePath
    
    # The Python script handles all UI. This wrapper just passes the exit code through.
    $scriptExitCode = $pythonExitCode
}
catch {
    Write-Host "`n######################################################" -ForegroundColor Red
    Write-Host "### AUDIT FAILED ###" -ForegroundColor Red
    Write-Host "######################################################`n" -ForegroundColor Red
    Write-Error $_.Exception.Message
    # Only attempt to format the log if the path was successfully created and exists.
    if ($LogFilePath -and (Test-Path $LogFilePath)) {
        Format-LogFile -Path $LogFilePath
    }
    $scriptExitCode = 1
}
finally {
    if (Test-Path -LiteralPath $LogFilePath) {
        Write-Host "`nThe audit log has been saved to:" -ForegroundColor Gray
        $relativePath = Resolve-Path -Path $LogFilePath -Relative
        Write-Host $relativePath -ForegroundColor Gray
        Write-Host "" # Add a blank line for spacing
    }
}

exit $scriptExitCode
# === End of audit_experiment.ps1 ===
