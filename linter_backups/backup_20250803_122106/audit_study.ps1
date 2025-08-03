#!/usr/bin/env pwsh
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
    final analysis via 'process_study.ps1'.

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
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the target directory containing one or more experiments.")]
    [string]$TargetDirectory,

    [Parameter(Mandatory=$false)]
    [switch]$NoLog
)

# --- Auto-detect execution environment ---
$executable = "python"
$prefixArgs = @()
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    $executable = "pdm"
    $prefixArgs = "run", "python"
}

# --- Define ANSI Color Codes for Rich Text Output ---
$c = [char]27 # ANSI Escape Character
$c_reset = "$c[0m"
$c_green = "$c[92m"
$c_yellow = "$c[93m"
$c_red = "$c[91m"
$c_cyan = "$c[96m"

# --- Define Audit Exit Codes from experiment_manager.py ---
$AUDIT_ALL_VALID       = 0 # Experiment is complete and valid.
$AUDIT_NEEDS_REPROCESS = 1 # Experiment needs reprocessing (e.g., analysis issues).
$AUDIT_NEEDS_REPAIR    = 2 # Experiment needs repair (e.g., missing responses, critical files).
$AUDIT_NEEDS_MIGRATION = 3 # Experiment is legacy or malformed, requires full migration.
$AUDIT_NEEDS_AGGREGATION = 4 # Replications are valid, but experiment summary is not
$AUDIT_ABORTED_BY_USER = 99 # Specific exit code when user aborts via prompt in experiment_manager.py

# --- Helper function for consistent header formatting ---
function Format-HeaderLine {
    param(
        [string]$Message,
        [int]$TotalWidth = 80
    )
    $prefix = "###"
    $suffix = "###"
    $contentWidth = $TotalWidth - $prefix.Length - $suffix.Length
    $paddedMessage = " $Message "

    if ($paddedMessage.Length -ge $contentWidth) {
        return "$prefix$paddedMessage$suffix"
    }

    $paddingTotal = $contentWidth - $paddedMessage.Length
    $paddingLeft = [Math]::Floor($paddingTotal / 2)
    $paddingRight = $paddingTotal - $paddingLeft

    $content = (" " * $paddingLeft) + $paddedMessage + (" " * $paddingRight)
    
    return "$prefix$content$suffix"
}

# --- Main Script Logic ---
$scriptExitCode = 0

if (-not $NoLog.IsPresent) {
    $LogFilePath = Join-Path -Path $TargetDirectory -ChildPath "study_audit_log.txt"
    Start-Transcript -Path $LogFilePath -Force | Out-Null
    
    Write-Host "" # Blank line before message
    Write-Host "The audit log will be saved to:" -ForegroundColor Gray
    $relativePath = Resolve-Path -Path $LogFilePath -Relative
    Write-Host $relativePath -ForegroundColor Gray
}

try {
    $ResolvedPath = Resolve-Path -Path $TargetDirectory -ErrorAction Stop

    $scriptName = "src/experiment_manager.py"
    $auditResults = @()
    $overallStatus = $AUDIT_ALL_VALID
    $headerLine = "#" * 80

    Write-Host "`n$headerLine" -ForegroundColor Cyan
    Write-Host (Format-HeaderLine "RUNNING STUDY AUDIT") -ForegroundColor Cyan
    Write-Host "$headerLine`n" -ForegroundColor Cyan
    Write-Host "Auditing Study Directory:"
    $relativePathForDisplay = Resolve-Path -Path $TargetDirectory -Relative
    Write-Host "$relativePathForDisplay`n"

    # Find all subdirectories, excluding known output folders like 'anova'.
    $experimentDirs = Get-ChildItem -Path $ResolvedPath -Directory | Where-Object { $_.Name -ne 'anova' }

    if ($experimentDirs.Count -eq 0) {
        Write-Host "No experiment directories found in '$ResolvedPath'." -ForegroundColor Yellow
        return
    }

    # --- Print Real-time Audit Table Header ---
    Write-Host ""
    $progressWidth = 10
    $experimentNameCap = 40 # Set a reasonable maximum width for names
    Write-Host ("{0,-$progressWidth} {1,-$experimentNameCap} {2}" -f "Progress", "Experiment", "Result")
    Write-Host ("-" * $progressWidth + " " + "-" * $experimentNameCap + " " + "-" * 8)

    $i = 0
    foreach ($dir in $experimentDirs) {
        $i++
        $arguments = @("--verify-only", $dir.FullName, "--force-color")
        $output = @()
        
        if ($PSBoundParameters['Verbose']) {
            Write-Host "`n--- Auditing Experiment $($i)/$($experimentDirs.Count) (Verbose): $($dir.Name) ---" -ForegroundColor Yellow
            $finalArgs = $prefixArgs + $scriptName + $arguments
            & $executable @finalArgs 2>&1
            $exitCode = $LASTEXITCODE
            Write-Host "--- End of Audit for: $($dir.Name) ---" -ForegroundColor Yellow
        }
        else {
            $progress = "$i/$($experimentDirs.Count)"
            $displayName = $dir.Name
            if ($displayName.Length -gt $experimentNameCap) {
                $displayName = $displayName.Substring(0, $experimentNameCap - 3) + "..."
            }
            Write-Host ("{0,-$progressWidth} {1,-$experimentNameCap} " -f $progress, $displayName) -NoNewline
            $finalArgs = $prefixArgs + $scriptName + $arguments
            & $executable @finalArgs 2>&1 | Out-Null # Suppress Python output in non-verbose
            $exitCode = $LASTEXITCODE
        }

        # --- Status Logic based on the now-reliable exit code ---
        $trueStatus, $progressColor = switch ($exitCode) {
            $AUDIT_ALL_VALID         { "VALIDATED", "Green"; break }
            $AUDIT_NEEDS_REPROCESS   { "NEEDS UPDATE", "Yellow"; break }
            $AUDIT_NEEDS_REPAIR      { "NEEDS REPAIR", "Red"; break }
            $AUDIT_NEEDS_MIGRATION   { "NEEDS MIGRATION", "Red"; break }
            $AUDIT_NEEDS_AGGREGATION { "NEEDS FINALIZATION", "Yellow"; break }
            default                  { "ERROR", "Red"; break }
        }
        if (-not $PSBoundParameters['Verbose']) {
            $progressText = if ($progressColor -eq "Green") { "[ OK ]" } else { "[ FAIL ]" }
            Write-Host $progressText -ForegroundColor $progressColor
        }

        $auditResults += [PSCustomObject]@{ Name = $dir.Name; ExitCode = $exitCode; TrueStatus = $trueStatus }

        if ($exitCode -gt $overallStatus -and $exitCode -ne $AUDIT_ABORTED_BY_USER) {
            $overallStatus = $exitCode
        }
    }

    # --- Print Summary Report ---
    Write-Output ""
    Write-Output "$c_cyan`n$headerLine$c_reset"
    Write-Output "$c_cyan$(Format-HeaderLine "STUDY AUDIT SUMMARY REPORT")$c_reset"
    Write-Output "$c_cyan$headerLine`n$c_reset"
    
    # Use a fixed width for the experiment name column to match the real-time table
    $maxNameLength = 40
    $statusWidth = 20
    $gap = "   "

    # Create header as a single string
    $headerString = ("{0,-$maxNameLength}" -f "Experiment") + $gap + ("{0,-$statusWidth}" -f "Status") + $gap + "Details"
    Write-Output $headerString
    # Create underline as a single string
    $underlineString = ("-" * $maxNameLength) + $gap + ("-" * $statusWidth) + $gap + ("-" * "Details".Length)
    Write-Output $underlineString

    foreach ($result in $auditResults) {
        $statusText, $details, $colorCode = switch ($result.TrueStatus) {
            "VALIDATED"          { "VALIDATED", "Ready for processing.", $c_green; break }
            "NEEDS UPDATE"       { "NEEDS UPDATE", "Run 'repair_experiment.ps1' to update.", $c_yellow; break }
            "NEEDS REPAIR"       { "NEEDS REPAIR", "Run 'repair_experiment.ps1' to fix.", $c_red; break }
            "NEEDS MIGRATION"    { "NEEDS MIGRATION", "Run 'migrate_experiment.ps1' to upgrade.", $c_red; break }
            "NEEDS FINALIZATION" { "NEEDS FINALIZATION", "Run 'repair_experiment.ps1' to finalize.", $c_yellow; break }
            default              { "UNKNOWN", "Manual investigation required.", $c_red; break }
        }
        
        $displayName = $result.Name
        if ($displayName.Length -gt $maxNameLength) {
            $displayName = $displayName.Substring(0, $maxNameLength - 3) + "..."
        }
        
        $statusPart = "$colorCode{0,-$statusWidth}$c_reset" -f $statusText
        $line = ("{0,-$maxNameLength}" -f $displayName) + $gap + $statusPart + $gap + $details
        Write-Output $line
    }

    # --- Final Conclusion ---
    # Part 1: Check if all individual experiments are validated and ready.
    $isStudyReadyForProcessing = ($auditResults | Where-Object { $_.TrueStatus -ne "VALIDATED" }).Count -eq 0

    # Part 2: Check for the final study-level artifacts.
    $studyCsvExists = Test-Path (Join-Path $ResolvedPath "STUDY_results.csv")
    $boxplotsDirExists = Test-Path (Join-Path $ResolvedPath "anova/boxplots")
    $diagnosticsDirExists = Test-Path (Join-Path $ResolvedPath "anova/diagnostics")
    $isStudyComplete = $isStudyReadyForProcessing -and $studyCsvExists -and $boxplotsDirExists -and $diagnosticsDirExists

    # If the study is ready for processing, show the completeness audit table.
    if ($isStudyReadyForProcessing) {
        $completenessChecks = @(
            @{ Name = "STUDY_results.csv"; Found = $studyCsvExists },
            @{ Name = "anova/boxplots/ directory"; Found = $boxplotsDirExists },
            @{ Name = "anova/diagnostics/ directory"; Found = $diagnosticsDirExists }
        )

        Write-Output "$c_cyan`n$headerLine$c_reset"
        Write-Output "$c_cyan$(Format-HeaderLine "STUDY COMPLETENESS AUDIT")$c_reset"
        Write-Output "$c_cyan$headerLine`n$c_reset"

        $artifactNameWidth = 40
        $statusWidth = 10
        $completenessHeader = ("{0,-$artifactNameWidth}" -f "Artifact") + $gap + "Status"
        Write-Output $completenessHeader
        $completenessUnderline = ("-" * $artifactNameWidth) + $gap + ("-" * "Status".Length)
        Write-Output $completenessUnderline

        foreach ($check in $completenessChecks) {
            $statusText = if ($check.Found) { "[  OK  ]" } else { "[ FAIL ]" }
            $statusColor = if ($check.Found) { $c_green } else { $c_red }
            $statusPart = "$statusColor{0,-$statusWidth}$c_reset" -f $statusText
            $line = ("{0,-$artifactNameWidth}" -f $check.Name) + $gap + $statusPart
            Write-Output $line
        }
    }
    
    if ($isStudyComplete) {
        # Case 1: All experiments are valid AND the final study artifacts exist.
        Write-Output "$c_green`n$headerLine$c_reset"
        Write-Output "$c_green$(Format-HeaderLine "AUDIT FINISHED: STUDY IS COMPLETE")$c_reset"
        Write-Output "$c_green$(Format-HeaderLine "Recommendation: No further action is required.")$c_reset"
        Write-Output "$c_green$headerLine`n$c_reset"
    }
    elseif ($isStudyReadyForProcessing) {
        # Case 2: All experiments are valid BUT the final study artifacts are missing.
        Write-Output "$c_green`n$headerLine$c_reset"
        Write-Output "$c_green$(Format-HeaderLine "AUDIT FINISHED: STUDY IS VALIDATED")$c_reset"
        Write-Output "$c_green$(Format-HeaderLine "Recommendation: Run 'process_study.ps1' to")$c_reset"
        Write-Output "$c_green$(Format-HeaderLine "complete the final analysis.")$c_reset"
        Write-Output "$c_green$headerLine`n$c_reset"
    }
    else {
        # Case 3: One or more experiments are not ready (need repair, migration, etc.).
        Write-Output "$c_red`n$headerLine$c_reset"
        Write-Output "$c_red$(Format-HeaderLine "AUDIT FINISHED: STUDY IS NOT READY")$c_reset"
        Write-Output "$c_red$(Format-HeaderLine "Recommendation: Address issues listed above.")$c_reset"
        Write-Output "$c_red$headerLine`n$c_reset"
    }
    
    # Set the exit code for the script based on the audit result.
    $scriptExitCode = $overallStatus
}
catch {
    $headerLine = "#" * 80
    Write-Host "`n$headerLine" -ForegroundColor Red
    Write-Host (Format-HeaderLine "STUDY AUDIT FAILED") -ForegroundColor Red
    Write-Host "$headerLine`n" -ForegroundColor Red
    Write-Host "ERROR: $($_.Exception.Message)`n" -ForegroundColor Red
    
    $scriptExitCode = 1
}
finally {
    # Only stop the transcript and clean the log if this script was the one that started it.
    if (-not $NoLog.IsPresent -and (Test-Path -LiteralPath $LogFilePath)) {
        Stop-Transcript | Out-Null
        
        # Post-process the log file to remove the default transcript header and footer.
        try {
            $logContent = Get-Content -Path $LogFilePath -Raw
            # Regex to find and remove the header block
            $cleanedContent = $logContent -replace '(?s)\*+\r?\nPowerShell transcript start.*?\*+\r?\n\r?\n', ''
            # Regex to find and remove the footer block
            $cleanedContent = $cleanedContent -replace '(?s)\*+\r?\nPowerShell transcript end.*', ''
            # Overwrite the file with the cleaned content
            Set-Content -Path $LogFilePath -Value $cleanedContent.Trim() -Force
        }
        catch {
            # If cleanup fails, the original log is preserved.
            Write-Warning "Could not clean the transcript log file: $($_.Exception.Message)"
        }

        Write-Host "`nThe audit log has been saved to:" -ForegroundColor Gray
        $relativePath = Resolve-Path -Path $LogFilePath -Relative
        Write-Host $relativePath -ForegroundColor Gray
        Write-Host "" # Add a blank line for spacing
    }
}

# Exit with the overall status code. 0 means VALIDATED, non-zero means NOT READY.
exit $scriptExitCode

# === End of audit_study.ps1 ===