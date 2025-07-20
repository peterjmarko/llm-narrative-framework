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
# Filename: audit_study.ps1

<#
.SYNOPSIS
    Audits all experiments within a study directory to check for analysis readiness.

.DESCRIPTION
    This script iterates through all subdirectories of a given study folder, treating each
    as an individual experiment. It runs a read-only audit on each one and presents a
    consolidated summary report. This helps determine if the entire study is ready for
    final analysis via 'analyze_study.ps1'.

.PARAMETER StudyDirectory
    The path to the study directory containing multiple experiment folders.

.PARAMETER Verbose
    If specified, displays the full, detailed audit report for each individual experiment.
    By default, only a summary table is shown.

.EXAMPLE
    # Run a summary audit on a study.
    .\audit_study.ps1 -StudyDirectory "output/studies/My_First_Study"

.EXAMPLE
    # Run a detailed audit, showing the full report for each experiment.
    .\audit_study.ps1 -StudyDirectory "output/studies/My_First_Study" -Verbose
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the study directory to audit.")]
    [string]$StudyDirectory
)

# --- Auto-detect execution environment ---
$executable = "python"
$prefixArgs = @()
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    $executable = "pdm"
    $prefixArgs = "run", "python"
}

# --- Define Audit Exit Codes from experiment_manager.py ---
$AUDIT_ALL_VALID       = 0 # Experiment is complete and valid.
$AUDIT_NEEDS_REPROCESS = 1 # Experiment needs reprocessing (e.g., analysis issues).
$AUDIT_NEEDS_REPAIR    = 2 # Experiment needs repair (e.g., missing responses, critical files).
$AUDIT_NEEDS_MIGRATION = 3 # Experiment is legacy or malformed, requires full migration.
$AUDIT_ABORTED_BY_USER = 99 # Specific exit code when user aborts via prompt in experiment_manager.py

# --- Helper function for consistent header formatting ---
function Format-HeaderLine {
    param(
        [string]$Message,
        [int]$TotalWidth = 54
    )
    $prefix = "###"
    $suffix = "###"
    $contentWidth = $TotalWidth - $prefix.Length - $suffix.Length
    $paddedMessage = " $Message "
    
    $paddingTotal = $contentWidth - $paddedMessage.Length
    if ($paddingTotal -lt 0) { $paddingTotal = 0 }

    $paddingLeft = [Math]::Floor($paddingTotal / 2)
    $paddingRight = $paddingTotal - $paddingLeft

    $content = (" " * $paddingLeft) + $paddedMessage + (" " * $paddingRight)
    
    # Ensure the content is exactly the right width if there's an off-by-one issue
    $content = $content.PadRight($contentWidth)

    return "$prefix$content$suffix"
}

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
try {
    $ResolvedPath = Resolve-Path -Path $StudyDirectory -ErrorAction Stop
    $LogFilePath = Join-Path $ResolvedPath "study_audit_log.txt"

    # Start a transcript to capture all console output to the log file.
    Start-Transcript -Path $LogFilePath -Force

    $scriptName = "src/experiment_manager.py"
    $auditResults = @()
    $overallStatus = $AUDIT_ALL_VALID
    $headerLine = "#" * 54

    Write-Host "`n$headerLine" -ForegroundColor Cyan
    Write-Host (Format-HeaderLine "RUNNING STUDY AUDIT") -ForegroundColor Cyan
    Write-Host "$headerLine`n" -ForegroundColor Cyan
    Write-Host "Auditing Study Directory: $ResolvedPath`n"
    Write-Host "Full audit log will be saved to: $LogFilePath`n"

    # Find all subdirectories, excluding known output folders like 'anova'.
    $experimentDirs = Get-ChildItem -Path $ResolvedPath -Directory | Where-Object { $_.Name -ne 'anova' }

    if ($experimentDirs.Count -eq 0) {
        Write-Host "No experiment directories found in '$ResolvedPath'." -ForegroundColor Yellow
        Stop-Transcript | Out-Null
        Format-LogFile -Path $LogFilePath
        Write-Host "`nTranscript stopped. Output has been saved in the log file:" -ForegroundColor DarkGray
        Write-Host $LogFilePath -ForegroundColor DarkGray
        exit 0
    }

    # --- Print Real-time Audit Table Header ---
    Write-Host ""
    $experimentNameCap = 60 # Set a reasonable maximum width for names
    Write-Host ("{0,-15} {1,-$experimentNameCap} {2}" -f "Progress", "Experiment", "Result")
    Write-Host ("-" * 15 + " " + "-" * $experimentNameCap + " " + "-" * 8)

    $i = 0
    foreach ($dir in $experimentDirs) {
        $i++
        $arguments = @("--verify-only", $dir.FullName, "--force-color")
        $output = @()
        $trueStatus = "UNKNOWN"
        
        if ($PSBoundParameters['Verbose']) {
            $arguments += "--verbose"
            Write-Host "`n--- Auditing Experiment $($i)/$($experimentDirs.Count) (Verbose): $($dir.Name) ---" -ForegroundColor Yellow
            $finalArgs = $prefixArgs + $scriptName + $arguments
            # In verbose mode, tee the output to both the console and a variable for parsing.
            $output = & $executable $finalArgs 2>&1 | Tee-Object -Variable capturedOutput | ForEach-Object { $_ }
            $exitCode = $LASTEXITCODE
            Write-Host "--- End of Audit for: $($dir.Name) ---" -ForegroundColor Yellow
        }
        else {
            $progress = "$i/$($experimentDirs.Count)"
            $displayName = $dir.Name
            if ($displayName.Length -gt $experimentNameCap) {
                $displayName = $displayName.Substring(0, $experimentNameCap - 3) + "..."
            }
            Write-Host ("{0,-15} {1,-$experimentNameCap} " -f $progress, $displayName) -NoNewline
            $finalArgs = $prefixArgs + $scriptName + $arguments
            $output = & $executable $finalArgs 2>&1
            $exitCode = $LASTEXITCODE
        }

        # --- Consistent Status Parsing Logic (for BOTH modes) ---
        $finalResultLine = $output | Select-String -Pattern "Audit Result:" | Select-Object -Last 1
        if ($finalResultLine) {
            $resultText = $finalResultLine.ToString()
            if ($resultText -match "PASSED. Experiment is complete and valid.") {
                $trueStatus = "VALIDATED"
                if (-not $PSBoundParameters['Verbose']) { Write-Host "[ OK ]" -ForegroundColor Green }
            } elseif ($resultText -match "PASSED. Experiment is ready for an update.") {
                $trueStatus = "NEEDS UPDATE"
                if (-not $PSBoundParameters['Verbose']) { Write-Host "[ FAIL ]" -ForegroundColor Red }
            } elseif ($resultText -match "FAILED. Critical data is missing or corrupt") {
                $trueStatus = "NEEDS REPAIR"
                if (-not $PSBoundParameters['Verbose']) { Write-Host "[ FAIL ]" -ForegroundColor Red }
            } elseif ($resultText -match "FAILED. Legacy or malformed runs detected.") {
                $trueStatus = "NEEDS MIGRATION"
                if (-not $PSBoundParameters['Verbose']) { Write-Host "[ FAIL ]" -ForegroundColor Red }
            }
        }
        
        if ($trueStatus -eq "UNKNOWN") {
             # If parsing fails, fall back to the exit code for a basic status.
             if ($exitCode -eq $AUDIT_ALL_VALID) {
                 $trueStatus = "VALIDATED"
                 if (-not $PSBoundParameters['Verbose']) { Write-Host "[ OK ]" -ForegroundColor Green }
             } else {
                 # A non-zero exit code with unknown text output defaults to a generic failure.
                 $trueStatus = "NEEDS REPAIR" # A safe default for a non-zero exit
                 if (-not $PSBoundParameters['Verbose']) { Write-Host "[ FAIL ]" -ForegroundColor Red }
             }
        }

        $auditResults += [PSCustomObject]@{ Name = $dir.Name; ExitCode = $exitCode; TrueStatus = $trueStatus }

        if ($exitCode -gt $overallStatus -and $exitCode -ne $AUDIT_ABORTED_BY_USER) {
            $overallStatus = $exitCode
        }
    }

    # --- Print Summary Report ---
    Write-Host ""
    Write-Host "`n$headerLine" -ForegroundColor Cyan
    Write-Host (Format-HeaderLine "STUDY AUDIT SUMMARY REPORT") -ForegroundColor Cyan
    Write-Host "$headerLine`n" -ForegroundColor Cyan
    
    # Set fixed widths for better alignment and to prevent wrapping.
    $maxNameLength = 45
    $statusWidth = 20
    $detailsWidth = 45
    $gap = "   "

    # Print header
    Write-Host ("{0,-$maxNameLength}" -f "Experiment") -NoNewline
    Write-Host ("$gap{0,-$statusWidth}" -f "Status") -NoNewline
    Write-Host ("$gap{0}" -f "Details")
    # Print underline
    Write-Host (("-" * $maxNameLength) + $gap + ("-" * $statusWidth) + $gap + ("-" * $detailsWidth))

    foreach ($result in $auditResults) {
        # Use the TrueStatus parsed from the output for the summary, ensuring consistency.
        $statusText, $details, $color = switch ($result.TrueStatus) {
            "VALIDATED"       { "VALIDATED", "Ready for analysis.", "Green"; break }
            "NEEDS UPDATE"    { "NEEDS UPDATE", "Requires update ('update_experiment.ps1').", "Yellow"; break }
            "NEEDS REPAIR"    { "NEEDS REPAIR", "Requires repair ('run_experiment.ps1').", "Red"; break }
            "NEEDS MIGRATION" { "NEEDS MIGRATION", "Requires migration ('migrate_experiment.ps1').", "Red"; break }
            default           { "UNKNOWN", "Manual investigation required.", "Red"; break }
        }
        $displayName = $result.Name
        if ($displayName.Length -gt $maxNameLength) {
            $displayName = $displayName.Substring(0, $maxNameLength - 3) + "..."
        }
        Write-Host ("{0,-$maxNameLength}" -f $displayName) -NoNewline
        Write-Host ("$gap{0,-$statusWidth}" -f $statusText) -ForegroundColor $color -NoNewline
        Write-Host ("$gap$details")
    }

    # --- Final Conclusion ---
    # The study is only considered valid if ALL experiments have a TrueStatus of "VALIDATED".
    $isStudyValidated = ($auditResults | Where-Object { $_.TrueStatus -ne "VALIDATED" }).Count -eq 0

    if ($isStudyValidated) {
        Write-Host "`n$headerLine" -ForegroundColor Green
        Write-Host (Format-HeaderLine "AUDIT FINISHED: STUDY IS VALIDATED") -ForegroundColor Green
        Write-Host (Format-HeaderLine "Recommendation: Run 'analyze_study.ps1' to") -ForegroundColor Green
        Write-Host (Format-HeaderLine "complete the final analysis.") -ForegroundColor Green
        Write-Host "$headerLine`n" -ForegroundColor Green
    }
    else {
        Write-Host "`n$headerLine" -ForegroundColor Red
        Write-Host (Format-HeaderLine "AUDIT FINISHED: STUDY IS NOT READY") -ForegroundColor Red
        Write-Host (Format-HeaderLine "Recommendation: Address issues listed above.") -ForegroundColor Red
        Write-Host "$headerLine`n" -ForegroundColor Red
    }
    
    Stop-Transcript | Out-Null
    Format-LogFile -Path $LogFilePath
    Write-Host "`nTranscript stopped. Output has been saved in the log file:" -ForegroundColor DarkGray
    Write-Host $LogFilePath -ForegroundColor DarkGray
    # Exit with the overall status code. 0 means VALIDATED, non-zero means NOT READY.
    exit $overallStatus
}
catch {
    $headerLine = "#" * 54
    Write-Host "`n$headerLine" -ForegroundColor Red
    Write-Host (Format-HeaderLine "STUDY AUDIT FAILED") -ForegroundColor Red
    Write-Host "$headerLine`n" -ForegroundColor Red
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    
    # Only stop the transcript and format the log if it was actually started.
    # The global $transcript variable is non-null if transcription is active.
    if ($transcript) {
        Stop-Transcript | Out-Null
        Format-LogFile -Path $LogFilePath
        Write-Host "`nTranscript stopped. Output has been saved in the log file:" -ForegroundColor DarkGray
        Write-Host $LogFilePath -ForegroundColor DarkGray
    }
    exit 1
}