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
# Filename: migrate_experiment.ps1

<#
.SYNOPSIS
    Upgrades a legacy or severely corrupted experiment via a safe, non-destructive copy.

.DESCRIPTION
    This is a powerful safety utility for handling legacy or corrupted experiments.
    It performs a non-destructive migration by creating a clean, timestamped copy
    of the target experiment and running the full upgrade and validation process
    on that new copy.

    The original data is always left untouched. The script provides a clear,
    context-aware prompt that explains the safety of the process and accurately
    describes when API calls might be necessary to repair missing data.

.PARAMETER TargetDirectory
    The path to the experiment directory that will be targeted for migration.
    This original directory will be copied, not modified.

.EXAMPLE
    # Copy and migrate "Legacy_Experiment_1"
    # This creates a folder like "output/migrated_experiments/Legacy_Experiment_1_migrated_20250712_103000"
    .\migrate_experiment.ps1 -TargetDirectory "output/legacy/Legacy_Experiment_1"
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the experiment directory to migrate.")]
    [string]$TargetDirectory,

    [Parameter(Mandatory = $false, HelpMessage = "Specifies a custom parent directory for the migrated experiment.")]
    [string]$DestinationParent,

    [Parameter(Mandatory = $false, HelpMessage = "Run in non-interactive mode, suppressing user prompts for confirmation.")]
    [switch]$NonInteractive,

    [Parameter(Mandatory=$false, HelpMessage="Suppresses the initial PDM detection message.")]
    [switch]$NoHeader
)

# --- Helper function to create standardized headers ---
function Write-Header {
    param(
        [string[]]$Lines,
        [string]$Color = "White",
        [int]$Width = 80
    )
    $separator = "#" * $Width
    Write-Host "`n$separator" -ForegroundColor $Color
    foreach ($line in $Lines) {
        # Check if the line is too long to be padded.
        if ($line.Length -gt ($Width - 8)) { # Use 8 to give a little buffer
            # If too long, print it plainly without attempting to center.
            Write-Host "### $($line) " -ForegroundColor $Color
        } else {
            # Otherwise, use the original centering logic.
            $paddingLength = $Width - $line.Length - 6 # 3 for '###', 3 for '###'
            $leftPad = [math]::Floor($paddingLength / 2)
            $rightPad = [math]::Ceiling($paddingLength / 2)
            $formattedLine = "###" + (" " * $leftPad) + $line + (" " * $rightPad) + "###"
            Write-Host $formattedLine -ForegroundColor $Color
        }
    }
    Write-Host $separator -ForegroundColor $Color
    Write-Host "" # Add a blank line after the header
}

function Run-Manager ($managerArgs, $executable, $prefixArgs, $C_RED, $C_RESET) {
    $managerScript = "src/experiment_manager.py"
    
    # Construct the arguments for the final command
    $command_executable = $executable
    $command_args = $prefixArgs + $managerScript + $managerArgs

    # If using PDM, the executable is 'pdm' and the arguments start with 'run python'
    if ($usingPdm) {
        $command_executable = "pdm"
    }
    
    # Use absolute paths in the system temp directory for robust streaming
    $tempStdout = Join-Path $env:TEMP "mig_stdout_$(Get-Random).log"
    $tempStderr = Join-Path $env:TEMP "mig_stderr_$(Get-Random).log"

    $proc = Start-Process -FilePath $command_executable -ArgumentList $command_args -NoNewWindow -PassThru -RedirectStandardOutput $tempStdout -RedirectStandardError $tempStderr
    
    Start-Sleep -Milliseconds 200 # Wait for process to start and lock file
    
    # Monitor using a FileStream with ReadWrite sharing to avoid locks.
    $fileStream = New-Object System.IO.FileStream($tempStdout, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    $reader = New-Object System.IO.StreamReader($fileStream)
    while (-not $proc.HasExited) {
        while ($line = $reader.ReadLine()) { Write-Host $line }
        Start-Sleep -Milliseconds 100
    }
    while ($line = $reader.ReadLine()) { Write-Host $line }
    $reader.Close(); $fileStream.Close(); $reader.Dispose(); $fileStream.Dispose()

    $managerExitCode = $proc.ExitCode
    $stderrContent = Get-Content $tempStderr -Raw
    
    Remove-Item $tempStdout, $tempStderr -ErrorAction SilentlyContinue

    if ($managerExitCode -ne 0) {
        Write-Host "`n$($C_RED)Experiment Manager failed with exit code $managerExitCode.$($C_RESET)"
        if ($stderrContent) {
            Write-Host "$($C_RED)Error Details:`n$stderrContent$($C_RESET)"
        }
    }
    return $managerExitCode
}

# --- Auto-detect execution environment ---
$executable = "python"
$prefixArgs = @()
$usingPdm = $false
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    $usingPdm = $true
    if (-not $NoHeader.IsPresent) { Write-Host "`nPDM detected. Using 'pdm run' to execute Python scripts." -ForegroundColor Cyan }
    $executable = "pdm"
    $prefixArgs = "run", "python"
}
else {
    if (-not $NoHeader.IsPresent) { Write-Host "PDM not detected. Using standard 'python' command." -ForegroundColor Yellow }
}

# --- Shared Variables ---
$C_CYAN = "`e[96m"; $C_GREEN = "`e[92m"; $C_YELLOW = "`e[93m"; $C_RED = "`e[91m"; $C_RESET = "`e[0m"

# --- Define Audit Exit Codes from experiment_manager.py ---
# These are mapped from the Python script for clarity and robustness.
$AUDIT_ALL_VALID       = 0 # Experiment is complete and valid.
$AUDIT_NEEDS_REPROCESS = 1 # Experiment needs reprocessing (e.g., analysis issues).
$AUDIT_NEEDS_REPAIR    = 2 # Experiment needs repair (e.g., missing responses, critical files).
$AUDIT_NEEDS_MIGRATION = 3 # Experiment is legacy or malformed, requires full migration.
$AUDIT_NEEDS_AGGREGATION = 4 # Replications valid, but experiment-level summary is missing.
$AUDIT_ABORTED_BY_USER = 99 # Specific exit code when user aborts via prompt in experiment_manager.py

# --- Main Script Logic ---
$logFilePath = $null # Initialize here so it's available in the 'finally' block

try {
    # 1. Validate input path
    $TargetDirectory = $TargetDirectory.Trim()
    if (-not (Test-Path $TargetDirectory -PathType Container)) {
        throw "The specified TargetDirectory '$TargetDirectory' does not exist as a directory relative to the current location: '$(Get-Location)'"
    }
    $TargetPath = Resolve-Path -Path $TargetDirectory -ErrorAction Stop

    # 2. Setup destination and logging BEFORE any action
    $TargetBaseName = (Get-Item -Path $TargetPath).Name
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $NewFolderName = "${TargetBaseName}_migrated_${Timestamp}"
    $DestinationParent = "output/migrated_experiments"
    if ($PSBoundParameters.ContainsKey('DestinationParent')) { $DestinationParent = $PSBoundParameters['DestinationParent'] }
    $DestinationPath = Join-Path -Path $DestinationParent -ChildPath $NewFolderName
    if (-not (Test-Path -Path $DestinationParent)) { New-Item -ItemType Directory -Path $DestinationParent -Force | Out-Null }
    $logFileName = "experiment_migration_log.txt"
    $logFilePath = Join-Path $DestinationPath $logFileName
    
    Write-Host "" # Add blank line for spacing
    Write-Host "The migration log will be saved to:" -ForegroundColor Gray
    $relativeLogPath = (Join-Path $DestinationParent $NewFolderName $logFileName).Replace("\", "/")
    Write-Host "$relativeLogPath`n" -ForegroundColor Gray
    Start-Transcript -Path $logFilePath -Force | Out-Null

    # 3. Run the audit, capturing its output to be logged by the transcript
    $auditorScriptName = "src/experiment_auditor.py"
    $managerScriptName = "src/experiment_manager.py"
    $auditArgs = $TargetPath, "--force-color"
    Write-Host "Auditing..." -ForegroundColor DarkGray
    $auditOutput = & $executable $prefixArgs $auditorScriptName $auditArgs 2>&1
    $auditOutput | Out-Host
    $pythonExitCode = $LASTEXITCODE

    # 4. Prompt for confirmation if needed
    if (-not $NonInteractive.IsPresent) {
        # Standard confirmation function
        function Confirm-Proceed {
            param([string]$Message)
            $promptText = "$Message (Y/N)"
            while ($true) {
                $choice = Read-Host -Prompt $promptText
                if ($choice.Trim().ToLower() -eq 'y') { return $true }
                if ($choice.Trim().ToLower() -eq 'n') { return $false }
            }
        }
        
        # Present the correct prompt based on the audit result
        $proceed = $false
        switch ($pythonExitCode) {
            $AUDIT_NEEDS_MIGRATION {
                $promptMessage = @"

This experiment is in a legacy format and requires migration to align it with current data formats.
This is a safe, non-destructive process:
  - Your original data at '$((Resolve-Path $TargetPath -Relative).TrimStart(".\"))' will NOT be modified.
  - A clean, upgraded copy of the experiment will be created.
  - API calls will ONLY be made to repair any missing LLM responses found in the original data.

Do you wish to proceed?
"@
                $proceed = Confirm-Proceed -Message $promptMessage
            }
            default { # Handles VALIDATED, NEEDS_REPAIR, etc.
                $promptMessage = @"

This experiment does not require migration.
Regardless, you may choose to go ahead with it. This is a safe, non-destructive process:
  - Your original data at '$((Resolve-Path $TargetPath -Relative).TrimStart(".\"))' will NOT be modified.
  - A clean, upgraded copy of the experiment will be created.
  - API calls will ONLY be made to repair any missing LLM responses found in the original data.

Do you wish to proceed with this full copy-and-upgrade?
"@
                $proceed = Confirm-Proceed -Message $promptMessage
            }
        }

        if (-not $proceed) {
            Write-Host "`nMigration aborted by user.`n" -ForegroundColor Yellow
            return
        }
    }

    # 5. Perform the migration
    Write-Header -Lines "Step 1/2: Copying Experiment Data" -Color Cyan
    Write-Host "Source:      $((Resolve-Path $TargetPath -Relative).TrimStart(".\"))"
    Write-Host "Destination: $DestinationPath"
    New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null
    Copy-Item -Path (Join-Path $TargetPath "*") -Destination $DestinationPath -Recurse -Force
    Write-Host "`nCopy complete."

    Write-Header -Lines "Step 2/2: Upgrading New Experiment Copy" -Color Cyan
    $migrateArgs = @($DestinationPath, "--migrate", "--force-color")
    $managerExitCode = Run-Manager -managerArgs $migrateArgs -executable $executable -prefixArgs $prefixArgs -C_RED $C_RED -C_RESET $C_RESET
    if ($managerExitCode -ne 0) { throw "ERROR: Migration process failed with exit code ${managerExitCode}." }

    # 6. Final validation audit
    $finalAuditArgs = $DestinationPath, "--force-color"
    $finalAuditOutput = & $executable $prefixArgs $auditorScriptName $finalAuditArgs 2>&1
    $finalAuditOutput | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "VALIDATION FAILED! The final result is not valid." }

    Write-Host "`nMigration process complete. Migrated data is in: '$((Resolve-Path $DestinationPath -Relative).TrimStart(".\"))'`n" -ForegroundColor Green
}
catch {
    Write-Header -Lines "MIGRATION FAILED" -Color Red
    $errorMessage = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { $_ }
    Write-Host $errorMessage -ForegroundColor Red
    exit 1
}
finally {
    if ($logFilePath -and (Get-Command "Stop-Transcript" -ErrorAction SilentlyContinue)) {
        Stop-Transcript | Out-Null
        try {
            if (Test-Path -LiteralPath $logFilePath) {
                $logContent = Get-Content -Path $logFilePath -Raw
                # Clean transcript header/footer and ANSI codes
                $cleanedContent = $logContent -replace '(?s)\*+\r?\nPowerShell transcript start.*?\*+\r?\n\r?\n', ''
                $cleanedContent = $cleanedContent -replace '(?s)\*+\r?\nPowerShell transcript end.*', ''
                $cleanedContent = $cleanedContent -replace "`e\[[0-9;]*m", ''
                Set-Content -Path $logFilePath -Value $cleanedContent.Trim() -Force
            }
        } catch { Write-Warning "Could not clean the transcript log file: $($_.Exception.Message)" }

        if (Test-Path -LiteralPath $logFilePath) {
            Write-Host "`nThe migration log has been saved at:" -ForegroundColor Gray
            $relativePath = Resolve-Path -Path $logFilePath -Relative
            Write-Host $relativePath; Write-Host ""
        }
    }
}

# === End of migrate_experiment.ps1 ===
