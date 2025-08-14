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
# Filename: fix_experiment.ps1

<#
.SYNOPSIS
    Fixes or updates an existing experiment. It intelligently applies the safest,
    cheapest fix required.

.DESCRIPTION
    This is the main "fix-it" tool for any experiment. It automatically performs
    a full audit to diagnose the experiment's state and then applies the most
    appropriate action.

    - If it finds critical data issues (e.g., missing LLM responses), it performs
      a data-level REPAIR.
    - If it finds only outdated analysis files, it performs a safe, local
      analysis-only UPDATE.
    - If the experiment is already valid, it becomes interactive, allowing the user
      to force a specific action (e.g., a full data repair or analysis update).
    - If the experiment is found to be unfixable (i.e., requires migration), the
      script will halt with a clear message and recommendation.

.PARAMETER TargetDirectory
    (Required) The path to the existing experiment directory that needs to be
    fixed or updated.

.PARAMETER Notes
    A string of notes to embed in the reports and logs of any newly generated
    or repaired replications.

.PARAMETER StartRep
    For data repairs, the replication number to start from.

.PARAMETER EndRep
    For data repairs, the replication number to end at.

.PARAMETER Verbose
    A switch to enable detailed, real-time output from all underlying Python scripts.

.EXAMPLE
    # Automatically find and fix any issues in the specified experiment.
    .\repair_experiment.ps1 -TargetDirectory "output/studies/MyStudy/Exp1"

.EXAMPLE
    # Run on a valid experiment to bring up the interactive "force action" menu.
    .\repair_experiment.ps1 "output/studies/MyStudy/Exp1"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the experiment directory to repair or update.")]
    [ValidateScript({
        if (-not (Test-Path $_ -PathType Container)) {
            throw "The specified TargetDirectory does not exist or is not a directory: $_"
        }
        return $true
    })]
    [string]$TargetDirectory,

    [Parameter(Mandatory = $false)]
    [int]$StartRep,

    [Parameter(Mandatory = $false)]
    [int]$EndRep,

    [Parameter(Mandatory = $false)]
    [string]$Notes,

    [Parameter(Mandatory=$false)]
    [switch]$Force,

    [Parameter(Mandatory=$false, HelpMessage="Run in non-interactive mode, suppressing user prompts for confirmation.")]
    [switch]$NonInteractive,

    [Parameter(Mandatory=$false, HelpMessage="Non-interactively forces a full analysis update on a valid experiment.")]
    [switch]$ForceUpdate,
    
    [Parameter(Mandatory=$false, HelpMessage="Non-interactively forces re-aggregation on a valid experiment.")]
    [switch]$ForceAggregate,

    [Parameter(Mandatory=$false, HelpMessage="Suppresses the initial PDM detection message.")]
    [switch]$NoHeader
)

function Write-Header($message, $color, $C_RESET) {
    $line = '#' * 80
    $bookend = "###"
    $contentWidth = $line.Length - ($bookend.Length * 2)
    $paddingNeeded = $contentWidth - $message.Length
    $leftPad = [Math]::Floor($paddingNeeded / 2)
    $rightPad = [Math]::Ceiling($paddingNeeded / 2)
    $centeredMsg = "$bookend$(' ' * $leftPad)$message$(' ' * $rightPad)$bookend"
    
    Write-Host ""
    Write-Host "$color$line"
    Write-Host "$color$centeredMsg"
    Write-Host "$color$line$C_RESET"
    Write-Host ""
}

# --- Auto-detect execution environment ---
$executable = "python"
$prefixArgs = @()
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    if (-not $NoHeader.IsPresent) { Write-Host "`nPDM detected. Using 'pdm run' to execute Python scripts." -ForegroundColor Cyan }
    $executable = "pdm"
    $prefixArgs = "run", "python"
}
else {
    if (-not $NoHeader.IsPresent) { Write-Host "PDM not detected. Using standard 'python' command." -ForegroundColor Yellow }
}

function Invoke-FixExperiment {
    $C_CYAN = "`e[96m"; $C_GREEN = "`e[92m"; $C_YELLOW = "`e[93m"; $C_RED = "`e[91m"; $C_RESET = "`e[0m"
    
    function Invoke-FinalizeExperiment-Local {
        # This nested function handles the three-step finalization process.
        # It uses variables from the parent scope ($TargetDirectory, $executable, $prefixArgs).
        Write-Host "`n--- Rebuilding batch run log from replication data... ---" -ForegroundColor Cyan
        $logRebuildArgs = @("src/replication_log_manager.py", "rebuild", $TargetDirectory)
        & $executable $prefixArgs $logRebuildArgs
        if ($LASTEXITCODE -ne 0) { throw "Log rebuild failed with exit code $LASTEXITCODE" }

        Write-Host "`n--- Compiling final experiment summary... ---" -ForegroundColor Cyan
        $aggArgs = @("src/compile_experiment_results.py", $TargetDirectory)
        & $executable $prefixArgs $aggArgs
        if ($LASTEXITCODE -ne 0) { throw "Result aggregation failed with exit code $LASTEXITCODE" }

        Write-Host "`n--- Finalizing batch run log with summary... ---" -ForegroundColor Cyan
        $logFinalizeArgs = @("src/replication_log_manager.py", "finalize", $TargetDirectory)
        & $executable $prefixArgs $logFinalizeArgs
        if ($LASTEXITCODE -ne 0) { throw "Log finalization failed with exit code $LASTEXITCODE" }
        
        # The calling function is responsible for the final success message/audit.
    }
    
    $nonInteractive = $false
    
    # Ensure console output uses UTF-8.
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

    # --- Logging Setup ---
    $logFileName = "experiment_repair_log.txt"
    $logFilePath = Join-Path $TargetDirectory $logFileName

    try {
        # Use -Force to overwrite the log file, even if it's read-only.
        Start-Transcript -Path $logFilePath -Force | Out-Null
        
        Write-Host "" # Blank line before message
        Write-Host "The repair log will be saved to:" -ForegroundColor Gray
        $relativePath = Resolve-Path -Path $logFilePath -Relative
        Write-Host $relativePath -ForegroundColor Gray
        # --- Handle non-interactive force flags first ---
        if ($ForceUpdate.IsPresent) {
            Write-Host "`n--- Forcing experiment reprocessing... ---" -ForegroundColor Cyan
            $procArgs = @("src/experiment_manager.py", "--reprocess", $TargetDirectory, "--non-interactive")
            & $executable $prefixArgs $procArgs
            if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 99) { throw "Forced update process failed with exit code $LASTEXITCODE" }
            # A final verification is not needed here, as the calling script (`repair_study.ps1`) will do it.
            return
        }

        if ($ForceAggregate.IsPresent) {
            Write-Host "`n--- Forcing experiment re-aggregation... ---" -ForegroundColor Cyan
            Write-Host "Forcing re-aggregation on a VALIDATED experiment. All summary files will be re-created." -ForegroundColor Yellow
            Write-Host "--- Entering RE-AGGREGATION Mode ---" -ForegroundColor Yellow
            Invoke-FinalizeExperiment-Local
            # A final verification is not needed here, as the calling script (`repair_study.ps1`) will do it.
            return
        }
        Write-Header "STEP 1: DIAGNOSING EXPERIMENT STATE" $C_CYAN $C_RESET

        # Perform a single, direct audit. The script will display the full report,
        # and we will capture the exit code to determine the next action.
        $auditArgs = @("src/experiment_auditor.py", $TargetDirectory, "--force-color")
        & $executable $prefixArgs $auditArgs
        $auditExitCode = $LASTEXITCODE

        $actionTaken = $false
        $procArgs = $null

        switch ($auditExitCode) {
            0 { # AUDIT_ALL_VALID
                if ($NonInteractive.IsPresent) {
                    Write-Host "Experiment is already valid. No action needed." -ForegroundColor Green
                    return
                }

                # The audit report is already on screen.
                Write-Host "`nExperiment is already complete and valid." -ForegroundColor Yellow
                
                $prompt = @"

Do you still want to proceed with repair?

(1) Full Repair: Deletes all LLM responses and re-runs all API calls. (Expensive & Destructive)
(2) Full Update: Re-runs analysis on existing data for all replications. (Quick & Safe)
(3) Aggregation Only: Re-creates only the top-level summary files. (Fastest)
(N) No Action

Enter your choice (1, 2, 3, or N)
"@
                $choice = Read-Host -Prompt $prompt
                switch ($choice.Trim().ToLower()) {
                    '1' { # Force Full Repair
                        Write-Host "`nWARNING: This will delete all LLM responses in '$TargetDirectory' and re-run the API sessions." -ForegroundColor Red
                        Write-Host "Are you absolutely sure that you want to OVERWRITE the existing LLM responses? (Type 'YES' to confirm): " -NoNewline -ForegroundColor Red
                        $confirm = Read-Host
                        if ($confirm.Trim() -ceq 'YES') {
                            Write-Host ""; Write-Host "Deleting LLM responses..." -ForegroundColor Yellow
                            Get-ChildItem -Path $TargetDirectory -Filter "llm_response_*.txt" -Recurse | Remove-Item -Force
                            Write-Header "STEP 2: APPLYING REPAIRS / UPDATES" $C_CYAN $C_RESET
                            $procArgs = @("src/experiment_manager.py", $TargetDirectory, "--non-interactive")
                        } else { Write-Host "`nAction aborted by user.`n" -ForegroundColor Yellow; return }
                    }
                    '2' { # Force Full Update
                        Write-Header "STEP 2: APPLYING REPAIRS / UPDATES" $C_CYAN $C_RESET
                        $procArgs = @("src/experiment_manager.py", "--reprocess", $TargetDirectory, "--non-interactive")
                    }
                    '3' { # Force Aggregation
                        Write-Host "`n--- Starting experiment finalization... ---" -ForegroundColor Cyan
                        Invoke-FinalizeExperiment-Local
                        $actionTaken = $true
                    }
                    'n' { Write-Host "`nNo action taken.`n" -ForegroundColor Yellow; return }
                    default { Write-Warning "`nInvalid choice. No action taken.`n"; return }
                }
            }
            1 { # AUDIT_NEEDS_REPROCESS
                Write-Header "STEP 2: APPLYING ANALYSIS-ONLY UPDATE" $C_CYAN $C_RESET
                Write-Host "Diagnosis: Analysis or report files are outdated." -ForegroundColor Gray
                Write-Host "Action:    Applying a safe, local analysis update (no API calls needed)." -ForegroundColor Gray
                $procArgs = @("src/experiment_manager.py", "--reprocess", $TargetDirectory, "--non-interactive")
            }
            2 { # AUDIT_NEEDS_REPAIR
                Write-Header "STEP 2: APPLYING DATA-LEVEL REPAIR" $C_CYAN $C_RESET
                Write-Host "Diagnosis: Critical data (queries/responses) is missing or incomplete."
                Write-Host "Action:    Applying a data-level repair. This may re-run API calls."
                $procArgs = @("src/experiment_manager.py", $TargetDirectory, "--non-interactive")
            }
            3 { # AUDIT_NEEDS_MIGRATION
                Write-Header "REPAIR HALTED" $C_CYAN $C_RESET
                $message = "This experiment is not fixable in its current state. Please see the audit result and recommendation above."
                Write-Host "$($C_YELLOW)$message`n$($C_RESET)"
                exit 1
            }
            4 { # AUDIT_NEEDS_AGGREGATION
                Write-Host "`n--- Starting experiment finalization... ---" -ForegroundColor Cyan
                Invoke-FinalizeExperiment-Local
                $actionTaken = $true
            }
            default { throw "Audit script failed unexpectedly with exit code $auditExitCode. Cannot proceed." }
        }

        # If a python process was configured, run it now.
        if ($procArgs) {
            if ($StartRep) { $procArgs += "--start-rep", $StartRep }
            if ($EndRep) { $procArgs += "--end-rep", $EndRep }
            if ($Notes) { $procArgs += "--notes", $Notes }
            if ($Verbose.IsPresent) { $procArgs += "--verbose" }
            
            & $executable $prefixArgs $procArgs
            if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 99) { throw "Repair process failed with exit code $LASTEXITCODE" }
            $actionTaken = $true
        }

        # If any action was successfully taken, run a final verification to confirm the new state.
        if ($actionTaken) {
            Write-Header "STEP 3: FINAL VERIFICATION" $C_CYAN $C_RESET
            
            # Run the audit in non-interactive mode to suppress its default banner.
            $finalAuditArgs = @("src/experiment_auditor.py", $TargetDirectory, "--force-color", "--non-interactive")
            & $executable $prefixArgs $finalAuditArgs
            $finalAuditCode = $LASTEXITCODE

            if ($finalAuditCode -eq 0) { # 0 is AUDIT_ALL_VALID
                Write-Header "REPAIR SUCCESSFUL: Experiment is now valid." $C_GREEN $C_RESET
            } else {
                throw "Final verification failed. The experiment is still not valid."
            }
        }

    } catch {
        # Use the existing Write-Header function for a standardized failure banner.
        Write-Header "REPAIR FAILED" $C_RED $C_RESET
        
        # Print the specific error message from the 'throw' statement.
        Write-Host "$($C_RED)$($_.Exception.Message)$($C_RESET)`n"
        
        # Exit with a non-zero status code to signal failure to calling scripts.
        exit 1
    } finally {
        # Stop the transcript silently to suppress the default message
        Stop-Transcript | Out-Null
        
        # Only print the custom message if a log file was actually created.
        if (Test-Path -LiteralPath $logFilePath) {
            Write-Host "`nThe repair log has been saved to:" -ForegroundColor Gray
            $relativePath = Resolve-Path -Path $logFilePath -Relative
            Write-Host $relativePath -ForegroundColor Gray
            Write-Host "" # Add a blank line for spacing
        }
    }
}

# This invocation guard ensures the main execution logic is only triggered
# when the script is run directly (not dot-sourced).
if ($MyInvocation.InvocationName -ne '.') {
    Invoke-FixExperiment
}

# === End of fix_experiment.ps1 ===
